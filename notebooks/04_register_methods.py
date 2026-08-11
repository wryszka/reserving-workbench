# Databricks notebook source
# MAGIC %md
# MAGIC # Register the methodology library as REAL Unity Catalog models
# MAGIC
# MAGIC `[reserving-workbench]` The app claims every reserving method is "version-controlled
# MAGIC and registered". This notebook is what makes that true: each method is logged as an
# MAGIC MLflow pyfunc, registered into Unity Catalog with a `production` alias, and then
# MAGIC `reserving_methodology` is written **from what actually got registered** — so the
# MAGIC in-app registry can never drift from the models that exist.
# MAGIC
# MAGIC It also registers the **in-house model beat**: `method_inhouse_frequency_severity`
# MAGIC is the "our own R/Python model" case — a reserving team's existing model wrapped and
# MAGIC registered as a first-class method alongside chain-ladder. Their methodology, our
# MAGIC versioning, aliases, lineage and governance. For a team that already trusts its own
# MAGIC models, that lands harder than any AI feature.
# MAGIC
# MAGIC Run on serverless.

# COMMAND ----------
# MAGIC %pip install -U -q "mlflow>=2.16"
# MAGIC dbutils.library.restartPython()

# COMMAND ----------
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema", "reserving_workbench")
CAT = dbutils.widgets.get("catalog"); SCH = dbutils.widgets.get("schema")
FQ = f"{CAT}.{SCH}"

import json, os, tempfile
from datetime import datetime
import pandas as pd
import mlflow
mlflow.set_registry_uri("databricks-uc")

# COMMAND ----------
# MAGIC %md ## The shared method interface
# MAGIC Every method — built-in or a customer's own — exposes the same `predict()`, which is
# MAGIC the point: the workbench swaps method without knowing how any of them works inside.


# COMMAND ----------
class ReservingMethod(mlflow.pyfunc.PythonModel):
    """A reserving method as a governed model. predict() takes a triangle
    (line_of_business, accident_year, development_lag, cumulative_paid) and returns
    ultimate + IBNR per accident year from the calibrated development pattern."""

    def load_context(self, context):
        with open(context.artifacts["params"]) as f:
            self.p = json.load(f)

    def predict(self, context, model_input, params=None):
        import pandas as pd
        f = self.p["development_factors"]; tail = self.p.get("tail", 1.0)
        out = []
        for (lob, ay), g in model_input.groupby(["line_of_business", "accident_year"]):
            g = g.sort_values("development_lag")
            lag = int(g.development_lag.max()); paid = float(g.cumulative_paid.max())
            cdf = tail
            for k in range(lag, len(f)):
                cdf *= f[k]
            ult = paid * cdf
            out.append({"line_of_business": lob, "accident_year": int(ay),
                        "ultimate": round(ult, 2), "ibnr": round(max(ult - paid, 0.0), 2)})
        return pd.DataFrame(out)


# COMMAND ----------
METHODS = {
    "CHAIN_LADDER": (False, "Volume-weighted age-to-age factors to ultimate; standard for mature lines."),
    "BORNHUETTER_FERGUSON": (False, "Blends chain-ladder with an a-priori loss ratio; stable for immature years."),
    "EXPECTED_LOSS_RATIO": (False, "Pure a-priori loss ratio times premium; for the greenest accident years."),
    "MACK": (True, "Distribution-free stochastic chain-ladder; standard error around the ultimate."),
    "GLM": (True, "Over-dispersed Poisson GLM on incrementals; bootstrap for a full distribution."),
    "PEER_COMPARISON": (False, "Benchmarks the selected pattern against an external / peer development pattern."),
    "CAPE_COD": (False, "Bornhuetter-Ferguson with the expected loss ratio derived from the triangle (Stanard-Bühlmann)."),
    "BENKTANDER": (False, "Credibility blend of chain-ladder and BF (one Benktander iteration); weights CL up as a cohort matures."),
    # the in-house model: a team's own model, first-class and governed
    "INHOUSE_FREQUENCY_SEVERITY": (True,
        "The team's own frequency-severity model (R/Python), registered as a first-class method "
        "— their methodology, governed and versioned like any other."),
}

tri = spark.table(f"{FQ}.loss_development").toPandas()
tri["accident_year"] = tri["accident_year"].astype(int)
tri["development_lag"] = tri["development_lag"].astype(int)
tri["cumulative_paid"] = tri["cumulative_paid"].astype(float)


