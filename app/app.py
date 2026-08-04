"""Reserving Workbench — thin FastAPI backend. Presentation only: every panel reads a real
engine table / UC function / metric view / serving endpoint. No reserving logic lives here."""
import json
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse

import datetime
import uuid

from server import agents, config, genie_api, reserving, sql

app = FastAPI(title="Reserving Workbench — Bricksurance SE")
F = config.fqn


@app.get("/healthz")
def healthz():
    return {"ok": True, "project": config.PROJECT}


@app.get("/api/config")
def get_config():
    host = config.workspace_host()
    return {
        "project": config.PROJECT, "entity": config.ENTITY,
        "catalog": config.CATALOG, "schema": config.SCHEMA,
        "valuation_date": config.VALUATION_DATE, "workspace_host": host,
        "genie_space_id": config.GENIE_SPACE_ID,
        "genie_embed_url": f"{host}/embed/genie/rooms/{config.GENIE_SPACE_ID}" if config.GENIE_SPACE_ID else "",
        "hub_app_url": config.HUB_APP_URL,
    }


# ------------------------------------------------------------------ triangle + LDF selection
@app.get("/api/triangle")
def triangle(lob: str = "COMMERCIAL_PROPERTY"):
    rows = sql.query(
        f"SELECT accident_year, development_lag, cumulative_paid, cumulative_incurred "
        f"FROM {F('loss_development')} WHERE line_of_business_code = '{sql.esc(lob)}' "
        f"ORDER BY accident_year, development_lag")
    lobs = sql.query(f"SELECT DISTINCT line_of_business_code lob FROM {F('loss_development')} ORDER BY lob")
    # pivot into a triangle grid + empirical volume-weighted factors
    grid, ays, lags = {}, set(), set()
    for r in rows:
        ay, lag = int(r["accident_year"]), int(r["development_lag"])
        ays.add(ay); lags.add(lag)
        grid[(ay, lag)] = {"paid": float(r["cumulative_paid"]), "incurred": float(r["cumulative_incurred"])}
    ays, lags = sorted(ays), sorted(lags)
    factors = {}
    for k in lags[:-1]:
        num = sum(grid[(ay, k + 1)]["paid"] for ay in ays if (ay, k + 1) in grid and (ay, k) in grid)
        den = sum(grid[(ay, k)]["paid"] for ay in ays if (ay, k + 1) in grid and (ay, k) in grid)
        factors[k] = round(num / den, 4) if den else None
    # per-AY individual factors (exposes the anomaly)
    indiv = {}
    for ay in ays:
        row = {}
        for k in lags[:-1]:
            if (ay, k) in grid and (ay, k + 1) in grid and grid[(ay, k)]["paid"]:
                row[k] = round(grid[(ay, k + 1)]["paid"] / grid[(ay, k)]["paid"], 3)
        indiv[ay] = row
    return {
        "lob": lob, "lobs": [r["lob"] for r in lobs],
        "accident_years": ays, "development_lags": lags,
        "cells": [{"ay": ay, "lag": lag, **grid[(ay, lag)]} for (ay, lag) in grid],
        "empirical_factors": factors, "individual_factors": indiv,
    }


@app.get("/api/selection")
def selection(lob: str = "COMMERCIAL_PROPERTY"):
    """The LDF selection audit trail: prior, empirical, elected — with rationale and lineage."""
    rows = sql.query(
        f"SELECT selection_id, valuation_date, source_code, averaging_method_code, "
        f"development_factors, tail_factor, prior_selection_id, status_code, rationale, "
        f"selected_by, approved_by FROM {F('selected_development_pattern')} "
        f"WHERE line_of_business_code = '{sql.esc(lob)}' ORDER BY valuation_date, selection_id")
    for r in rows:
        try:
            r["factors"] = json.loads(r.get("development_factors") or "[]")
        except Exception:
            r["factors"] = []
    return {"lob": lob, "selections": rows}


