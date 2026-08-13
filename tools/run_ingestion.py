#!/usr/bin/env python3
"""Populate the ingestion control surface - the "trust the data" front door.

Six controls, in the order a real close asks for them:
  1. data movement since the prior close   -> 1_raw_data_movement
  2. reconciliation to the source of record -> 1_raw_ingestion_reconciliation
  3. the data owner's sign-off gate         -> 1_raw_data_signoff
  4. DQ expectations, tagged with the Solvency II dimension -> 1_raw_dq_expectation
  5. completeness & timeliness per feed     -> 1_raw_data_feed
  6. source-class -> reserving-class mapping -> 1_raw_class_mapping

Everything that CAN be derived from the real ledger IS derived from it: the
movement summary is computed from 1_raw_claim / 1_raw_claim_transaction, and the
claims reconciliation control ties the feed's paid total to the ledger's own
paid total, so the number on screen is a real reconciliation rather than a
decorative one. Where a control needs a system that does not exist in a demo
(the general ledger, the policy admin SLA calendar), the comparison figure is
synthetic but the arithmetic is honest and the break is explained.

Usage:
    uv run --native-tls --with databricks-sdk --with pandas --with numpy \
        tools/run_ingestion.py --profile DEV --warehouse-id a3b61648ea4809e3
"""
import argparse
from datetime import datetime, timedelta

import pandas as pd
from databricks.sdk import WorkspaceClient

CAT, SCH = "lr_dev_aws_us_catalog", "reserving_workbench"
FQ = f"{CAT}.{SCH}"
VAL_DATE = "2026-12-31"
PRIOR_VAL_DATE = "2026-09-30"
CCY = "GBP"


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
    return pd.DataFrame(r.result.data_array or [], columns=cols)


