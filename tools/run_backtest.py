#!/usr/bin/env python3
"""Champion/challenger back-testing — replay every method at every past valuation.

The claim ledger spans 2019-2026. A "valuation as at year Y" is simply the triangle
built from movements with transaction_year <= Y. So for each past valuation we can
re-run every method exactly as it would have run then, and score its projected
ultimate against what has actually emerged since (the latest view of the cohort).

Writes method_backtest: one row per (valuation_year, line, accident_year, method).
This is the data behind "which method has been most accurate on this line over the
last N valuations" — a metric no spreadsheet team maintains and most packages don't
offer. Pure replay over the one ledger; no separate history stored.

Usage:
    uv run --native-tls --with databricks-sdk --with pandas --with numpy \
        tools/run_backtest.py --profile DEV --warehouse-id a3b61648ea4809e3
"""
import argparse
from datetime import datetime
import pandas as pd
from databricks.sdk import WorkspaceClient

CAT, SCH = "lr_dev_aws_us_catalog", "reserving_workbench"
FQ = f"{CAT}.{SCH}"
APRIORI_LR = 0.62
# valuations to replay — need enough maturity to score, so start a few years in
BACKTEST_YEARS = [2022, 2023, 2024, 2025]
LATEST = 2026

# Collision-free line code (lob[:4] collides COMMERCIAL_PROPERTY/COMMERCIAL_MOTOR → "COMM").
LINE_CODE = {"COMMERCIAL_PROPERTY": "CPRP", "COMMERCIAL_MOTOR": "CMOT",
             "GENERAL_LIABILITY": "GENL", "PROFESSIONAL_INDEMNITY": "PROF", "MARINE": "MARN"}
def lc(lob):
    return LINE_CODE.get(lob, (lob[:4]).upper())


def q(w, wid, sql):
    r = w.statement_execution.execute_statement(statement=sql, warehouse_id=wid, wait_timeout="50s")
    while r.status.state.value in ("PENDING", "RUNNING"):
        r = w.statement_execution.get_statement(r.statement_id)
    if r.status.state.value != "SUCCEEDED":
        raise RuntimeError((r.status.error.message if r.status.error else "?") + f"\n{sql[:300]}")
    return r


def read_df(w, wid, sql):
    r = q(w, wid, sql)
    return pd.DataFrame(r.result.data_array or [], columns=[c.name for c in r.manifest.schema.columns])


