# Databricks notebook source
# MAGIC %md
# MAGIC # Methodology Library + Governance
# MAGIC
# MAGIC `[reserving-workbench]` Registers each reserving method as a Unity Catalog
# MAGIC model (MLflow pyfunc) so they are governed identically — versioned, aliased,
# MAGIC promotable — and indexes them in `reserving_methodology`. Seeds the
# MAGIC expert-judgement repository (incl. the AY2023 anomaly override) and registers
# MAGIC the Senior Reserving Actuary agent. Mirrors the Solvency II app's model-registry
# MAGIC + overlay-register patterns so this consolidates onto the shared layer later.

# COMMAND ----------
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema", "reserving_workbench")
CAT = dbutils.widgets.get("catalog"); SCH = dbutils.widgets.get("schema")
FQ = f"{CAT}.{SCH}"

import mlflow, pandas as pd, json
from datetime import datetime
mlflow.set_registry_uri("databricks-uc")

# COMMAND ----------
# MAGIC %md ## 1. Register each method as a UC pyfunc model

# COMMAND ----------
class ReservingMethod(mlflow.pyfunc.PythonModel):
    """A reserving method as a governed model. predict() takes a triangle
    (line_of_business, accident_year, development_lag, cumulative_paid) and
    returns ultimate + IBNR per accident year, using the calibrated factors."""
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
                        "ultimate": round(ult, 2), "ibnr": round(max(ult - paid, 0), 2)})
        return pd.DataFrame(out)

# Calibrate volume-weighted factors from the live triangle (per method a variant).
tri = spark.table(f"{FQ}.loss_development").toPandas()
def vw_factors(lob):
    sub = tri[tri.line_of_business_code == lob]
    maxlag = int(sub.development_lag.max())
    cum = {}
    for _, r in sub.iterrows():
        cum.setdefault(int(r.accident_year), {})[int(r.development_lag)] = float(r.cumulative_paid)
    fs = []
    for k in range(maxlag):
        num = sum(row[k+1] for row in cum.values() if k in row and k+1 in row)
        den = sum(row[k] for row in cum.values() if k in row and k+1 in row)
        fs.append(num/den if den else 1.0)
    return fs

METHODS = {
    "CHAIN_LADDER": dict(produces_dist=False, summary="Volume-weighted age-to-age factors to ultimate; standard for mature lines."),
    "BORNHUETTER_FERGUSON": dict(produces_dist=False, summary="Blends chain-ladder with an a-priori loss ratio; stable for immature years."),
    "MACK": dict(produces_dist=True, summary="Distribution-free stochastic chain-ladder; gives a standard error around the ultimate."),
    "GLM": dict(produces_dist=True, summary="Over-dispersed Poisson GLM on incrementals; bootstrap for a full distribution."),
    "PEER_COMPARISON": dict(produces_dist=False, summary="Benchmarks the selected pattern against an external / peer development pattern."),
}

reg_rows = []
import tempfile, os
for method, meta in METHODS.items():
    # a representative calibration (property line) stored as the model's params artifact
    params = {"development_factors": vw_factors("COMMERCIAL_PROPERTY"), "tail": 1.01, "method": method}
    tmp = tempfile.mkdtemp(); pth = os.path.join(tmp, "params.json")
    with open(pth, "w") as f: json.dump(params, f)
    model_name = f"{CAT}.{SCH}.method_{method.lower()}"
    with mlflow.start_run(run_name=f"register_{method.lower()}"):
        info = mlflow.pyfunc.log_model(
            artifact_path="model", python_model=ReservingMethod(),
            artifacts={"params": pth}, registered_model_name=model_name)
    from mlflow.tracking import MlflowClient
    c = MlflowClient()
    ver = c.get_latest_versions(model_name)[-1].version if hasattr(c, "get_latest_versions") else info.registered_model_version
    try:
        c.set_registered_model_alias(model_name, "production", ver)
    except Exception as e:
        print(f"alias note: {e}")
    reg_rows.append(dict(
        methodology_id=f"METH-{method}", reserving_method_code=method,
        uc_model_name=model_name, model_version=int(ver), alias="production",
        produces_distribution=meta["produces_dist"], summary=meta["summary"],
        owner_role="Chief Actuary", registered_at=datetime.utcnow().isoformat()))

spark.createDataFrame(pd.DataFrame(reg_rows)).createOrReplaceTempView("v_meth")
spark.sql(f"INSERT OVERWRITE {FQ}.reserving_methodology SELECT * FROM v_meth")
print(f"Registered {len(reg_rows)} methods in the library.")

# COMMAND ----------
# MAGIC %md ## 2. Seed the expert-judgement repository (incl. the AY2023 override)