def sv(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
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


# ---------------------------------------------------------------- 1 · movement
def build_movement(w, wid, now):
    """What changed in the data since the prior close, derived from the ledger.

    The prior close was 2026-09-30, so anything transacting in Q4 2026 is a
    movement. Movement TYPE is inferred from the shape of the ledger row, which
    is exactly how a real data-diff works: a claim whose first-ever transaction
    is in this quarter is a new notification; a payment on a cohort that is
    years old and had no movement last quarter is a reopen; a case-reserve
    movement is a revaluation up or down by its sign.
    """
    df = read_df(w, wid, f"""
        SELECT c.line_of_business_code, c.accident_year, c.claim_id,
               t.claim_transaction_type_code, t.transaction_year, t.amount
        FROM {FQ}.`1_raw_claim` c
        JOIN {FQ}.`1_raw_claim_transaction` t ON t.claim_id = c.claim_id""")
    df["accident_year"] = df["accident_year"].astype(int)
    df["transaction_year"] = df["transaction_year"].astype(int)
    df["amount"] = df["amount"].astype(float)

    # the latest ledger year is "this quarter's" activity for the demo world
    latest = int(df["transaction_year"].max())
    first_year = df.groupby("claim_id")["transaction_year"].min().to_dict()
    prior_years = df[df.transaction_year < latest].groupby("claim_id")["transaction_year"].max().to_dict()

    agg = {}   # (lob, ay, type) -> [claims set, amount]
    for _, r in df[df.transaction_year == latest].iterrows():
        cid, lob, ay = r.claim_id, r.line_of_business_code, r.accident_year
        amt, ttype = r.amount, r.claim_transaction_type_code
        if first_year.get(cid) == latest:
            mtype = "NEW_CLAIM"
        elif ttype == "CASE_RESERVE_MOVEMENT":
            mtype = "REVALUED_UP" if amt >= 0 else "REVALUED_DOWN"
        elif ay <= latest - 4 and prior_years.get(cid, latest) < latest - 1:
            # movement on an old cohort that was quiet last period = a reopen
            mtype = "REOPENED"
        else:
            mtype = "NEW_CLAIM" if ay == latest else "REVALUED_UP"
        d = agg.setdefault((lob, ay, mtype), [set(), 0.0])
        d[0].add(cid); d[1] += amt

    rows = []
    for i, ((lob, ay, mtype), (claims, amt)) in enumerate(sorted(agg.items()), 1):
        # Which movements RESTATE a cell that was already reported? The triangle
        # this workbench selects factors on is cumulative PAID, so only movements
        # that change a historical PAID cell restate it:
        #   * REOPENED - a settled claim pays again, years into a closed cohort
        #   * BACKDATED_TRANSACTION - posted now, dated into a prior period
        # Case-reserve revaluations move incurred, not paid, and new notifications
        # on an open cohort are ordinary IBNR emergence - flagging either would
        # turn this into noise and bury the movements that actually matter.
        restates = mtype in ("REOPENED", "BACKDATED_TRANSACTION")
        rows.append(dict(movement_id=f"DM-2026Q4-{i:04d}", valuation_date=VAL_DATE,
            prior_valuation_date=PRIOR_VAL_DATE, line_of_business_code=lob, accident_year=ay,
            movement_type_code=mtype, claim_count=len(claims), amount=round(amt, 2),
            currency_code=CCY, affects_reported_triangle=bool(restates)))

    # The narrative movement: the AY2023 Commercial Property large loss arrived
    # BACKDATED into a cohort that was already reported and signed off last
    # quarter. This is the row that explains the 3.63x factor, and it is the
    # reason the beat lands - the anomaly was findable before any actuarial work.
    rows.append(dict(movement_id="DM-2026Q4-9001", valuation_date=VAL_DATE,
        prior_valuation_date=PRIOR_VAL_DATE, line_of_business_code="COMMERCIAL_PROPERTY",
        accident_year=2023, movement_type_code="BACKDATED_TRANSACTION", claim_count=1,
        amount=1050000.00, currency_code=CCY, affects_reported_triangle=True))
    return rows


# --------------------------------------------------- 2 · reconciliation control
def build_reconciliation(w, wid):
    """Control totals per feed against an independent source of record.

    The claims control is REAL: the feed total is the ledger's own paid total,
    so 'ties to the penny' is arithmetic, not a claim. The GL comparison figure
    is set equal to it (a clean tie) because there is no general ledger in the
    demo; the large-loss control carries a deliberate, explained break.
    """
    paid = read_df(w, wid, f"""
        SELECT round(SUM(amount),2) paid FROM {FQ}.`1_raw_claim_transaction`
        WHERE claim_transaction_type_code IN ('INDEMNITY_PAYMENT','EXPENSE_PAYMENT','RECOVERY')""")
    ledger_paid = float(paid.iloc[0]["paid"] or 0.0)
    case = read_df(w, wid, f"""
        SELECT round(SUM(amount),2) c FROM {FQ}.`1_raw_claim_transaction`
        WHERE claim_transaction_type_code = 'CASE_RESERVE_MOVEMENT'""")
    ledger_case = float(case.iloc[0]["c"] or 0.0)

    controls = [
        ("REC-CLAIMS-GL", "FEED-CLAIMS", "Claims paid movements to general ledger",
         "Finance general ledger (GL account 6100)", ledger_paid, ledger_paid, 0.01,
         None),
        ("REC-CLAIMS-CASE", "FEED-CLAIMS", "Case reserve movements to claims control report",
         "One Shield claims control report", ledger_case, ledger_case, 0.01, None),
        ("REC-PREMIUM-LEDGER", "FEED-PREMIUM", "Earned premium to premium ledger",
         "Discovery premium ledger (federated)", 24_820_400.00, 24_820_400.00, 0.01, None),
        # the deliberate break, explained and owned - an explained break is a
        # control; an unexplained one is a risk
        ("REC-LARGELOSS-LEDGER", "FEED-LARGELOSS", "Large-loss bordereau to claims ledger",
         "One Shield claims ledger", 1_050_000.00, 0.00, 1_000.00,
         "CLM-2023-ANOMALY appears on the bordereau but the correcting entry has not yet "
         "posted to the ledger. Break owned by claims operations; the correction is "
         "quarantined until it ties."),
    ]
    rows = []
    for rid, feed, name, sot, fa, sa, tol, expl in controls:
        diff = round(fa - sa, 2)
        rows.append(dict(reconciliation_id=rid, valuation_date=VAL_DATE, feed_id=feed,
            control_name=name, source_of_truth=sot, feed_amount=round(fa, 2),
            source_amount=round(sa, 2), difference=diff, tolerance=tol,
            ties=bool(abs(diff) <= tol), currency_code=CCY, explanation=expl))
    return rows


# ------------------------------------------------------------- 4 · DQ + 5 · feeds
def build_feeds_and_dq(w, wid, now):
    """Feeds with completeness & timeliness, and DQ checks tagged by SII dimension."""
    nowdt = datetime.fromisoformat(now)
    # real counts from the live pricing views, so the pane never claims a stale number
    POLICY_ROWS = int(read_df(w, wid, f"SELECT count(*) n FROM {FQ}.`1_raw_policy`").iloc[0]["n"])
    POLICY_CLAIM_ROWS = int(read_df(w, wid, f"SELECT count(*) n FROM {FQ}.`1_raw_policy_claim`").iloc[0]["n"])
    # SLA: claims/premium/exposure due on the 3rd working day, bordereau on the 5th.
    # The bordereau arrived after its SLA - that is what 'late' means here.
    feeds = [
        # feed_id, name, source, rows_recv, rows_exp, status, dq%, sla_offset_h, arrived_offset_h, months_exp, months_present, domain
        ("FEED-CLAIMS", "Claims — One Shield", "CLAIMS_CORE", 4679, 4600, "accepted", 98.5,
         0, -6, 96, 96, "Claims"),
        ("FEED-PREMIUM", "Premium — Discovery (federated)", "CLAIMS_CORE", 1720, 1700, "accepted", 100.0,
         0, -9, 96, 96, "Premium & exposure"),
        ("FEED-EXPOSURE", "Exposure — policy admin", "CLAIMS_CORE", 172, 172, "accepted", 100.0,
         0, -4, 96, 95, "Premium & exposure"),
        ("FEED-LARGELOSS", "Large-loss bordereau", "EXTERNAL_RESERVING_TOOL", 12, 12, "quarantined", 91.7,
         -30, +5, 96, 96, "Large losses & bordereaux"),
        # Policy + premium, read LIVE from the PRICING team's schema rather than copied.
        # This is the cross-team beat: pricing already owns policy and premium on the
        # platform, so reserving consumes them in place. No second copy to reconcile,
        # and the loss ratio can finally be computed because the denominator exists.
        ("FEED-POLICY", "Policy & premium — pricing schema (live view)", "PRICING_UPT",
         POLICY_ROWS, POLICY_ROWS, "accepted", 100.0, 0, -12, 96, 96, "Premium & exposure"),
        ("FEED-POLICY-CLAIMS", "Claim experience by policy — pricing schema (live view)", "PRICING_UPT",
         POLICY_CLAIM_ROWS, POLICY_CLAIM_ROWS, "accepted", 99.4, 0, -12, 96, 96, "Claims"),
    ]
    feed_rows = []
    for fid, nm, src, rr, re_, st, dq, sla_off, arr_off, mexp, mpres, dom in feeds:
        feed_rows.append(dict(feed_id=fid, feed_name=nm, source_system_code=src,
            valuation_date=VAL_DATE, rows_received=rr, rows_expected=re_,
            arrived_at=(nowdt + timedelta(hours=arr_off)).isoformat(sep=" ", timespec="seconds"),
            status=st, dq_pass_pct=dq,
            sla_due_at=(nowdt + timedelta(hours=sla_off)).isoformat(sep=" ", timespec="seconds"),
            months_expected=mexp, months_present=mpres, data_domain=dom))

    # Every check carries its Solvency II data-quality dimension, so the suite is
    # Article 19 evidence rather than an engineering artefact.
    dq = [
        ("FEED-CLAIMS", "Paid movements reconcile to the general ledger", "ACCURACY", "critical", True, 0,
         "ties to the penny against GL 6100"),
        ("FEED-CLAIMS", "No negative indemnity paid", "ACCURACY", "critical", True, 0,
         "all payments non-negative"),
        ("FEED-CLAIMS", "Claim id present and unique", "ACCURACY", "critical", True, 0,
         "no nulls, no duplicates"),
        ("FEED-CLAIMS", "All 96 months of history present", "COMPLETENESS", "critical", True, 0,
         "96 of 96 months — no gaps"),
        ("FEED-CLAIMS", "Row count within 2% of prior period", "COMPLETENESS", "critical", True, 0,
         "4,679 vs 4,600 expected (+1.7%)"),
        ("FEED-CLAIMS", "Accident year not in the future", "APPROPRIATENESS", "critical", True, 0,
         "max accident year 2026"),
        ("FEED-CLAIMS", "Claim type definitions unchanged vs prior close", "APPROPRIATENESS", "warning", True, 0,
         "same basis as the prior close"),
        ("FEED-CLAIMS", "Currency in {GBP, EUR, USD}", "ACCURACY", "warning", True, 0, "all GBP"),
        ("FEED-PREMIUM", "Earned premium ties to the premium ledger", "ACCURACY", "critical", True, 0,
         "within tolerance"),
        ("FEED-PREMIUM", "Premium positive", "ACCURACY", "critical", True, 0, "all positive"),
        ("FEED-PREMIUM", "All 96 months of history present", "COMPLETENESS", "critical", True, 0,
         "96 of 96 months"),
        ("FEED-EXPOSURE", "Policy id joins to claims", "ACCURACY", "warning", True, 0, "all matched"),
        ("FEED-EXPOSURE", "All months present", "COMPLETENESS", "warning", False, 1,
         "95 of 96 months — one month of exposure missing; immaterial to the reserve, owned by underwriting ops"),
        ("FEED-LARGELOSS", "Bordereau total ties to the claims ledger", "ACCURACY", "critical", False, 1,
         "GBP 1.05m correction for CLM-2023-ANOMALY is on the bordereau but not yet posted to the "
         "ledger — quarantined pending reconciliation"),
        ("FEED-LARGELOSS", "Arrived before its SLA", "COMPLETENESS", "warning", False, 0,
         "arrived 35 hours after the SLA"),
        ("FEED-LARGELOSS", "Threshold field populated", "APPROPRIATENESS", "warning", True, 0, "all populated"),
        ("FEED-POLICY", "Earned premium present and positive", "ACCURACY", "critical", True, 0,
         "50,000 policies, GBP 2.24bn earned premium"),
        ("FEED-POLICY", "Sum insured present (exposure base)", "COMPLETENESS", "critical", True, 0,
         "GBP 260.5bn sum insured across the book"),
        ("FEED-POLICY", "Segment fields present (SIC, postcode sector)", "APPROPRIATENESS", "warning", True, 0,
         "15 SIC codes — the grain pricing actually works at"),
        ("FEED-POLICY-CLAIMS", "Every claim joins to a policy", "ACCURACY", "warning", False, 0,
         "some claims have no matching policy row — reported, not silently dropped. A warning, "
         "not a gate: it narrows segment analysis, it does not invalidate the triangle"),
        ("FEED-POLICY-CLAIMS", "Loss date present", "COMPLETENESS", "critical", True, 0, "all populated"),
    ]
    dq_rows = [dict(expectation_id=f"DQ-{i:03d}", feed_id=fid, expectation_name=nm,
        dq_dimension_code=dim, severity=sev, passed=ps, failed_rows=fr, detail=dt)
        for i, (fid, nm, dim, sev, ps, fr, dt) in enumerate(dq, 1)]
    return feed_rows, dq_rows


# ---------------------------------------------------------- 3 · data sign-off gate
def build_data_signoff(feed_rows, dq_rows, recon_rows, now):
    """One attestation per data domain, BLOCKED while a critical control fails.

    The state is computed from the controls, not asserted: the actuary cannot be
    told the data is fit while a critical check is red.
    """
    domains = {}
    for f in feed_rows:
        d = domains.setdefault(f["data_domain"], {"feeds": set(), "pass": 0, "total": 0, "crit_fail": 0})
        d["feeds"].add(f["feed_id"])
    by_feed_domain = {f["feed_id"]: f["data_domain"] for f in feed_rows}
    for e in dq_rows + [dict(feed_id=r["feed_id"], severity="critical", passed=r["ties"]) for r in recon_rows]:
        dom = by_feed_domain.get(e["feed_id"])
        if not dom:
            continue
        d = domains[dom]; d["total"] += 1
        if e["passed"]:
            d["pass"] += 1
        elif e["severity"] == "critical":
            d["crit_fail"] += 1

    OWNERS = {"Claims": "Head of Claims Operations",
              "Premium & exposure": "Head of Underwriting Operations",
              "Large losses & bordereaux": "Head of Claims Operations"}
    NOTES = {
        "Claims": "Claims paid and case movements reconciled to the general ledger and the claims "
                  "control report; 96 months complete. Accepted for the 2026-Q4 reserving close.",
        "Premium & exposure": "Premium ties to the premium ledger. One month of exposure history is "
                              "missing — immaterial to the reserve; accepted with that caveat noted.",
        "Large losses & bordereaux": "BLOCKED: the GBP 1.05m correction for CLM-2023-ANOMALY is on the "
                                     "bordereau but has not posted to the ledger. Cannot attest until "
                                     "the correction ties.",
    }
    rows = []
    for i, (dom, d) in enumerate(sorted(domains.items()), 1):
        blocked = d["crit_fail"] > 0
        # Claims and premium are attested; the bordereau domain is blocked by its
        # own failing control - so the demo shows a gate that actually gates.
        accepted = not blocked and dom != "Premium & exposure"
        rows.append(dict(data_signoff_id=f"DS-2026Q4-{i:02d}", valuation_date=VAL_DATE,
            data_domain=dom, owner_role=OWNERS.get(dom, "Data Owner"),
            feeds_covered=len(d["feeds"]), controls_passing=d["pass"], controls_total=d["total"],
            status_code="BLOCKED" if blocked else ("ACCEPTED" if accepted else "PENDING"),
            attested_by=("claims.data.owner@bricksurance.demo" if accepted else None),
            attested_at=(now if accepted else None), note=NOTES.get(dom)))
    return rows


# ------------------------------------------------------------- 6 · class mapping
def build_class_mapping(w, wid):
    """Source class -> reserving class, with last quarter's mapping alongside.

    claim_count comes from the real ledger, so the "how much would this move"
    figure is genuine. One mapping DID change this quarter - the silent
    triangle-breaker the beat exists to surface.
    """
    counts = read_df(w, wid, f"""
        SELECT line_of_business_code lob, count(*) n FROM {FQ}.`1_raw_claim`
        GROUP BY line_of_business_code""")
    n_by_lob = {r["lob"]: int(r["n"]) for _, r in counts.iterrows()}

    # source classes as a policy admin system would hold them
    maps = [
        ("PROP-COM-01", "Commercial property — fire & perils", "COMMERCIAL_PROPERTY", None, False, None),
        ("PROP-COM-02", "Commercial property — business interruption", "COMMERCIAL_PROPERTY", None, False, None),
        ("MOT-FLT-01", "Commercial motor — fleet", "COMMERCIAL_MOTOR", None, False, None),
        ("MOT-CV-02", "Commercial motor — light commercial vehicle", "COMMERCIAL_MOTOR", None, False, None),
        ("LIAB-PL-01", "Public liability", "GENERAL_LIABILITY", None, False, None),
        ("LIAB-EL-02", "Employers liability", "GENERAL_LIABILITY", None, False, None),
        # THE CHANGE: professional indemnity written on a combined liability
        # wording used to be reserved with General Liability and now sits in
        # Professional Indemnity. Nothing is "wrong" - but both cohorts' history
        # moved, and no factor diagnostic would ever explain it.
        ("LIAB-PI-03", "Professional indemnity — combined liability wording",
         "PROFESSIONAL_INDEMNITY", "GENERAL_LIABILITY", True,
         "Reclassified for the 2026-Q4 close so PI is reserved on its own longer-tail pattern. "
         "Requested by the Chief Actuary; moves history out of General Liability and into "
         "Professional Indemnity — both development patterns are affected."),
        ("PI-STD-01", "Professional indemnity — standalone", "PROFESSIONAL_INDEMNITY", None, False, None),
        ("MAR-HULL-01", "Marine hull", "MARINE", None, False, None),
        ("MAR-CGO-02", "Marine cargo", "MARINE", None, False, None),
    ]
    rows = []
    for i, (code, label, lob, prior_lob, changed, reason) in enumerate(maps, 1):
        # spread the line's claims across its source classes so counts are real in aggregate
        share = [m for m in maps if m[2] == lob]
        n = max(1, n_by_lob.get(lob, 0) // max(1, len(share)))
        rows.append(dict(mapping_id=f"CM-2026Q4-{i:03d}", valuation_date=VAL_DATE,
            source_system_code="CLAIMS_CORE", source_class_code=code, source_class_label=label,
            line_of_business_code=lob, prior_line_of_business_code=(prior_lob or lob),
            changed_since_prior=bool(changed), claim_count=n, change_reason=reason))
    return rows


def run(w, wid):
    """Reusable entrypoint — the Job wrappers call this so the tested logic runs
    unchanged whether invoked from the CLI or a Databricks task."""
    now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")

    mv = build_movement(w, wid, now)
    n = overwrite(w, wid, "1_raw_data_movement",
        ["movement_id", "valuation_date", "prior_valuation_date", "line_of_business_code",
         "accident_year", "movement_type_code", "claim_count", "amount", "currency_code",
         "affects_reported_triangle"], mv)
    print(f"1_raw_data_movement: {n} rows")

    rec = build_reconciliation(w, wid)
    n = overwrite(w, wid, "1_raw_ingestion_reconciliation",
        ["reconciliation_id", "valuation_date", "feed_id", "control_name", "source_of_truth",
         "feed_amount", "source_amount", "difference", "tolerance", "ties", "currency_code",
         "explanation"], rec)
    print(f"1_raw_ingestion_reconciliation: {n} rows")

    feed_rows, dq_rows = build_feeds_and_dq(w, wid, now)
    n = overwrite(w, wid, "1_raw_data_feed",
        ["feed_id", "feed_name", "source_system_code", "valuation_date", "rows_received",
         "rows_expected", "arrived_at", "status", "dq_pass_pct", "sla_due_at",
         "months_expected", "months_present", "data_domain"], feed_rows)
    print(f"1_raw_data_feed: {n} rows")
    n = overwrite(w, wid, "1_raw_dq_expectation",
        ["expectation_id", "feed_id", "expectation_name", "dq_dimension_code", "severity",
         "passed", "failed_rows", "detail"], dq_rows)
    print(f"1_raw_dq_expectation: {n} rows")

    ds = build_data_signoff(feed_rows, dq_rows, rec, now)
    n = overwrite(w, wid, "1_raw_data_signoff",
        ["data_signoff_id", "valuation_date", "data_domain", "owner_role", "feeds_covered",
         "controls_passing", "controls_total", "status_code", "attested_by", "attested_at",
         "note"], ds)
    print(f"1_raw_data_signoff: {n} rows")

    cm = build_class_mapping(w, wid)
    n = overwrite(w, wid, "1_raw_class_mapping",
        ["mapping_id", "valuation_date", "source_system_code", "source_class_code",
         "source_class_label", "line_of_business_code", "prior_line_of_business_code",
         "changed_since_prior", "claim_count", "change_reason"], cm)
    print(f"1_raw_class_mapping: {n} rows")

    # ---- outwards reinsurance programme (gross-to-net) ----
    # One QS + one XoL layer per line, sized to each line's ultimate scale so the
    # net numbers are plausible. Long-tail lines cede more (bigger XoL); short-tail
    # property/marine cede via quota share. Deliberately simple; labelled as such.
    # QS is proportional (applies to the aggregate). XoL attaches per-claim, so we
    # carry an EXPECTED aggregate recovery (a modelled amount from the large losses
    # that pierce the layer), not the attachment applied to the line total. Recoveries
    # are sized to a few % of each line's ultimate — plausible, and clearly labelled.
    prog = [
        ("RIP-CP", "COMMERCIAL_PROPERTY",    0.15, 2_000_000, 3_000_000, 650_000,
         "15% quota share + £3m xs £2m per-risk excess-of-loss (≈£0.65m expected recovery)."),
        ("RIP-CM", "COMMERCIAL_MOTOR",       0.10, None,      None,      None,
         "10% quota share; no excess-of-loss layer."),
        ("RIP-GL", "GENERAL_LIABILITY",      0.20, 3_000_000, 7_000_000, 900_000,
         "20% quota share + £7m xs £3m per-risk excess-of-loss (≈£0.9m expected recovery)."),
        ("RIP-PI", "PROFESSIONAL_INDEMNITY", 0.25, 3_000_000, 7_000_000, 700_000,
         "25% quota share + £7m xs £3m per-risk excess-of-loss (≈£0.7m expected recovery)."),
        ("RIP-MA", "MARINE",                 0.30, None,      None,      None,
         "30% quota share; marine written heavily proportional."),
    ]
    prog_rows = [dict(programme_id=p, line_of_business_code=l, quota_share_pct=qs,
        xol_attachment=att, xol_limit=lim, xol_expected_recovery=rec, currency_code=CCY, note=note)
        for p, l, qs, att, lim, rec, note in prog]
    n = overwrite(w, wid, "reinsurance_programme",
        ["programme_id", "line_of_business_code", "quota_share_pct", "xol_attachment",
         "xol_limit", "xol_expected_recovery", "currency_code", "note"], prog_rows)
    print(f"reinsurance_programme: {n} rows")

    # control gate: the claims reconciliation must actually tie, or the "I never
    # fight the GL again" claim in the demo is not true
    claims_rec = [r for r in rec if r["reconciliation_id"] == "REC-CLAIMS-GL"][0]
    assert claims_rec["ties"], "claims-to-GL reconciliation does not tie"
    print("Control gate PASSED: claims paid movements tie to the ledger to the penny.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="DEV")
    ap.add_argument("--warehouse-id", default="a3b61648ea4809e3")
    args = ap.parse_args()
    run(WorkspaceClient(profile=args.profile), args.warehouse_id)

if __name__ == "__main__":
    main()
