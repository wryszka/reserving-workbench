"""Reserving Workbench — thin FastAPI backend. Presentation only: every panel reads a real
engine table / UC function / metric view / serving endpoint. No reserving logic lives here."""
import json
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse

from server import agents, config, sql

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