# ------------------------------------------------------------------ interactive selection (the decision module)
@app.post("/api/selection/compute")
def selection_compute(body: dict):
    """Recompute empirical factors under a chosen averaging basis (+ any manual per-factor
    overrides) and the resulting chain-ladder ultimate/IBNR, live from the triangle. Also
    returns the prior-selection reserve so the UI can show the delta. Read-only (no writeback)."""
    lob = body.get("lob", "COMMERCIAL_PROPERTY")
    basis = body.get("basis", "VOLUME_WEIGHTED")
    last_n = int(body.get("last_n", 5) or 5)
    tail = float(body.get("tail", 1.01) or 1.01)
    overrides = body.get("overrides") or {}
    out = reserving.compute(lob, basis, last_n, tail, overrides)
    out["prior_reserve"] = reserving.prior_reserve(lob, tail)
    return out


@app.post("/api/selection/elect")
def selection_elect(body: dict):
    """Write back the actuary's election as a NEW audited selected_development_pattern row.
    source = DATABRICKS_EMPIRICAL (accepted the computed pattern) or MANUAL (overrode factors).
    Retires the prior DRAFT for this LOB so the trail reads prior → this. Returns the new
    reserve. This is the human-in-the-loop decision the whole module exists for."""
    import json
    lob = body.get("lob", "COMMERCIAL_PROPERTY")
    factors = body.get("factors") or []
    tail = float(body.get("tail", 1.01) or 1.01)
    basis = body.get("basis", "VOLUME_WEIGHTED")
    overrode = bool(body.get("overrode"))
    rationale = (body.get("rationale") or "").strip()
    user = _user_from_headers()
    if len(factors) < 2:
        return {"ok": False, "error": "Need a development-factor array."}
    if overrode and len(rationale) < 10:
        return {"ok": False, "error": "An override needs a rationale (≥10 chars)."}
    source = "MANUAL" if overrode else "DATABRICKS_EMPIRICAL"
    sel_id = f"SEL-LIVE-{lob[:4]}-{datetime.datetime.now().strftime('%H%M%S')}"
    prior = sql.query_one(
        f"SELECT selection_id FROM {F('selected_development_pattern')} "
        f"WHERE line_of_business_code = '{sql.esc(lob)}' AND source_code = 'PRIOR_SELECTION' "
        f"AND status_code = 'APPROVED' ORDER BY valuation_date DESC LIMIT 1")
    prior_id = prior["selection_id"] if prior else None
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    fac_json = json.dumps([round(float(f), 4) for f in factors]).replace("'", "''")
    rat = rationale.replace("'", "''") if rationale else None
    # retire any live/draft for this LOB so the trail stays clean
    sql.query(f"UPDATE {F('selected_development_pattern')} SET status_code='RETIRED' "
              f"WHERE line_of_business_code='{sql.esc(lob)}' AND status_code IN ('DRAFT','PENDING_APPROVAL') "
              f"AND source_code='DATABRICKS_EMPIRICAL'")
    avg_sql = "NULL" if overrode else ("'" + sql.esc(basis) + "'")
    prior_sql = ("'" + prior_id + "'") if prior_id else "NULL"
    rat_sql = ("'" + rat + "'") if rat else "NULL"
    ts = now[:19].replace("T", " ")
    cols = ("selection_id, valuation_date, accident_year, line_of_business_code, currency_code, "
            "source_code, averaging_method_code, last_n_years, development_factors, tail_factor, "
            "prior_selection_id, status_code, rationale, selected_by, selected_at, approved_by, approved_at")
    vals = (f"'{sel_id}', DATE'{config.VALUATION_DATE}', NULL, '{sql.esc(lob)}', 'GBP', "
            f"'{source}', {avg_sql}, NULL, '{fac_json}', {tail}, "
            f"{prior_sql}, 'PENDING_APPROVAL', {rat_sql}, '{sql.esc(user)}', "
            f"TIMESTAMP'{ts}', NULL, NULL")
    sql.query(f"INSERT INTO {F('selected_development_pattern')} ({cols}) VALUES ({vals})")
    tri = reserving.read_triangle(lob)
    fdict = {i: float(f) for i, f in enumerate(factors)}
    res = reserving.ultimate_ibnr(tri, fdict, tail)
    return {"ok": True, "selection_id": sel_id, "source": source, "status": "PENDING_APPROVAL",
            "prior_selection_id": prior_id, "selected_by": user, "reserve": res}


def _user_from_headers():
    return "reserving.actuary@bricksurance.demo"


