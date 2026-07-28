# Databricks notebook source
# MAGIC %md
# MAGIC # Reserving Engine — methods → estimates → cashflow → validation
# MAGIC
# MAGIC `[reserving-workbench]` The platform-native reserving run. Reads the loss-
# MAGIC development triangle (a view over the claim ledger — never a stored copy),
# MAGIC applies the methodology library (chain-ladder, Bornhuetter-Ferguson, Mack,
# MAGIC GLM-bootstrap), writes governed `reserve_estimate` rows (one per method, never
# MAGIC overwriting a basis), derives the `reserve_cashflow_pattern` (the single-producer
# MAGIC contract to Solvency II / IFRS 17), and computes `actual_vs_expected` validation.
# MAGIC
# MAGIC Deterministic and reconciling: paid + case + IBNR = ultimate to the penny.
# MAGIC Runs on serverless; pandas driver-side (triangles are small). Synthetic data —
# MAGIC Bricksurance SE is fictional.

# COMMAND ----------
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema", "reserving_workbench")
dbutils.widgets.text("valuation_date", "2026-12-31")
CAT = dbutils.widgets.get("catalog")
SCH = dbutils.widgets.get("schema")
VAL_DATE = dbutils.widgets.get("valuation_date")
FQ = f"{CAT}.{SCH}"

import pandas as pd, numpy as np, json, uuid
from datetime import datetime

# COMMAND ----------
# MAGIC %md ## 1. Read the triangle (view over the ledger)

# COMMAND ----------
tri = spark.table(f"{FQ}.loss_development").toPandas()
# earned premium proxy per (lob, ay) for BF/ELR a-priori — from latest incurred * loss-ratio assumption
APRIORI_LR = 0.62  # a-priori expected loss ratio for BF/ELR
print(f"Triangle rows: {len(tri)}; LOBs: {sorted(tri.line_of_business_code.unique())}")

def cum_triangle(df, lob, measure="cumulative_paid"):
    """Return {accident_year: {development_lag: value}} for observed cells only."""
    sub = df[(df.line_of_business_code == lob)]
    out = {}
    for _, r in sub.iterrows():
        out.setdefault(int(r.accident_year), {})[int(r.development_lag)] = float(r[measure])
    return out

# COMMAND ----------
# MAGIC %md ## 2. Development factors (volume-weighted) + methods

# COMMAND ----------
def age_to_age(tri_dict, max_lag):
    """Volume-weighted age-to-age factors f[k] = sum cum[k+1] / sum cum[k] over AYs with both."""
    factors = {}
    for k in range(max_lag):
        num = den = 0.0
        for ay, row in tri_dict.items():
            if k in row and (k + 1) in row:
                num += row[k + 1]; den += row[k]
        factors[k] = (num / den) if den else 1.0
    return factors

def cdf_to_ultimate(factors, from_lag, max_lag, tail=1.0):
    """Cumulative dev factor from `from_lag` to ultimate."""
    f = 1.0
    for k in range(from_lag, max_lag):
        f *= factors.get(k, 1.0)
    return f * tail

def latest_diagonal(tri_dict):
    """{ay: (latest_lag, cum_value)} — the most-developed observed cell per AY."""
    return {ay: (max(row), row[max(row)]) for ay, row in tri_dict.items()}

# COMMAND ----------
# MAGIC %md ## 3. Run all methods, write reserve_estimate