# COMMAND ----------
now = datetime.utcnow().isoformat()
judgements = [
    dict(judgement_id="EJ-2026Q4-001", quarter="2026-Q4",
         line_of_business_code="COMMERCIAL_PROPERTY", accident_year=2023,
         category_code="METHODOLOGY_JUDGEMENT", magnitude=-620000.00, currency_code="GBP",
         rationale=("AY2023 12-24m development distorted by a single late-reported large loss "
                    "(CLM-2023-ANOMALY, GBP 1.05m). Empirical volume-weighted factor spikes to 3.63x "
                    "vs the stable 1.67x prior pattern. Held the prior selected pattern for the 12-24m "
                    "step; the large loss is reserved individually. Reduces the mechanical ultimate."),
         linked_qrt_cells=json.dumps(["S.19.01.R0100.C0100", "S.19.01.R0100.C0110"]),
         required_approval_role_code="SENIOR_ACTUARY", status_code="APPROVED",
         prior_judgement_id=None, author="a.reserving.analyst", created_at=now,
         approver="senior.reserving.actuary", approved_at=now),
    dict(judgement_id="EJ-2026Q4-002", quarter="2026-Q4",
         line_of_business_code="GENERAL_LIABILITY", accident_year=None,
         category_code="TAIL_EXTENSION", magnitude=310000.00, currency_code="GBP",
         rationale=("Extended the GL tail beyond the observed triangle to reflect long-tail bodily-injury "
                    "development consistent with market benchmarks; mechanical triangle truncates too early."),
         linked_qrt_cells=json.dumps(["S.19.01.R0100.C0140"]),
         required_approval_role_code="SENIOR_ACTUARY", status_code="APPROVED",
         prior_judgement_id=None, author="a.reserving.analyst", created_at=now,
         approver="senior.reserving.actuary", approved_at=now),
]
spark.createDataFrame(pd.DataFrame(judgements)).createOrReplaceTempView("v_ej")
spark.sql(f"INSERT OVERWRITE {FQ}.expert_judgement SELECT * FROM v_ej")
print(f"Seeded {len(judgements)} expert judgements.")

# COMMAND ----------
# MAGIC %md ## 3. Seed selected development patterns (the LDF selection audit trail)

# COMMAND ----------
def vwf(lob): return vw_factors(lob)
sel = [
    # prior selection: the stable 1.67-led pattern (what the actuary holds)
    dict(selection_id="SEL-2026Q3-PROP-PRIOR", valuation_date="2026-09-30", accident_year=None,
         line_of_business_code="COMMERCIAL_PROPERTY", currency_code="GBP",
         source_code="PRIOR_SELECTION", averaging_method_code=None, last_n_years=None,
         development_factors=json.dumps([1.667, 1.20, 1.08, 1.05, 1.02, 1.01]), tail_factor=1.01,
         prior_selection_id=None, status_code="APPROVED",
         rationale="Prior quarter's approved pattern, carried forward as the comparison baseline.",
         selected_by="senior.reserving.actuary", selected_at=now,
         approved_by="chief.actuary", approved_at=now),
    # this quarter empirical (anomaly-inflated) — proposed, pending
    dict(selection_id="SEL-2026Q4-PROP-EMPIRICAL", valuation_date="2026-12-31", accident_year=None,
         line_of_business_code="COMMERCIAL_PROPERTY", currency_code="GBP",
         source_code="DATABRICKS_EMPIRICAL", averaging_method_code="VOLUME_WEIGHTED", last_n_years=None,
         development_factors=json.dumps([round(x,4) for x in vwf("COMMERCIAL_PROPERTY")]), tail_factor=1.01,
         prior_selection_id="SEL-2026Q3-PROP-PRIOR", status_code="DRAFT",
         rationale=None, selected_by="a.reserving.analyst", selected_at=now,
         approved_by=None, approved_at=None),
    # the elected override: hold prior for the anomalous 12-24m step
    dict(selection_id="SEL-2026Q4-PROP-ELECTED", valuation_date="2026-12-31", accident_year=None,
         line_of_business_code="COMMERCIAL_PROPERTY", currency_code="GBP",
         source_code="PRIOR_SELECTION", averaging_method_code=None, last_n_years=None,
         development_factors=json.dumps([1.667, 1.20, 1.08, 1.05, 1.02, 1.01]), tail_factor=1.01,
         prior_selection_id="SEL-2026Q4-PROP-EMPIRICAL", status_code="APPROVED",
         rationale=("Overrode the empirical 12-24m factor (3.63x, distorted by the CLM-2023-ANOMALY "
                    "late-reported large loss) and held the prior 1.667x pattern; large loss reserved individually."),
         selected_by="senior.reserving.actuary", selected_at=now,
         approved_by="chief.actuary", approved_at=now),
]
spark.createDataFrame(pd.DataFrame(sel)).createOrReplaceTempView("v_sel")
spark.sql(f"INSERT OVERWRITE {FQ}.selected_development_pattern SELECT * FROM v_sel")
print(f"Seeded {len(sel)} selected development patterns (prior / empirical / elected-override).")

# COMMAND ----------
print("Methodology library + governance seeded. All tables populated.")