# ------------------------------------------------------------------ methodology library
@app.get("/api/methodology")
def methodology():
    rows = sql.query(
        f"SELECT methodology_id, reserving_method_code, uc_model_name, model_version, alias, "
        f"produces_distribution, summary, owner_role FROM {F('reserving_methodology')} "
        f"ORDER BY reserving_method_code")
    return {"methods": rows}


# ------------------------------------------------------------------ estimates
@app.get("/api/estimates")
def estimates(lob: str = None):
    where = f"WHERE line_of_business_code = '{sql.esc(lob)}'" if lob else ""
    rows = sql.query(
        f"SELECT line_of_business_code, accident_year, reserving_method_code, paid_to_date, "
        f"case_reserves, ultimate_loss, ibnr, outstanding, ultimate_std_error, selection_id "
        f"FROM {F('reserve_estimate')} {where} ORDER BY line_of_business_code, accident_year, reserving_method_code")
    return {"estimates": rows}


# ------------------------------------------------------------------ diagnostics / validation
@app.get("/api/diagnostics")
def diagnostics():
    q = sql.query_many({
        "ave": (f"SELECT line_of_business_code, accident_year, expected_emergence, actual_emergence, "
                f"variance, standardised_residual, within_tolerance FROM {F('actual_vs_expected')} "
                f"ORDER BY abs(standardised_residual) DESC"),
        "flags": (f"SELECT count(*) breaches FROM {F('actual_vs_expected')} WHERE within_tolerance = false"),
    })
    return {"actual_vs_expected": q["ave"], "breaches": q["flags"][0] if q["flags"] else {}}


# ------------------------------------------------------------------ expert judgement + lineage
@app.get("/api/judgements")
def judgements():
    rows = sql.query(
        f"SELECT judgement_id, quarter, line_of_business_code, accident_year, category_code, "
        f"magnitude, currency_code, rationale, linked_qrt_cells, required_approval_role_code, "
        f"status_code, author, approver FROM {F('expert_judgement')} ORDER BY abs(magnitude) DESC")
    for r in rows:
        try:
            r["qrt_cells"] = json.loads(r.get("linked_qrt_cells") or "[]")
        except Exception:
            r["qrt_cells"] = []
    return {"judgements": rows}


# --- expert judgement: raise / approve (the overlays-register pattern, made interactive) ---
# Magnitude-routed approval authority (mirrors the Solvency II app).
_APPROVAL_THRESHOLDS = [(10_000_000.0, "BOARD"), (1_000_000.0, "CHIEF_ACTUARY"), (0.0, "SENIOR_ACTUARY")]


def _required_role(magnitude):
    m = abs(float(magnitude or 0))
    for thresh, role in _APPROVAL_THRESHOLDS:
        if m >= thresh:
            return role
    return "SENIOR_ACTUARY"