def sv(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def overwrite(w, wid, table, cols, rows):
    fq = f"{FQ}.`{table}`"
    if not rows:
        q(w, wid, f"DELETE FROM {fq} WHERE 1=1"); return 0
    first = True
    for i in range(0, len(rows), 400):
        part = rows[i:i+400]
        vals = ",\n".join("(" + ", ".join(sv(r.get(c)) for c in cols) + ")" for r in part)
        q(w, wid, f"{'INSERT OVERWRITE' if first else 'INSERT INTO'} {fq} ({', '.join(cols)}) VALUES\n{vals};")
        first = False
    return len(rows)


# ---- triangle-as-at from the raw ledger, truncated to a valuation year ----
def triangle_asof(ledger, val_year):
    """{lob: {ay: {lag: cum_paid}}} using only movements with transaction_year <= val_year."""
    sub = ledger[ledger.transaction_year <= val_year]
    out = {}
    # incremental paid = indemnity + expense - recovery, per (lob, ay, lag)
    for _, r in sub.iterrows():
        ay = int(r.accident_year); ty = int(r.transaction_year); lag = ty - ay
        if lag < 0:
            continue
        t = r.claim_transaction_type_code; amt = float(r.amount)
        inc = amt if t in ("INDEMNITY_PAYMENT", "EXPENSE_PAYMENT") else (-amt if t == "RECOVERY" else 0.0)
        if inc == 0.0:
            continue
        d = out.setdefault(r.line_of_business_code, {}).setdefault(ay, {})
        d[lag] = d.get(lag, 0.0) + inc
    # incremental -> cumulative
    for lob in out:
        for ay in out[lob]:
            run = 0.0
            for lag in sorted(out[lob][ay]):
                run += out[lob][ay][lag]; out[lob][ay][lag] = round(run, 2)
    return out


def a2a(tri, max_lag):
    f = {}
    for k in range(max_lag):
        num = sum(row[k+1] for row in tri.values() if k in row and k+1 in row)
        den = sum(row[k] for row in tri.values() if k in row and k+1 in row)
        f[k] = num/den if den else 1.0
    return f


def cdf(f, frm, max_lag, tail=1.01):
    x = tail
    for k in range(frm, max_lag):
        x *= f.get(k, 1.0)
    return x


def project(tri, max_lag):
    """Return {ay: {method: ultimate}} for the triangle at one valuation."""
    f = a2a(tri, max_lag)
    # Cape Cod ELR from this triangle
    cc_num = cc_den = 0.0
    for ay, row in tri.items():
        lag = max(row); paid = row[lag]; c = cdf(f, lag, max_lag)
        rep = 1.0/c if c else 1.0
        prem = paid / APRIORI_LR
        cc_num += paid; cc_den += prem * rep
    elr = (cc_num/cc_den) if cc_den else APRIORI_LR
    out = {}
    for ay, row in tri.items():
        lag = max(row); paid = row[lag]
        c = cdf(f, lag, max_lag); cl = paid * c
        prem = paid / APRIORI_LR; apri = prem * APRIORI_LR
        pct_unpaid = 1.0 - (1.0/c if c else 1.0); pct_rep = (1.0/c if c else 1.0)
        bf = paid + apri * pct_unpaid
        out[ay] = {
            "CHAIN_LADDER": cl,
            "BORNHUETTER_FERGUSON": bf,
            "EXPECTED_LOSS_RATIO": apri,
            "CAPE_COD": paid + (prem*elr)*pct_unpaid,
            "BENKTANDER": pct_rep*cl + (1.0-pct_rep)*bf,
        }
    return out


def run(w, wid):
    """Reusable entrypoint — the Job wrappers call this so the tested logic runs
    unchanged whether invoked from the CLI or a Databricks task."""

    ledger = read_df(w, wid, f"""
        SELECT c.line_of_business_code, c.accident_year, t.transaction_year,
               t.claim_transaction_type_code, t.amount
        FROM {FQ}.`1_raw_claim` c JOIN {FQ}.`1_raw_claim_transaction` t ON t.claim_id = c.claim_id""")
    for col in ("accident_year", "transaction_year"):
        ledger[col] = ledger[col].astype(int)
    ledger["amount"] = ledger["amount"].astype(float)

    # "emerged" = the cohort's ACTUAL developed losses at the latest valuation — the
    # latest cumulative paid, with only a tiny residual tail. Crucially this is NOT a
    # chain-ladder projection: if it were, we'd be grading chain-ladder against a future
    # version of itself and it would always look best (it wouldn't be a fair test). Using
    # near-emerged actuals means no method is the yardstick.
    #
    # We can only do this honestly for cohorts that are MATURE NOW (latest development age
    # >= MIN_MATURITY): a 2019 cohort seen in 2026 is ~7 years run off, so its paid is
    # essentially its ultimate and the residual tail is negligible. Younger cohorts have no
    # trustworthy "actual" yet, so they're excluded — that's the honest boundary.
    MIN_MATURITY = 4
    RESID_TAIL = 1.01     # small fixed tail on the near-final paid, identical for every method
    latest_tri = triangle_asof(ledger, LATEST)
    emerged = {}
    for lob, t in latest_tri.items():
        emerged[lob] = {}
        for ay, row in t.items():
            age = LATEST - ay
            if age < MIN_MATURITY:
                continue    # not run off enough to have a trustworthy actual
            latest_paid = row[max(row)]
            emerged[lob][ay] = latest_paid * RESID_TAIL

    rows = []
    for vy in BACKTEST_YEARS:
        tri = triangle_asof(ledger, vy)
        for lob, t in tri.items():
            ml = max(max(r) for r in t.values())
            if ml < 1:
                continue
            proj = project(t, ml)
            for ay, methods in proj.items():
                em = emerged.get(lob, {}).get(ay)
                if not em or em <= 0:
                    continue
                age = vy - ay
                if age < 0:
                    continue
                for method, ult in methods.items():
                    rows.append(dict(
                        backtest_id=f"BT-{vy}-{lc(lob)}-{ay}-{method[:2]}",
                        valuation_year=vy, line_of_business_code=lob, accident_year=ay,
                        reserving_method_code=method, projected_ultimate=round(ult, 2),
                        emerged_ultimate=round(em, 2), error_pct=round((ult-em)/em, 4),
                        development_age=age, currency_code="GBP"))

    n = overwrite(w, wid, "method_backtest",
        ["backtest_id", "valuation_year", "line_of_business_code", "accident_year",
         "reserving_method_code", "projected_ultimate", "emerged_ultimate", "error_pct",
         "development_age", "currency_code"], rows)
    print(f"method_backtest: {n} rows across {len(BACKTEST_YEARS)} valuations")

    # sanity summary: mean absolute error by method (immature cohorts, age<=2, where it matters)
    import statistics
    by_m = {}
    for r in rows:
        if r["development_age"] <= 2:
            by_m.setdefault(r["reserving_method_code"], []).append(abs(r["error_pct"]))
    print("Mean abs error on immature cohorts (age<=2), by method:")
    for m, errs in sorted(by_m.items(), key=lambda kv: statistics.mean(kv[1])):
        print(f"  {m:22s} {statistics.mean(errs)*100:5.1f}%  (n={len(errs)})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="DEV")
    ap.add_argument("--warehouse-id", default="a3b61648ea4809e3")
    args = ap.parse_args()
    run(WorkspaceClient(profile=args.profile), args.warehouse_id)

if __name__ == "__main__":
    main()