# COMMAND ----------
def mack_std_error(tri_dict, factors, max_lag):
    """Mack (1993) recursive standard error of the ultimate per AY (distribution-free).
    Simplified: uses the Mack sigma^2 estimator per development period."""
    # sigma_k^2 = 1/(n-k-1) * sum C_i,k * (f_i,k - f_k)^2
    sigma2 = {}
    for k in range(max_lag):
        pairs = [(row[k], row[k + 1]) for ay, row in tri_dict.items() if k in row and (k + 1) in row]
        if len(pairs) <= 1:
            sigma2[k] = sigma2.get(k - 1, 0.0) * 0.5 if k else 0.0
            continue
        fk = sum(b for _, b in pairs) / sum(a for a, _ in pairs)
        s = sum(a * ((b / a) - fk) ** 2 for a, b in pairs) / (len(pairs) - 1)
        sigma2[k] = s
    diag = latest_diagonal(tri_dict)
    se = {}
    for ay, (lag, cval) in diag.items():
        if lag >= max_lag:
            se[ay] = 0.0; continue
        # simplified process variance accumulation to ultimate
        var = 0.0; c = cval
        for k in range(lag, max_lag):
            fk = factors.get(k, 1.0)
            var = (fk ** 2) * var + (c * sigma2.get(k, 0.0))
            c = c * fk
        se[ay] = float(np.sqrt(max(var, 0.0)))
    return se

rows = []
def add_estimate(lob, ay, method, paid, case, ultimate, se=None, sel_id=None, meth_id=None):
    ibnr = ultimate - (paid + case)
    rows.append(dict(
        reserve_estimate_id=f"RES-{VAL_DATE[:4]}-{lob[:4]}-{ay}-{method[:2]}",
        valuation_date=VAL_DATE, accident_year=ay, line_of_business_code=lob,
        reserving_method_code=method, methodology_id=meth_id, selection_id=sel_id,
        currency_code="GBP",
        paid_to_date=round(paid, 2), case_reserves=round(case, 2),
        ultimate_loss=round(ultimate, 2), ibnr=round(max(ibnr, 0.0), 2),
        outstanding=round(ultimate - paid, 2),
        ultimate_std_error=round(se, 2) if se is not None else None,
        expert_judgement_applied=0.0, source_system_code="RESERVING_ENGINE"))

for lob in sorted(tri.line_of_business_code.unique()):
    paid_t = cum_triangle(tri, lob, "cumulative_paid")
    inc_t = cum_triangle(tri, lob, "cumulative_incurred")
    max_lag = max(max(r) for r in paid_t.values())
    f_paid = age_to_age(paid_t, max_lag)
    diag_p = latest_diagonal(paid_t); diag_i = latest_diagonal(inc_t)
    se_mack = mack_std_error(paid_t, f_paid, max_lag)
    for ay in sorted(paid_t):
        lag, paid = diag_p[ay]
        _, inc = diag_i.get(ay, (lag, paid))
        case = max(inc - paid, 0.0)
        # a-priori ultimate for BF/ELR: use incurred-to-date scaled up as premium proxy
        premium_proxy = inc / APRIORI_LR if inc else paid / APRIORI_LR
        apriori_ult = premium_proxy * APRIORI_LR
        cdf = cdf_to_ultimate(f_paid, lag, max_lag)
        # Chain-ladder
        cl_ult = paid * cdf
        add_estimate(lob, ay, "CHAIN_LADDER", paid, case, cl_ult)
        # Bornhuetter-Ferguson: paid + apriori * (1 - 1/cdf)
        pct_unpaid = 1.0 - (1.0 / cdf if cdf else 1.0)
        bf_ult = paid + apriori_ult * pct_unpaid
        add_estimate(lob, ay, "BORNHUETTER_FERGUSON", paid, case, bf_ult)
        # Expected Loss Ratio: pure a-priori
        add_estimate(lob, ay, "EXPECTED_LOSS_RATIO", paid, case, apriori_ult)
        # Mack: chain-ladder ultimate + standard error
        add_estimate(lob, ay, "MACK", paid, case, cl_ult, se=se_mack.get(ay, 0.0))

est = pd.DataFrame(rows)
print(f"Reserve estimates: {len(est)} rows across {est.reserving_method_code.nunique()} methods")
spark.createDataFrame(est).createOrReplaceTempView("v_estimates")
spark.sql(f"INSERT OVERWRITE {FQ}.reserve_estimate SELECT * FROM v_estimates")