@app.post("/api/judgements/raise")
def judgement_raise(body: dict):
    """Raise a new expert judgement (maker). Status starts DRAFT, or PENDING_APPROVAL if submitted.
    Approval role is routed by magnitude. Rationale must be substantive (>=20 chars). Audited."""
    import json as _json
    b = body or {}
    lob = b.get("lob") or None
    ay = b.get("accident_year")
    cat = b.get("category_code", "EXPERT_JUDGEMENT_OTHER")
    try:
        mag = float(b.get("magnitude"))
    except (TypeError, ValueError):
        return {"ok": False, "error": "magnitude must be a number"}
    if mag == 0:
        return {"ok": False, "error": "a judgement with zero impact is not a judgement"}
    rationale = (b.get("rationale") or "").strip()
    if len(rationale) < 20:
        return {"ok": False, "error": "rationale must be substantive (≥20 chars) — this is the audit narrative"}
    submit = bool(b.get("submit"))
    qrt = b.get("qrt_cells") or []
    role = _required_role(mag)
    jid = "EJ-LIVE-" + uuid.uuid4().hex[:8]
    user = "reserving.actuary@bricksurance.demo"
    now_expr = "current_timestamp()"
    lob_sql = ("'" + sql.esc(lob) + "'") if lob else "NULL"
    ay_sql = str(int(ay)) if ay not in (None, "", "null") else "NULL"
    qrt_sql = "'" + sql.esc(_json.dumps(qrt)) + "'" if qrt else "NULL"
    status = "PENDING_APPROVAL" if submit else "DRAFT"
    cols = ("judgement_id, quarter, line_of_business_code, accident_year, category_code, magnitude, "
            "currency_code, rationale, linked_qrt_cells, required_approval_role_code, status_code, "
            "prior_judgement_id, author, created_at, approver, approved_at")
    vals = (f"'{jid}', '2026-Q4', {lob_sql}, {ay_sql}, '{sql.esc(cat)}', {mag}, 'GBP', "
            f"'{sql.esc(rationale)}', {qrt_sql}, '{role}', '{status}', NULL, '{sql.esc(user)}', "
            f"{now_expr}, NULL, NULL")
    sql.query(f"INSERT INTO {F('expert_judgement')} ({cols}) VALUES ({vals})")
    eid = "AE-EJ-" + uuid.uuid4().hex[:8]
    sql.query(f"INSERT INTO {F('5_gov_audit_event')} (event_id, event_type, entity_type, entity_id, detail, actor, created_at) "
              f"VALUES ('{eid}', 'judgement_raised', 'judgement', '{jid}', 'Raised {sql.esc(cat)} judgement, {mag:.0f} GBP', '{sql.esc(user)}', {now_expr})")
    return {"ok": True, "judgement_id": jid, "status": status, "required_approval_role": role, "author": user}


@app.post("/api/judgements/approve")
def judgement_approve(body: dict):
    """Approve a pending judgement (checker). Records approver + timestamp. Audited."""
    b = body or {}
    jid = b.get("judgement_id")
    if not jid:
        return {"ok": False, "error": "judgement_id required"}
    approver = "chief.actuary@bricksurance.demo"
    sql.query(f"UPDATE {F('expert_judgement')} SET status_code='APPROVED', approver='{sql.esc(approver)}', "
              f"approved_at=current_timestamp() WHERE judgement_id='{sql.esc(jid)}'")
    eid = "AE-EJ-" + uuid.uuid4().hex[:8]
    sql.query(f"INSERT INTO {F('5_gov_audit_event')} (event_id, event_type, entity_type, entity_id, detail, actor, created_at) "
              f"VALUES ('{eid}', 'judgement_approved', 'judgement', '{sql.esc(jid)}', 'Approved judgement {sql.esc(jid)}', '{sql.esc(approver)}', current_timestamp())")
    return {"ok": True, "judgement_id": jid, "approver": approver}


@app.get("/api/lineage")
def lineage(estimate_id: str):
    row = sql.query_one(f"SELECT {F('fn_reserve_to_qrt')}('{sql.esc(estimate_id)}') AS cells")
    cells = (row.get("cells") if row else "") or ""
    return {"estimate_id": estimate_id, "qrt_cells": [c.strip() for c in cells.split(";") if c.strip()]}


# ------------------------------------------------------------------ committee + agent
@app.get("/api/committee")
def committee():
    q = sql.query_many({
        "by_lob": (f"SELECT line_of_business_code, round(sum(ibnr),0) ibnr, round(sum(outstanding),0) outstanding "
                   f"FROM {F('reserve_estimate')} WHERE reserving_method_code='CHAIN_LADDER' "
                   f"GROUP BY line_of_business_code ORDER BY line_of_business_code"),
        "totals": (f"SELECT round(sum(ultimate_loss),0) ultimate, round(sum(ibnr),0) ibnr, "
                   f"round(sum(outstanding),0) outstanding FROM {F('reserve_estimate')} "
                   f"WHERE reserving_method_code='CHAIN_LADDER'"),
    })
    return {"by_lob": q["by_lob"], "totals": q["totals"][0] if q["totals"] else {}}


@app.post("/api/agent/brief")
def agent_brief(body: dict = None):
    return agents.senior_reserving_brief((body or {}).get("period"))


