#!/usr/bin/env python3
"""Run the reserving engine against the LIVE triangle and write results.

Reads loss_development from the warehouse, applies the methodology library
(chain-ladder, BF, ELR, Mack), writes reserve_estimate + reserve_cashflow_pattern
+ actual_vs_expected, then seeds the governance tables (methodology registry,
expert judgements, selected patterns). Pure SQL/pandas via the Statement
Execution API so it runs for real without a cluster; the MLflow pyfunc
registration lives in notebooks/02 for the job path.

Usage:
    uv run --native-tls --with databricks-sdk --with pandas --with numpy \
        tools/run_reserving.py --profile DEV --warehouse-id a3b61648ea4809e3
"""
import argparse, json
from datetime import datetime
import numpy as np, pandas as pd
from databricks.sdk import WorkspaceClient

CAT, SCH = "lr_dev_aws_us_catalog", "reserving_workbench"
FQ = f"{CAT}.{SCH}"
VAL_DATE = "2026-12-31"
APRIORI_LR = 0.62


def q(w, wid, sql):
    r = w.statement_execution.execute_statement(statement=sql, warehouse_id=wid, wait_timeout="50s")
    while r.status.state.value in ("PENDING", "RUNNING"):
        r = w.statement_execution.get_statement(r.statement_id)
    if r.status.state.value != "SUCCEEDED":
        raise RuntimeError((r.status.error.message if r.status.error else "?") + f"\n--SQL--\n{sql[:400]}")
    return r


def read_df(w, wid, sql):
    r = q(w, wid, sql)
    cols = [c.name for c in r.manifest.schema.columns]
    data = r.result.data_array or []
    return pd.DataFrame(data, columns=cols)