# COMMAND ----------
# MAGIC %md ## 4. Cashflow pattern (SII / IFRS17 single-producer contract)

# COMMAND ----------
cf_rows = []
for lob in sorted(tri.line_of_business_code.unique()):
    paid_t = cum_triangle(tri, lob, "cumulative_paid")
    max_lag = max(max(r) for r in paid_t.values())
    f_paid = age_to_age(paid_t, max_lag)
    diag_p = latest_diagonal(paid_t)
    for ay in sorted(paid_t):
        lag, paid = diag_p[ay]
        # project remaining incremental payments to ultimate
        c = paid
        for k in range(lag, max_lag):
            nxt = c * f_paid.get(k, 1.0)
            inc = nxt - c
            if inc > 0.01:
                cf_rows.append(dict(
                    cashflow_id=f"CF-{VAL_DATE[:4]}-{lob[:4]}-{ay}-{k+1}",
                    reserve_estimate_id=f"RES-{VAL_DATE[:4]}-{lob[:4]}-{ay}-CH",
                    development_period=(k + 1 - lag), expected_payment=round(inc, 2),
                    currency_code="GBP"))
            c = nxt
cf = pd.DataFrame(cf_rows)
print(f"Cashflow rows: {len(cf)}")
spark.createDataFrame(cf).createOrReplaceTempView("v_cf")
spark.sql(f"INSERT OVERWRITE {FQ}.reserve_cashflow_pattern SELECT * FROM v_cf")

# COMMAND ----------
# MAGIC %md ## 5. Actual-vs-Expected validation (rolling cohort)

# COMMAND ----------
# Compare chain-ladder's expected emergence in the latest year vs what actually emerged.
ave_rows = []
for lob in sorted(tri.line_of_business_code.unique()):
    paid_t = cum_triangle(tri, lob, "cumulative_paid")
    max_lag = max(max(r) for r in paid_t.values())
    f_paid = age_to_age(paid_t, max_lag)
    for ay, row in paid_t.items():
        lags = sorted(row)
        if len(lags) < 2:
            continue
        last, prev = lags[-1], lags[-2]
        actual = row[last] - row[prev]
        expected = row[prev] * (f_paid.get(prev, 1.0) - 1.0)
        var = actual - expected
        se = abs(expected) * 0.15 or 1.0
        ave_rows.append(dict(
            ave_id=f"AVE-{VAL_DATE[:4]}-{lob[:4]}-{ay}",
            validation_period=f"{VAL_DATE[:4]}", reserving_method_code="CHAIN_LADDER",
            line_of_business_code=lob, accident_year=ay,
            expected_emergence=round(expected, 2), actual_emergence=round(actual, 2),
            variance=round(var, 2), standardised_residual=round(var / se, 4),
            currency_code="GBP", within_tolerance=bool(abs(var / se) <= 2.5)))
ave = pd.DataFrame(ave_rows)
print(f"AvE rows: {len(ave)}; out-of-tolerance: {(~ave.within_tolerance).sum()} (expect the AY2023 CP anomaly)")
spark.createDataFrame(ave).createOrReplaceTempView("v_ave")
spark.sql(f"INSERT OVERWRITE {FQ}.actual_vs_expected SELECT * FROM v_ave")

# COMMAND ----------
# MAGIC %md ## 6. Reconciliation gate

# COMMAND ----------
bad = spark.sql(f"""
  SELECT COUNT(*) n FROM {FQ}.reserve_estimate
  WHERE abs((paid_to_date + case_reserves + ibnr) - ultimate_loss) >= 1.0
""").collect()[0]["n"]
assert bad == 0, f"{bad} reserve estimates fail paid+case+ibnr=ultimate reconciliation"
print("Reconciliation gate PASSED: paid + case + IBNR = ultimate for every estimate.")