# ------------------------------------------------------------------ full-system lifecycle + external engines
LIFECYCLE = [
    {"n": 1, "stage": "Ingestion & triangle construction",
     "answers": "Where does my triangle come from? — ingest claims/premium (Federation to source), DQ expectations, versioned snapshots",
     "where": "loss_development ← claim ledger", "status": "next"},
    {"n": 2, "stage": "Triangle & LDF selection",
     "answers": "View triangle + empirical factors, compare to prior, elect/override — audited",
     "where": "selected_development_pattern", "status": "built"},
    {"n": 3, "stage": "Methodology library",
     "answers": "Chain-ladder, BF, Mack, GLM, peer — each a governed UC model",
     "where": "reserving_methodology", "status": "built"},
    {"n": 4, "stage": "Reserve estimates",
     "answers": "Ultimate / IBNR / outstanding per method, reconciling to the penny",
     "where": "reserve_estimate", "status": "built"},
    {"n": 5, "stage": "Validation & diagnostics",
     "answers": "Actual-vs-expected, tail-fit, residuals — the workbench validates its own methods",
     "where": "actual_vs_expected", "status": "built"},
    {"n": 6, "stage": "Expert judgement",
     "answers": "Overlays, audit-trailed, magnitude-routed approval",
     "where": "expert_judgement", "status": "built"},
    {"n": 7, "stage": "Roll-forward, ranges & committee sign-off",
     "answers": "How do I get to a signed number? — prior→new ultimate walk, stochastic ranges, board pack",
     "where": "reserve_estimate (+ranges)", "status": "next"},
    {"n": 8, "stage": "Downstream & close",
     "answers": "Single-producer contract to Solvency II TP, IFRS 17 LIC, GL recon, capital model; the reserving close cockpit",
     "where": "reserve_cashflow_pattern", "status": "next"},
]


@app.get("/api/lifecycle")
def lifecycle():
    return {"stages": LIFECYCLE,
            "built": sum(1 for s in LIFECYCLE if s["status"] == "built"),
            "total": len(LIFECYCLE)}


@app.get("/api/engines")
def engines():
    """The external-engine (ResQ) talk track: show every selection by source, so a ResQ-produced
    pick sits in the same governed table as a native one — same audit trail, same downstream."""
    rows = sql.query(
        f"SELECT source_code, line_of_business_code, selection_id, status_code, rationale, selected_by "
        f"FROM {F('selected_development_pattern')} ORDER BY source_code, line_of_business_code")
    counts = sql.query(
        f"SELECT source_code, count(*) n FROM {F('selected_development_pattern')} GROUP BY source_code ORDER BY source_code")
    return {"selections": rows, "counts": counts}


# ------------------------------------------------------------------ ingestion (the front door)
@app.get("/api/ingestion")
def ingestion():
    q = sql.query_many({
        "feeds": (f"SELECT feed_id, feed_name, source_system_code, rows_received, rows_expected, "
                  f"status, dq_pass_pct FROM {F('1_raw_data_feed')} ORDER BY feed_name"),
        "dq": (f"SELECT feed_id, expectation_name, severity, passed, failed_rows, detail "
               f"FROM {F('1_raw_dq_expectation')} ORDER BY feed_id, severity DESC, passed"),
    })
    return {"feeds": q["feeds"], "expectations": q["dq"]}


@app.post("/api/ingestion/accept")
def ingestion_accept(body: dict):
    """Human-in-the-loop: accept a feed into the reserving mart. Blocked if a critical
    expectation is failing (the actuary must resolve the quarantine first). Audited."""
    feed = body.get("feed_id"); user = "reserving.actuary@bricksurance.demo"
    if not feed:
        return {"ok": False, "error": "feed_id required"}
    crit = sql.query_one(f"SELECT count(*) n FROM {F('1_raw_dq_expectation')} "
                         f"WHERE feed_id='{sql.esc(feed)}' AND severity='critical' AND passed=false")
    if crit and int(crit["n"]) > 0:
        return {"ok": False, "error": f"{crit['n']} critical data-quality check(s) failing — resolve the quarantine before accepting."}
    sql.query(f"UPDATE {F('1_raw_data_feed')} SET status='accepted' WHERE feed_id='{sql.esc(feed)}'")
    eid = "AE-ING-" + uuid.uuid4().hex[:8]
    sql.query(f"INSERT INTO {F('5_gov_audit_event')} (event_id, event_type, entity_type, entity_id, detail, actor, created_at) "
              f"VALUES ('{eid}', 'feed_accepted', 'feed', '{sql.esc(feed)}', 'Accepted feed into the reserving mart', '{sql.esc(user)}', current_timestamp())")
    return {"ok": True, "feed_id": feed, "by": user}