def sv(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
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
        verb = "INSERT OVERWRITE" if first else "INSERT INTO"
        q(w, wid, f"{verb} {fq} ({', '.join(cols)}) VALUES\n{vals};")
        first = False
    return len(rows)


# ---- actuarial helpers -------------------------------------------------------
def cum(df, lob, col):
    out = {}
    for _, r in df[df.line_of_business_code == lob].iterrows():
        out.setdefault(int(r.accident_year), {})[int(r.development_lag)] = float(r[col])
    return out


def a2a(tri, max_lag):
    f = {}
    for k in range(max_lag):
        num = sum(row[k+1] for row in tri.values() if k in row and k+1 in row)
        den = sum(row[k] for row in tri.values() if k in row and k+1 in row)
        f[k] = num/den if den else 1.0
    return f


def cdf(f, frm, max_lag, tail=1.0):
    x = tail
    for k in range(frm, max_lag):
        x *= f.get(k, 1.0)
    return x


def diag(tri):
    return {ay: (max(r), r[max(r)]) for ay, r in tri.items()}


def mack_se(tri, f, max_lag):
    sig2 = {}
    for k in range(max_lag):
        pairs = [(r[k], r[k+1]) for r in tri.values() if k in r and k+1 in r]
        if len(pairs) <= 1:
            sig2[k] = 0.0; continue
        fk = sum(b for _, b in pairs)/sum(a for a, _ in pairs)
        sig2[k] = sum(a*((b/a)-fk)**2 for a, b in pairs)/(len(pairs)-1)
    d = diag(tri); se = {}
    for ay, (lag, cval) in d.items():
        var = 0.0; c = cval
        for k in range(lag, max_lag):
            fk = f.get(k, 1.0)
            var = (fk**2)*var + c*sig2.get(k, 0.0); c *= fk
        se[ay] = float(np.sqrt(max(var, 0.0)))
    return se


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="DEV")
    ap.add_argument("--warehouse-id", default="a3b61648ea4809e3")
    args = ap.parse_args()
    w = WorkspaceClient(profile=args.profile); wid = args.warehouse_id
    now = datetime.utcnow().isoformat()

    tri = read_df(w, wid, f"SELECT * FROM {FQ}.loss_development")
    for c in ["accident_year", "development_lag"]:
        tri[c] = tri[c].astype(int)
    for c in ["cumulative_paid", "cumulative_incurred", "incremental_paid", "incremental_incurred"]:
        tri[c] = tri[c].astype(float)
    lobs = sorted(tri.line_of_business_code.unique())
    print(f"Triangle: {len(tri)} rows, LOBs {lobs}")

    est, cf, ave = [], [], []
    for lob in lobs:
        pt = cum(tri, lob, "cumulative_paid"); it = cum(tri, lob, "cumulative_incurred")
        max_lag = max(max(r) for r in pt.values())
        f = a2a(pt, max_lag); dp = diag(pt); di = diag(it); se = mack_se(pt, f, max_lag)
        for ay in sorted(pt):
            lag, paid = dp[ay]; _, inc = di.get(ay, (lag, paid))
            case = max(inc - paid, 0.0)
            prem = (inc or paid) / APRIORI_LR; apri = prem * APRIORI_LR
            c = cdf(f, lag, max_lag)
            cl = paid * c
            pct_unpaid = 1.0 - (1.0/c if c else 1.0)
            bf = paid + apri*pct_unpaid
            for method, ult, serr in [("CHAIN_LADDER", cl, None), ("BORNHUETTER_FERGUSON", bf, None),
                                       ("EXPECTED_LOSS_RATIO", apri, None), ("MACK", cl, se.get(ay, 0.0))]:
                ult = max(ult, paid + case)  # never below incurred
                est.append(dict(reserve_estimate_id=f"RES-2026-{lob[:4]}-{ay}-{method[:2]}",
                    valuation_date=VAL_DATE, accident_year=ay, line_of_business_code=lob,
                    reserving_method_code=method, methodology_id=f"METH-{method}",
                    selection_id=("SEL-2026Q4-PROP-ELECTED" if lob == "COMMERCIAL_PROPERTY" else None),
                    currency_code="GBP", paid_to_date=round(paid, 2), case_reserves=round(case, 2),
                    ultimate_loss=round(ult, 2), ibnr=round(max(ult-paid-case, 0.0), 2),
                    outstanding=round(ult-paid, 2),
                    ultimate_std_error=(round(serr, 2) if serr is not None else None),
                    expert_judgement_applied=0.0, source_system_code="RESERVING_ENGINE"))
            # cashflow (chain-ladder runoff)
            cc = paid
            for k in range(lag, max_lag):
                nxt = cc*f.get(k, 1.0); incp = nxt-cc
                if incp > 0.01:
                    cf.append(dict(cashflow_id=f"CF-2026-{lob[:4]}-{ay}-{k+1}",
                        reserve_estimate_id=f"RES-2026-{lob[:4]}-{ay}-CH",
                        development_period=(k+1-lag), expected_payment=round(incp, 2), currency_code="GBP"))
                cc = nxt
            # AvE latest step
            lags = sorted(pt[ay])
            if len(lags) >= 2:
                last, prev = lags[-1], lags[-2]
                actual = pt[ay][last]-pt[ay][prev]; expected = pt[ay][prev]*(f.get(prev, 1.0)-1.0)
                var = actual-expected; serr2 = abs(expected)*0.15 or 1.0
                ave.append(dict(ave_id=f"AVE-2026-{lob[:4]}-{ay}", validation_period="2026",
                    reserving_method_code="CHAIN_LADDER", line_of_business_code=lob, accident_year=ay,
                    expected_emergence=round(expected, 2), actual_emergence=round(actual, 2),
                    variance=round(var, 2), standardised_residual=round(var/serr2, 4),
                    currency_code="GBP", within_tolerance=bool(abs(var/serr2) <= 2.5)))

    n = overwrite(w, wid, "reserve_estimate",
        ["reserve_estimate_id","valuation_date","accident_year","line_of_business_code",
         "reserving_method_code","methodology_id","selection_id","currency_code","paid_to_date",
         "case_reserves","ultimate_loss","ibnr","outstanding","ultimate_std_error",
         "expert_judgement_applied","source_system_code"], est)
    print(f"reserve_estimate: {n} rows")
    n = overwrite(w, wid, "reserve_cashflow_pattern",
        ["cashflow_id","reserve_estimate_id","development_period","expected_payment","currency_code"], cf)
    print(f"reserve_cashflow_pattern: {n} rows")
    n = overwrite(w, wid, "actual_vs_expected",
        ["ave_id","validation_period","reserving_method_code","line_of_business_code","accident_year",
         "expected_emergence","actual_emergence","variance","standardised_residual","currency_code",
         "within_tolerance"], ave)
    print(f"actual_vs_expected: {n} rows")

    # governance seeds (methodology registry, judgements, selected patterns)
    methods = [("CHAIN_LADDER", False, "Volume-weighted age-to-age factors to ultimate; standard for mature lines."),
               ("BORNHUETTER_FERGUSON", False, "Blends chain-ladder with an a-priori loss ratio; stable for immature years."),
               ("EXPECTED_LOSS_RATIO", False, "Pure a-priori loss ratio times premium; for the greenest years."),
               ("MACK", True, "Distribution-free stochastic chain-ladder; standard error around the ultimate."),
               ("GLM", True, "Over-dispersed Poisson GLM on incrementals; bootstrap for a full distribution."),
               ("PEER_COMPARISON", False, "Benchmarks the selected pattern against an external / peer pattern.")]
    meth_rows = [dict(methodology_id=f"METH-{m}", reserving_method_code=m,
                      uc_model_name=f"{CAT}.{SCH}.method_{m.lower()}", model_version=1, alias="production",
                      produces_distribution=dist, summary=s, owner_role="Chief Actuary", registered_at=now)
                 for m, dist, s in methods]
    overwrite(w, wid, "reserving_methodology",
        ["methodology_id","reserving_method_code","uc_model_name","model_version","alias",
         "produces_distribution","summary","owner_role","registered_at"], meth_rows)
    print(f"reserving_methodology: {len(meth_rows)} rows")

    # empirical factors for the property line (for the selection seeds)
    pt = cum(tri, "COMMERCIAL_PROPERTY", "cumulative_paid")
    ml = max(max(r) for r in pt.values()); fp = a2a(pt, ml)
    emp = [round(fp[k], 4) for k in range(ml)]
    judgements = [dict(judgement_id="EJ-2026Q4-001", quarter="2026-Q4",
        line_of_business_code="COMMERCIAL_PROPERTY", accident_year=2023, category_code="METHODOLOGY_JUDGEMENT",
        magnitude=-620000.00, currency_code="GBP",
        rationale=("AY2023 12-24m development distorted by a single late-reported large loss (CLM-2023-ANOMALY, "
                   "GBP 1.05m). Empirical volume-weighted factor spikes vs the stable prior pattern; held the prior "
                   "selection for that step and reserved the large loss individually."),
        linked_qrt_cells=json.dumps(["S.19.01.R0100.C0100","S.19.01.R0100.C0110"]),
        required_approval_role_code="SENIOR_ACTUARY", status_code="APPROVED", prior_judgement_id=None,
        author="a.reserving.analyst", created_at=now, approver="senior.reserving.actuary", approved_at=now),
        dict(judgement_id="EJ-2026Q4-002", quarter="2026-Q4", line_of_business_code="GENERAL_LIABILITY",
        accident_year=None, category_code="TAIL_EXTENSION", magnitude=310000.00, currency_code="GBP",
        rationale=("Extended the GL tail beyond the observed triangle to reflect long-tail bodily-injury development "
                   "consistent with market benchmarks; the mechanical triangle truncates too early."),
        linked_qrt_cells=json.dumps(["S.19.01.R0100.C0140"]), required_approval_role_code="SENIOR_ACTUARY",
        status_code="APPROVED", prior_judgement_id=None, author="a.reserving.analyst", created_at=now,
        approver="senior.reserving.actuary", approved_at=now)]
    overwrite(w, wid, "expert_judgement",
        ["judgement_id","quarter","line_of_business_code","accident_year","category_code","magnitude",
         "currency_code","rationale","linked_qrt_cells","required_approval_role_code","status_code",
         "prior_judgement_id","author","created_at","approver","approved_at"], judgements)
    print(f"expert_judgement: {len(judgements)} rows")

    prior_f = json.dumps([1.667, 1.20, 1.08, 1.05, 1.02, 1.01])
    sel = [dict(selection_id="SEL-2026Q3-PROP-PRIOR", valuation_date="2026-09-30", accident_year=None,
        line_of_business_code="COMMERCIAL_PROPERTY", currency_code="GBP", source_code="PRIOR_SELECTION",
        averaging_method_code=None, last_n_years=None, development_factors=prior_f, tail_factor=1.01,
        prior_selection_id=None, status_code="APPROVED",
        rationale="Prior quarter's approved pattern, carried forward as the comparison baseline.",
        selected_by="senior.reserving.actuary", selected_at=now, approved_by="chief.actuary", approved_at=now),
        dict(selection_id="SEL-2026Q4-PROP-EMPIRICAL", valuation_date="2026-12-31", accident_year=None,
        line_of_business_code="COMMERCIAL_PROPERTY", currency_code="GBP", source_code="DATABRICKS_EMPIRICAL",
        averaging_method_code="VOLUME_WEIGHTED", last_n_years=None, development_factors=json.dumps(emp),
        tail_factor=1.01, prior_selection_id="SEL-2026Q3-PROP-PRIOR", status_code="DRAFT", rationale=None,
        selected_by="a.reserving.analyst", selected_at=now, approved_by=None, approved_at=None),
        dict(selection_id="SEL-2026Q4-PROP-ELECTED", valuation_date="2026-12-31", accident_year=None,
        line_of_business_code="COMMERCIAL_PROPERTY", currency_code="GBP", source_code="PRIOR_SELECTION",
        averaging_method_code=None, last_n_years=None, development_factors=prior_f, tail_factor=1.01,
        prior_selection_id="SEL-2026Q4-PROP-EMPIRICAL", status_code="APPROVED",
        rationale=("Overrode the empirical 12-24m factor (distorted by the CLM-2023-ANOMALY late-reported large loss) "
                   "and held the prior 1.667x pattern; the large loss is reserved individually."),
        selected_by="senior.reserving.actuary", selected_at=now, approved_by="chief.actuary", approved_at=now),
        # A ResQ-SOURCED selection (General Liability): the external-engine talk track made real —
        # same table, source_code=RESQ, same governance as a native pick.
        dict(selection_id="SEL-2026Q3-GL-PRIOR", valuation_date="2026-09-30", accident_year=None,
        line_of_business_code="GENERAL_LIABILITY", currency_code="GBP", source_code="PRIOR_SELECTION",
        averaging_method_code=None, last_n_years=None,
        development_factors=json.dumps([1.90, 1.52, 1.26, 1.12, 1.06, 1.03]), tail_factor=1.02,
        prior_selection_id=None, status_code="APPROVED",
        rationale="Prior quarter's approved GL pattern, carried forward as the comparison baseline.",
        selected_by="senior.reserving.actuary", selected_at=now, approved_by="chief.actuary", approved_at=now),
        dict(selection_id="SEL-2026Q4-GL-RESQ", valuation_date="2026-12-31", accident_year=None,
        line_of_business_code="GENERAL_LIABILITY", currency_code="GBP", source_code="RESQ",
        averaging_method_code=None, last_n_years=None,
        development_factors=json.dumps([1.85, 1.50, 1.25, 1.12, 1.06, 1.03]), tail_factor=1.02,
        prior_selection_id="SEL-2026Q3-GL-PRIOR", status_code="APPROVED",
        rationale=("Selected in LCP ResQ by the reserving team; Databricks prepared the governed triangle, "
                   "orchestrated the ResQ run, and read the selected pattern back. Same audit trail as a native pick."),
        selected_by="resq.reserving.team", selected_at=now, approved_by="chief.actuary", approved_at=now)]
    overwrite(w, wid, "selected_development_pattern",
        ["selection_id","valuation_date","accident_year","line_of_business_code","currency_code","source_code",
         "averaging_method_code","last_n_years","development_factors","tail_factor","prior_selection_id",
         "status_code","rationale","selected_by","selected_at","approved_by","approved_at"], sel)
    print(f"selected_development_pattern: {len(sel)} rows")

    # reconciliation gate
    bad = read_df(w, wid, f"""SELECT COUNT(*) n FROM {FQ}.reserve_estimate
        WHERE abs((paid_to_date + case_reserves + ibnr) - ultimate_loss) >= 1.0""")
    assert int(bad.iloc[0]["n"]) == 0, "reconciliation FAILED"
    print("Reconciliation gate PASSED: paid + case + IBNR = ultimate for every estimate.")


if __name__ == "__main__":
    main()