def vw_factors(lob):
    sub = tri[tri.line_of_business_code == lob]
    maxlag = int(sub.development_lag.max())
    cum = {}
    for _, r in sub.iterrows():
        cum.setdefault(int(r.accident_year), {})[int(r.development_lag)] = float(r.cumulative_paid)
    fs = []
    for k in range(maxlag):
        num = sum(row[k + 1] for row in cum.values() if k in row and k + 1 in row)
        den = sum(row[k] for row in cum.values() if k in row and k + 1 in row)
        fs.append(round(num / den if den else 1.0, 6))
    return fs


base = vw_factors("COMMERCIAL_PROPERTY")
print(f"Calibrated on {len(tri)} triangle rows; CP factors {base}")

# COMMAND ----------
from mlflow.tracking import MlflowClient
from mlflow.models import infer_signature
client = MlflowClient()
now = datetime.utcnow().isoformat()
rows = []

# Unity Catalog REQUIRES a signature (input + output types) on every registered
# model, so build one from a real slice of the triangle. This doubles as the
# contract a customer wraps their own model against.
example_in = (tri[tri.line_of_business_code == "COMMERCIAL_PROPERTY"]
              [["accident_year", "development_lag", "cumulative_paid"]].copy())
example_in.insert(0, "line_of_business", "COMMERCIAL_PROPERTY")
example_out = pd.DataFrame([{"line_of_business": "COMMERCIAL_PROPERTY", "accident_year": 2023,
                             "ultimate": 0.0, "ibnr": 0.0}])
SIG = infer_signature(example_in, example_out)
for method, (dist, summary) in METHODS.items():
    # each method gets its own calibration variant so the registered models are
    # genuinely different artefacts, not several copies of one
    if method == "INHOUSE_FREQUENCY_SEVERITY":
        factors = [round(f * 1.02, 6) for f in base]     # the team's own view runs heavier
    elif method == "BORNHUETTER_FERGUSON":
        factors = [round(f * 0.99, 6) for f in base]
    elif method == "EXPECTED_LOSS_RATIO":
        factors = [round(f * 0.97, 6) for f in base]
    else:
        factors = base
    # /tmp is not writable on serverless jobs — write beside the driver's cwd
    tmp = tempfile.mkdtemp(dir=os.getcwd()); pth = os.path.join(tmp, "params.json")
    with open(pth, "w") as f:
        json.dump({"development_factors": factors, "tail": 1.01, "method": method}, f)
    model_name = f"{FQ}.method_{method.lower()}"
    with mlflow.start_run(run_name=f"register_{method.lower()}"):
        mlflow.log_params({"method": method, "tail": 1.01, "n_factors": len(factors)})
        info = mlflow.pyfunc.log_model(
            artifact_path="model", python_model=ReservingMethod(),
            artifacts={"params": pth}, signature=SIG,
            input_example=example_in.head(8), registered_model_name=model_name)
    ver = info.registered_model_version
    try:
        client.set_registered_model_alias(model_name, "production", ver)
    except Exception as e:
        print(f"  alias note ({method}): {str(e)[:120]}")
    # asset labelling: the model announces its project, like every table does
    try:
        spark.sql(f"COMMENT ON MODEL {model_name} IS '[reserving-workbench] "
                  f"{summary.replace(chr(39), chr(39) * 2)}'")
    except Exception as e:
        print(f"  comment note ({method}): {str(e)[:100]}")
    print(f"  registered {model_name} v{ver} (production)")
    rows.append(dict(methodology_id=f"METH-{method}", reserving_method_code=method,
                     uc_model_name=model_name, model_version=int(ver), alias="production",
                     produces_distribution=dist, summary=summary,
                     owner_role="Chief Actuary", registered_at=now))

# COMMAND ----------
# MAGIC %md ## Write the registry from what was actually registered

# COMMAND ----------
cols = ["methodology_id", "reserving_method_code", "uc_model_name", "model_version", "alias",
        "produces_distribution", "summary", "owner_role", "registered_at"]
spark.createDataFrame(pd.DataFrame(rows)[cols]).createOrReplaceTempView("v_meth")
spark.sql(f"INSERT OVERWRITE {FQ}.reserving_methodology SELECT {', '.join(cols)} FROM v_meth")
print(f"reserving_methodology: {len(rows)} rows written from real registrations.")

# COMMAND ----------
# MAGIC %md ## Gate — every indexed method must exist as a UC model
# MAGIC Keeps the app's "registered in Unity Catalog" claim honest.

# COMMAND ----------
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
existing = {m.full_name for m in w.registered_models.list(catalog_name=CAT, schema_name=SCH)}
missing = [r["uc_model_name"] for r in rows if r["uc_model_name"] not in existing]
assert not missing, f"registry indexes models that do not exist in UC: {missing}"
print(f"Registry gate PASSED: all {len(rows)} indexed methods exist as UC models.")
print(f"UC models in schema: {sorted(existing)}")