# ------------------------------------------------------------------ landing / attention (Beat 2)
@app.get("/api/attention")
def attention():
    """'What needs my attention today' — the close-week hook that pulls the actuary
    straight to the anomaly, plus headline reserve KPIs and pending decisions."""
    q = sql.query_many({
        "breaches": (f"SELECT line_of_business_code, accident_year, standardised_residual "
                     f"FROM {F('actual_vs_expected')} WHERE within_tolerance = false ORDER BY abs(standardised_residual) DESC"),
        "pending_sel": (f"SELECT count(*) n FROM {F('selected_development_pattern')} WHERE status_code IN ('DRAFT','PENDING_APPROVAL')"),
        "pending_signoff": (f"SELECT count(*) n FROM {F('reserve_signoff')} WHERE status_code = 'PENDING_APPROVAL'"),
        "large": (f"SELECT count(*) n FROM {F('large_loss')} WHERE distorts_factor = true"),
        "totals": (f"SELECT round(sum(ultimate_loss),0) ultimate, round(sum(ibnr),0) ibnr, round(sum(outstanding),0) outstanding "
                   f"FROM {F('reserve_estimate')} WHERE reserving_method_code='CHAIN_LADDER'"),
        "signoff": (f"SELECT line_of_business_code, status_code, signed_best_estimate FROM {F('reserve_signoff')} ORDER BY line_of_business_code"),
    })
    return {"breaches": q["breaches"],
            "pending_selections": (q["pending_sel"][0]["n"] if q["pending_sel"] else 0),
            "pending_signoffs": (q["pending_signoff"][0]["n"] if q["pending_signoff"] else 0),
            "large_losses": (q["large"][0]["n"] if q["large"] else 0),
            "totals": q["totals"][0] if q["totals"] else {}, "signoff": q["signoff"],
            "valuation_date": config.VALUATION_DATE}


# ------------------------------------------------------------------ Workbench AI (supervisor)
@app.post("/api/ai/ask")
def ai_ask(body: dict = None):
    b = body or {}
    return agents.ask(question=b.get("question"), specialist=b.get("specialist"))


@app.post("/api/ai/cache/toggle")
def ai_cache_toggle(body: dict = None):
    config.USE_CACHE = bool((body or {}).get("on", not config.USE_CACHE))
    return {"use_cache": config.USE_CACHE}


@app.post("/api/ai/cache/warm")
def ai_cache_warm():
    return {"warmed": agents.warm_cache()}


@app.post("/api/genie/ask")
def genie_ask(body: dict):
    """Ask Genie server-side via the Conversation API (no iframe). Returns answer + SQL + rows."""
    return genie_api.ask((body or {}).get("question", ""))


@app.get("/api/ai/status")
def ai_status():
    """Is the registered agent endpoint live? Drives the 'served by' badge honestly."""
    ep = config.resolve_agent_endpoint()
    return {"agent_endpoint": ep or None, "endpoint_live": bool(ep), "fm_endpoint": config.FM_ENDPOINT,
            "genie_space_id": config.GENIE_SPACE_ID}


@app.post("/api/ai/review-selection")
def ai_review_selection(body: dict):
    """AI peer-review of the actuary's in-progress factor selection (the Triangle page)."""
    b = body or {}
    return agents.review_selection(
        b.get("lob", "COMMERCIAL_PROPERTY"), b.get("proposed_factors") or [],
        b.get("empirical_factors") or [], b.get("prior_factors") or [],
        bool(b.get("overrode")), b.get("rationale") or "")


# ------------------------------------------------------------------ wider process: variability / large loss / roll-forward
@app.get("/api/variability")
def variability():
    return {"rows": sql.query(
        f"SELECT line_of_business_code, best_estimate, standard_error, coefficient_of_variation, "
        f"percentile_75, percentile_95 FROM {F('reserve_variability')} ORDER BY coefficient_of_variation DESC")}


@app.get("/api/large-losses")
def large_losses():
    return {"rows": sql.query(
        f"SELECT large_loss_id, claim_id, line_of_business_code, accident_year, incurred, threshold, "
        f"treatment, distorts_factor FROM {F('large_loss')} ORDER BY incurred DESC")}


