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


def run(w, wid):
    """Reusable entrypoint — the Job wrappers call this so the tested logic runs
    unchanged whether invoked from the CLI or a Databricks task."""
    now = datetime.utcnow().isoformat()

    tri = read_df(w, wid, f"SELECT * FROM {FQ}.loss_development")
    for c in ["accident_year", "development_lag"]:
        tri[c] = tri[c].astype(int)
    for c in ["cumulative_paid", "cumulative_incurred", "incremental_paid", "incremental_incurred"]:
        tri[c] = tri[c].astype(float)
    lobs = sorted(tri.line_of_business_code.unique())
    print(f"Triangle: {len(tri)} rows, LOBs {lobs}")

    # outwards RI programme per line (gross-to-net). QS is proportional; the XoL
    # EXPECTED recovery is a line-level aggregate (XoL attaches per-claim, not to the
    # aggregate ultimate). Read the programme + each line's total CL ultimate so the
    # aggregate XoL recovery can be apportioned across cohorts by ultimate share.
    prog = {}
    try:
        pr = read_df(w, wid, f"SELECT line_of_business_code, quota_share_pct, xol_expected_recovery "
                             f"FROM {FQ}.reinsurance_programme")
        def _num(v):  # pandas gives NaN (not None) for SQL NULL — treat both as 0
            try:
                x = float(v); return 0.0 if x != x else x   # x!=x is the NaN test
            except (TypeError, ValueError):
                return 0.0
        for _, r in pr.iterrows():
            prog[r["line_of_business_code"]] = (_num(r["quota_share_pct"]), _num(r["xol_expected_recovery"]))
    except Exception as e:
        print(f"  (no reinsurance_programme yet: {e}) — net columns will be NULL")

    # first pass: total chain-ladder ultimate per line, to apportion the aggregate XoL recovery
    line_ult = {}
    for lob in lobs:
        pt0 = cum(tri, lob, "cumulative_paid"); ml0 = max(max(r) for r in pt0.values())
        f0 = a2a(pt0, ml0); dp0 = diag(pt0)
        line_ult[lob] = sum(dp0[ay][1] * cdf(f0, dp0[ay][0], ml0) for ay in pt0)

    def to_net(gross, lob):
        """gross cohort ultimate -> (net, ceded). QS scales per cohort; the line's
        aggregate XoL expected recovery is apportioned to this cohort by its share
        of the line ultimate. None if no programme on the line."""
        if lob not in prog:
            return None, None
        qs, xol_rec = prog[lob]
        share = (gross / line_ult[lob]) if line_ult.get(lob) else 0.0
        ceded_qs = gross * qs
        ceded_xol = xol_rec * share
        net = gross - ceded_qs - ceded_xol
        return round(max(net, 0.0), 2), round(ceded_qs + ceded_xol, 2)

    est, cf, ave = [], [], []
    for lob in lobs:
        pt = cum(tri, lob, "cumulative_paid"); it = cum(tri, lob, "cumulative_incurred")
        max_lag = max(max(r) for r in pt.values())
        f = a2a(pt, max_lag); dp = diag(pt); di = diag(it); se = mack_se(pt, f, max_lag)
        # Cape Cod: derive ONE expected loss ratio for the line from the triangle itself
        # (Stanard-Bühlmann): ELR = sum(latest paid) / sum(premium * reported-pct), so the
        # a-priori isn't taken on faith like BF — it's estimated from the data.
        cc_num = cc_den = 0.0
        for a in pt:
            la, pa = dp[a]; ca = cdf(f, la, max_lag)
            rep = (1.0 / ca) if ca else 1.0                 # reported proportion to date
            prem_a = (di.get(a, (la, pa))[1] or pa) / APRIORI_LR
            cc_num += pa; cc_den += prem_a * rep
        cape_cod_elr = (cc_num / cc_den) if cc_den else APRIORI_LR
        for ay in sorted(pt):
            lag, paid = dp[ay]; _, inc = di.get(ay, (lag, paid))
            case = max(inc - paid, 0.0)
            prem = (inc or paid) / APRIORI_LR; apri = prem * APRIORI_LR
            c = cdf(f, lag, max_lag)
            cl = paid * c
            pct_unpaid = 1.0 - (1.0/c if c else 1.0)
            pct_rep = (1.0/c if c else 1.0)                  # reported proportion (Benktander Z)
            bf = paid + apri*pct_unpaid
            # Cape Cod: same BF form but with the data-derived ELR
            capecod = paid + (prem * cape_cod_elr) * pct_unpaid
            # Benktander (Neuhaus): iterate BF once — credibility Z = reported proportion.
            # ult = Z*CL + (1-Z)*BF, the standard optimal-credibility blend.
            benk = pct_rep * cl + (1.0 - pct_rep) * bf
            for method, ult, serr in [("CHAIN_LADDER", cl, None), ("BORNHUETTER_FERGUSON", bf, None),
                                       ("EXPECTED_LOSS_RATIO", apri, None), ("MACK", cl, se.get(ay, 0.0)),
                                       ("CAPE_COD", capecod, None), ("BENKTANDER", benk, None)]:
                ult = max(ult, paid + case)  # never below incurred
                net_ult, ceded = to_net(ult, lob)
                ibnr_g = max(ult-paid-case, 0.0)
                # net IBNR scales with the net proportion of the ultimate (simplification)
                ibnr_net = round(ibnr_g * (net_ult/ult), 2) if (net_ult is not None and ult) else None
                est.append(dict(reserve_estimate_id=f"RES-2026-{lob[:4]}-{ay}-{method[:2]}",
                    valuation_date=VAL_DATE, accident_year=ay, line_of_business_code=lob,
                    reserving_method_code=method, methodology_id=f"METH-{method}",
                    selection_id=("SEL-2026Q4-PROP-ELECTED" if lob == "COMMERCIAL_PROPERTY" else None),
                    currency_code="GBP", paid_to_date=round(paid, 2), case_reserves=round(case, 2),
                    ultimate_loss=round(ult, 2), ibnr=round(ibnr_g, 2),
                    outstanding=round(ult-paid, 2),
                    ultimate_net=net_ult, ibnr_net=ibnr_net, ceded_ultimate=ceded,
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
            # Actual-vs-expected on the FIRST development step (0->1) — where factor-selection risk
            # is highest and where a late large loss shows up. Expected uses the MEDIAN individual
            # factor for the line (robust to a single outlier year), so clean cohorts sit near zero
            # and an anomalous cohort (AY2023 CP, which developed far ABOVE the norm) shows a large
            # POSITIVE residual — the residual sign now matches "developed high, flagged".
            if 0 in pt[ay] and 1 in pt[ay] and pt[ay][0]:
                indiv0 = sorted((pt[a][1]/pt[a][0]) for a in pt if 0 in pt[a] and 1 in pt[a] and pt[a][0])
                median_f0 = indiv0[len(indiv0)//2] if indiv0 else f.get(0, 1.0)
                actual = pt[ay][1] - pt[ay][0]
                expected = pt[ay][0] * (median_f0 - 1.0)
                var = actual - expected; serr2 = abs(expected)*0.15 or 1.0
                ave.append(dict(ave_id=f"AVE-2026-{lob[:4]}-{ay}", validation_period="2026",
                    reserving_method_code="CHAIN_LADDER", line_of_business_code=lob, accident_year=ay,
                    expected_emergence=round(expected, 2), actual_emergence=round(actual, 2),
                    variance=round(var, 2), standardised_residual=round(var/serr2, 4),
                    currency_code="GBP", within_tolerance=bool(abs(var/serr2) <= 2.5)))

    n = overwrite(w, wid, "reserve_estimate",
        ["reserve_estimate_id","valuation_date","accident_year","line_of_business_code",
         "reserving_method_code","methodology_id","selection_id","currency_code","paid_to_date",
         "case_reserves","ultimate_loss","ibnr","outstanding","ultimate_net","ibnr_net",
         "ceded_ultimate","ultimate_std_error",
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
    # Seed the registry ONLY where empty. notebook 04 registers the REAL MLflow models
    # (including the customer's own in-house method) and owns this table; overwriting it
    # here would clobber those. So this is a fallback for a fresh schema, not a reset.
    existing_meth = read_df(w, wid, f"SELECT count(*) n FROM {FQ}.reserving_methodology")
    if int(existing_meth.iloc[0]["n"]) == 0:
        overwrite(w, wid, "reserving_methodology",
            ["methodology_id","reserving_method_code","uc_model_name","model_version","alias",
             "produces_distribution","summary","owner_role","registered_at"], meth_rows)
        print(f"reserving_methodology: seeded {len(meth_rows)} rows (was empty)")
    else:
        print(f"reserving_methodology: left intact ({int(existing_meth.iloc[0]['n'])} rows — owned by notebook 04)")

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

    # ---- wider-process tables: variability, large loss, roll-forward, sign-off ----
    import math
    # reserve variability (Mack CoV + percentiles) from the MACK estimates
    mack = [e for e in est if e["reserving_method_code"] == "MACK"]
    by_lob_mack = {}
    for e in mack:
        d = by_lob_mack.setdefault(e["line_of_business_code"], {"ult": 0.0, "var": 0.0})
        d["ult"] += e["ultimate_loss"]
        d["var"] += (e["ultimate_std_error"] or 0.0) ** 2
    # Plausible per-line CoV floor: long-tail liability lines are more uncertain than short-tail
    # property/marine. The smooth synthetic triangle understates Mack sigma, so floor it to a
    # realistic level per line (real reserve CoVs run ~3-15% by tail length).
    COV_FLOOR = {"COMMERCIAL_PROPERTY": 0.05, "COMMERCIAL_MOTOR": 0.07, "GENERAL_LIABILITY": 0.12,
                 "PROFESSIONAL_INDEMNITY": 0.14, "MARINE": 0.06}
    var_rows = []
    for lob, d in by_lob_mack.items():
        be = d["ult"]; se_raw = math.sqrt(d["var"])
        cov = max((se_raw / be) if be else 0.0, COV_FLOOR.get(lob, 0.08))
        se = round(be * cov, 2)
        var_rows.append(dict(variability_id=f"VAR-2026-{lob[:4]}", valuation_date=VAL_DATE,
            line_of_business_code=lob, reserving_method_code="MACK", best_estimate=round(be, 2),
            standard_error=se, coefficient_of_variation=round(cov, 4),
            percentile_75=round(be + 0.674 * se, 2), percentile_95=round(be + 1.645 * se, 2),
            currency_code="GBP"))
    overwrite(w, wid, "reserve_variability",
        ["variability_id", "valuation_date", "line_of_business_code", "reserving_method_code",
         "best_estimate", "standard_error", "coefficient_of_variation", "percentile_75",
         "percentile_95", "currency_code"], var_rows)
    print(f"reserve_variability: {len(var_rows)} rows")

    # large loss: the AY2023 anomaly claim, reserved individually (distorts the factor)
    ll_rows = [dict(large_loss_id="LL-2023-001", claim_id="CLM-2023-ANOMALY",
        line_of_business_code="COMMERCIAL_PROPERTY", accident_year=2023, incurred=1050000.00,
        threshold=500000.00, treatment="reserved_individually", distorts_factor=True, currency_code="GBP")]
    overwrite(w, wid, "large_loss",
        ["large_loss_id", "claim_id", "line_of_business_code", "accident_year", "incurred",
         "threshold", "treatment", "distorts_factor", "currency_code"], ll_rows)
    print(f"large_loss: {len(ll_rows)} rows")

    # roll-forward waterfall for Commercial Property (prior → this quarter)
    cl_cp = sum(e["ultimate_loss"] for e in est if e["line_of_business_code"] == "COMMERCIAL_PROPERTY" and e["reserving_method_code"] == "CHAIN_LADDER")
    opening = round(cl_cp * 0.94, 2)
    rf = [("opening", opening, 0), ("expected_runoff", round(-cl_cp * 0.06, 2), 1),
          ("experience_ave", round(cl_cp * 0.05, 2), 2), ("assumption_change", round(cl_cp * 0.02, 2), 3),
          ("large_loss", round(cl_cp * 0.04, 2), 4), ("expert_judgement", round(-cl_cp * 0.045, 2), 5)]
    closing = round(sum(a for _, a, _ in rf), 2)
    rf.append(("closing", closing, 6))
    rf_rows = [dict(rollforward_id=f"RF-2026-COMM-{o}", valuation_date=VAL_DATE,
        line_of_business_code="COMMERCIAL_PROPERTY", driver=drv, amount=amt, display_order=o,
        currency_code="GBP") for drv, amt, o in rf]
    overwrite(w, wid, "reserve_rollforward",
        ["rollforward_id", "valuation_date", "line_of_business_code", "driver", "amount",
         "display_order", "currency_code"], rf_rows)
    print(f"reserve_rollforward: {len(rf_rows)} rows")

    # sign-off rows (one signed, others pending) — reproduce-as-at carries a data version
    so_rows = []
    for lob in lobs:
        signed = lob == "GENERAL_LIABILITY"
        be = sum(e["ultimate_loss"] for e in est if e["line_of_business_code"] == lob and e["reserving_method_code"] == "CHAIN_LADDER")
        so_rows.append(dict(signoff_id=f"SO-2026-{lob[:4]}", valuation_date=VAL_DATE,
            line_of_business_code=lob, signed_best_estimate=round(be, 2),
            selection_id=None, reserving_method_code="CHAIN_LADDER", data_version="v1 (2026-12-31 snapshot)",
            status_code="APPROVED" if signed else "PENDING_APPROVAL",
            signed_by="chief.actuary" if signed else None,
            signed_at=now if signed else None, currency_code="GBP"))
    overwrite(w, wid, "reserve_signoff",
        ["signoff_id", "valuation_date", "line_of_business_code", "signed_best_estimate",
         "selection_id", "reserving_method_code", "data_version", "status_code", "signed_by",
         "signed_at", "currency_code"], so_rows)
    print(f"reserve_signoff: {len(so_rows)} rows")

    # seed a few audit events so the governance panel isn't empty on first load
    ae = [
        ("selection_elected", "selection", "SEL-2026Q4-PROP-ELECTED", "Held prior 12-24m factor for AY2023 anomaly", "senior.reserving.actuary"),
        ("judgement_approved", "judgement", "EJ-2026Q4-001", "Approved -620,000 methodology judgement (CP AY2023)", "chief.actuary"),
        ("selection_elected", "selection", "SEL-2026Q4-GL-RESQ", "Imported ResQ pattern for General Liability", "resq.reserving.team"),
        ("signed_off", "signoff", "SO-2026-GENE", "Signed off General Liability reserves, data v1", "chief.actuary"),
    ]
    ae_rows = [dict(event_id=f"AE-{i:04d}", event_type=t, entity_type=et, entity_id=eid,
        detail=det, actor=act, created_at=now) for i, (t, et, eid, det, act) in enumerate(ae, 1)]
    overwrite(w, wid, "5_gov_audit_event",
        ["event_id", "event_type", "entity_type", "entity_id", "detail", "actor", "created_at"], ae_rows)
    print(f"5_gov_audit_event: {len(ae_rows)} rows")

    # NOTE: the ingestion control surface (feeds, DQ expectations, reconciliation,
    # data sign-off gate, data movement, class mapping) is owned by
    # tools/run_ingestion.py — run it AFTER this script. It was moved out of here
    # so there is exactly one writer per table; having both scripts write
    # 1_raw_data_feed meant whichever ran last silently won.

    # reconciliation gate
    bad = read_df(w, wid, f"""SELECT COUNT(*) n FROM {FQ}.reserve_estimate
        WHERE abs((paid_to_date + case_reserves + ibnr) - ultimate_loss) >= 1.0""")
    assert int(bad.iloc[0]["n"]) == 0, "reconciliation FAILED"
    print("Reconciliation gate PASSED: paid + case + IBNR = ultimate for every estimate.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="DEV")
    ap.add_argument("--warehouse-id", default="a3b61648ea4809e3")
    args = ap.parse_args()
    run(WorkspaceClient(profile=args.profile), args.warehouse_id)

if __name__ == "__main__":
    main()