@app.get("/api/rollforward")
def rollforward(lob: str = "COMMERCIAL_PROPERTY"):
    return {"lob": lob, "rows": sql.query(
        f"SELECT driver, amount, display_order FROM {F('reserve_rollforward')} "
        f"WHERE line_of_business_code = '{sql.esc(lob)}' ORDER BY display_order")}


# ------------------------------------------------------------------ governance panel
@app.get("/api/governance")
def governance():
    q = sql.query_many({
        "audit": (f"SELECT event_type, entity_type, entity_id, detail, actor, created_at "
                  f"FROM {F('5_gov_audit_event')} ORDER BY created_at DESC LIMIT 40"),
        "models": (f"SELECT reserving_method_code, uc_model_name, model_version, alias, owner_role "
                   f"FROM {F('reserving_methodology')} ORDER BY reserving_method_code"),
        "signoff": (f"SELECT line_of_business_code, signed_best_estimate, reserving_method_code, data_version, "
                    f"status_code, signed_by, signed_at FROM {F('reserve_signoff')} ORDER BY line_of_business_code"),
        "recon": (f"SELECT round(SUM(incremental_paid),2) tri FROM {F('loss_development')}"),
        "recon_ledger": (f"SELECT round(SUM(amount),2) led FROM {F('1_raw_claim_transaction')} "
                         f"WHERE claim_transaction_type_code IN ('INDEMNITY_PAYMENT','EXPENSE_PAYMENT','RECOVERY')"),
        "ai": (f"SELECT surface, specialist_key, endpoint, served_by, was_cached, created_at "
               f"FROM {F('5_ai_routing_trace')} ORDER BY created_at DESC LIMIT 25"),
    })
    tri = float(q["recon"][0]["tri"]) if q["recon"] and q["recon"][0]["tri"] else 0
    led = float(q["recon_ledger"][0]["led"]) if q["recon_ledger"] and q["recon_ledger"][0]["led"] else 0
    return {"audit": q["audit"], "models": q["models"], "signoff": q["signoff"], "ai_activity": q["ai"],
            "reconciliation": {"triangle_paid": tri, "ledger_paid": led, "ties": abs(tri - led) < 1.0}}


@app.post("/api/signoff")
def signoff(body: dict):
    """Sign off a line of business's reserves — the 'put my name on the number' action."""
    lob = body.get("lob")
    user = "chief.actuary@bricksurance.demo"
    if not lob:
        return {"ok": False, "error": "lob required"}
    sql.query(f"UPDATE {F('reserve_signoff')} SET status_code='APPROVED', signed_by='{sql.esc(user)}', "
              f"signed_at=current_timestamp() WHERE line_of_business_code='{sql.esc(lob)}'")
    eid = "AE-SO-" + uuid.uuid4().hex[:8]
    sql.query(f"INSERT INTO {F('5_gov_audit_event')} (event_id, event_type, entity_type, entity_id, detail, actor, created_at) "
              f"VALUES ('{eid}', 'signed_off', 'signoff', 'SO-{sql.esc(lob[:4])}', 'Signed off {sql.esc(lob)} reserves', '{sql.esc(user)}', current_timestamp())")
    return {"ok": True, "lob": lob, "signed_by": user}


# ------------------------------------------------------------------ demo reset
@app.post("/api/reset")
def reset_demo():
    """Restore the demo to a clean state: clear live selections, agent-query audit rows,
    warm cache rows, and reset sign-offs to the seeded baseline (GL signed, rest pending)."""
    actions = []
    sql.query(f"DELETE FROM {F('selected_development_pattern')} WHERE selection_id LIKE 'SEL-LIVE-%'"); actions.append("cleared live selections")
    sql.query(f"DELETE FROM {F('expert_judgement')} WHERE judgement_id LIKE 'EJ-LIVE-%'"); actions.append("cleared live judgements")
    sql.query(f"DELETE FROM {F('5_gov_audit_event')} WHERE event_type='agent_query' OR event_id LIKE 'AE-SO-%' OR event_id LIKE 'AE-EJ-%' OR event_id LIKE 'AE-ING-%'"); actions.append("cleared demo audit rows")
    sql.query(f"UPDATE {F('reserve_signoff')} SET status_code=CASE WHEN line_of_business_code='GENERAL_LIABILITY' THEN 'APPROVED' ELSE 'PENDING_APPROVAL' END, "
              f"signed_by=CASE WHEN line_of_business_code='GENERAL_LIABILITY' THEN 'chief.actuary' ELSE NULL END"); actions.append("reset sign-offs to baseline")
    return {"ok": True, "actions": actions}


# ------------------------------------------------------------------ Learn
LEARN = [
    {"n": 1, "title": "Why reserving exists", "body":
     "Reserving estimates the money an insurer must hold for claims that have happened but aren't fully paid — "
     "the largest number on a P&C balance sheet. It feeds statutory accounts, the Solvency II SCR, IFRS 17 and "
     "the capital model. Getting it wrong in either direction is a regulatory and commercial problem."},
    {"n": 2, "title": "The triangle", "body":
     "Losses are organised by accident year (row) and development lag (column): how a cohort's losses grow as "
     "they mature. Here the triangle is a governed VIEW over the claim ledger — it reconciles to the penny and "
     "can never drift, because there is no separately-stored copy."},
    {"n": 3, "title": "Development factors & selection", "body":
     "Age-to-age (loss-development) factors project each cohort to ultimate. The actuary reviews the empirical "
     "factors, compares to the prior selection, and elects — overriding when a data anomaly (e.g. one late "
     "large loss) distorts the mechanical pick. This selection is the core judgement, and it is audited."},
    {"n": 4, "title": "Methods & uncertainty", "body":
     "Chain-ladder, Bornhuetter-Ferguson, Mack, GLM and peer-comparison each project the ultimate; swapping "
     "method writes a new estimate, never an overwrite. Mack and GLM also give a distribution — the coefficient "
     "of variation and percentiles that become the Solvency II risk margin and IFRS 17 risk adjustment."},
    {"n": 5, "title": "Validation & judgement", "body":
     "Actual-vs-expected on a rolling cohort validates the methods against emerging experience; breaches are "
     "flagged automatically. Expert judgements sit on top of the mechanical reserve, each audit-trailed with a "
     "rationale, a magnitude-routed approval, and the QRT cells they touch."},
    {"n": 6, "title": "Governance & sign-off", "body":
     "Every data point is reconciled, every action is logged, every model is versioned. Sign-off records the "
     "signed best estimate and the as-at data version, so the whole basis is reproducible for the auditor — "
     "the actuary can put their name to the number and defend it."},
    {"n": 7, "title": "The wider process & the seam", "body":
     "Ingestion and DQ upstream; roll-forward, ranges, committee pack and the regulatory/capital handoff "
     "downstream. And the engine seam: run the selection natively, or orchestrate an external tool (ResQ) — "
     "the pick lands in the same governed table either way."},
]


@app.get("/api/learn")
def learn():
    return {"panels": LEARN}


# ------------------------------------------------------------------ assets manifest (asset labelling)
@app.get("/api/assets")
def assets():
    """What UC objects this workbench owns, read live from information_schema tags — so the
    'what does this asset belong to' question is answerable inside the product."""
    q = sql.query_many({
        "tables": (f"SELECT table_name, comment FROM system.information_schema.tables "
                   f"WHERE table_catalog='{config.CATALOG}' AND table_schema='{config.SCHEMA}' "
                   f"ORDER BY table_name"),
        "tagged": (f"SELECT tag_name, tag_value, count(*) n FROM system.information_schema.table_tags "
                   f"WHERE catalog_name='{config.CATALOG}' AND schema_name='{config.SCHEMA}' "
                   f"AND tag_name LIKE 'bxc_%' GROUP BY tag_name, tag_value ORDER BY tag_name"),
    })
    return {"project": config.PROJECT, "catalog": config.CATALOG, "schema": config.SCHEMA,
            "tables": q["tables"], "tags": q["tagged"]}


# ------------------------------------------------------------------ SPA
DIST = os.path.join(os.path.dirname(__file__), "dist")


@app.get("/")
def index():
    return FileResponse(os.path.join(DIST, "index.html"))
