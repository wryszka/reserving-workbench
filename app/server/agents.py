"""Reserving AI — a supervisor over several specialist agents, each a real Foundation
Model API call grounded on live reserving tables, with a warm cache for repeatable demos.

Specialists:
  senior_reserving   — committee brief: emerging trends, cohorts to watch, judgement calls
  movement           — explains the reserve roll-forward ("why did reserves move?")
  data_quality       — validation / actual-vs-expected breaches, where to look
  committee_note     — drafts the committee memo for a decision
The supervisor classifies a free-text question and routes to one specialist.
"""
import hashlib
import json
from . import config, sql

F = config.fqn


# --------------------------------------------------------------------- cache
def _cache_key(agent, prompt):
    h = hashlib.sha256()
    h.update(agent.encode()); h.update(b"|"); h.update(prompt.encode())
    return h.hexdigest()[:32]


def cache_get(agent, prompt):
    if not config.USE_CACHE:
        return None
    try:
        row = sql.query_one(
            f"SELECT response, model FROM {F('5_ai_cache')} WHERE cache_key = '{_cache_key(agent, prompt)}' LIMIT 1")
        if row and row.get("response"):
            return {"text": row["response"], "model": row.get("model") or config.FM_ENDPOINT, "cached": True}
    except Exception:
        pass
    return None


def cache_put(agent, prompt, question, text, model):
    try:
        key = _cache_key(agent, prompt)
        q = sql.esc(question or "")[:2000]; resp = sql.esc(text or ""); m = sql.esc(model or "")
        sql.query(f"DELETE FROM {F('5_ai_cache')} WHERE cache_key = '{key}'")
        sql.query(f"INSERT INTO {F('5_ai_cache')} (cache_key, agent, question, response, model, created_at) "
                  f"VALUES ('{key}', '{sql.esc(agent)}', '{q}', '{resp}', '{m}', current_timestamp())")
    except Exception:
        pass


def _fm(system, prompt, agent, question):
    """Cache-first FMAPI call. Returns {text, model, cached}."""
    hit = cache_get(agent, prompt)
    if hit:
        return hit
    try:
        from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
        w = config.get_workspace_client()
        resp = w.serving_endpoints.query(
            name=config.FM_ENDPOINT,
            messages=[ChatMessage(role=ChatMessageRole.SYSTEM, content=system),
                      ChatMessage(role=ChatMessageRole.USER, content=prompt)],
            max_tokens=750)
        text = resp.choices[0].message.content if resp.choices else ""
        cache_put(agent, prompt, question, text, config.FM_ENDPOINT)
        return {"text": text, "model": config.FM_ENDPOINT, "cached": False}
    except Exception as e:
        return {"text": f"(Agent endpoint unavailable: {e})", "model": config.FM_ENDPOINT, "cached": False}


# --------------------------------------------------------------------- data fetch
def _facts():
    return sql.query_many({
        "ave": (f"SELECT line_of_business_code, accident_year, variance, standardised_residual "
                f"FROM {F('actual_vs_expected')} WHERE within_tolerance = false ORDER BY abs(standardised_residual) DESC LIMIT 8"),
        "spread": (f"SELECT line_of_business_code, round(sum(ibnr),0) ibnr FROM {F('reserve_estimate')} "
                   f"WHERE reserving_method_code='CHAIN_LADDER' GROUP BY line_of_business_code ORDER BY ibnr DESC"),
        "judge": (f"SELECT line_of_business_code, category_code, magnitude, status_code, rationale "
                  f"FROM {F('expert_judgement')} ORDER BY abs(magnitude) DESC LIMIT 6"),
        "roll": (f"SELECT driver, amount FROM {F('reserve_rollforward')} "
                 f"WHERE line_of_business_code='COMMERCIAL_PROPERTY' ORDER BY display_order"),
        "var": (f"SELECT line_of_business_code, coefficient_of_variation, best_estimate "
                f"FROM {F('reserve_variability')} ORDER BY coefficient_of_variation DESC"),
    })


# --------------------------------------------------------------------- specialists
SPECIALISTS = {
    "senior_reserving": {
        "name": "Senior Reserving Actuary",
        "scope": "Committee brief — emerging trends, cohorts needing attention, the judgement calls.",
        "triggers": "brief, committee, emerging, trends, overall, summary, what should I look at",
        "system": ("You are the Senior Reserving Actuary for Bricksurance SE (commercial P&C). Brief the "
                   "quarterly reserving committee: emerging trends, cohorts needing attention, judgement "
                   "calls. Be specific and quantitative, cite AYs, lines and figures. Concise. Synthetic "
                   "demo data; no disclaimers."),
    },
    "movement": {
        "name": "Movement Explainer",
        "scope": "Explains the reserve roll-forward — why reserves moved this quarter, by driver.",
        "triggers": "why did reserves move, movement, roll-forward, change, driver, increase, decrease",
        "system": ("You explain reserve movements for Bricksurance SE. Given the roll-forward drivers "
                   "(opening → expected run-off → experience → assumption change → large loss → expert "
                   "judgement → closing), narrate WHY reserves moved, quantifying each driver. Concise."),
    },
    "data_quality": {
        "name": "Data-Quality Investigator",
        "scope": "Validation and actual-vs-expected breaches — which cohorts, why, where to look.",
        "triggers": "validation, breach, tolerance, data quality, anomaly, outlier, actual vs expected, residual",
        "system": ("You are a reserving data-quality investigator for Bricksurance SE. Given the "
                   "actual-vs-expected breaches, point the actuary at the cohorts that need attention, "
                   "quantify the residuals, and hypothesise the likely cause (e.g. a large loss). Concise."),
    },
    "committee_note": {
        "name": "Committee-Note Drafter",
        "scope": "Drafts the committee memo for a reserving decision / judgement.",
        "triggers": "draft, note, memo, write up, minute, document, rationale, paper",
        "system": ("You draft concise reserving-committee notes for Bricksurance SE. Given the judgements "
                   "and selections, write a short, professional committee note: decision, rationale, "
                   "quantified impact, and the basis. Ready for an actuary to edit, not to author from scratch."),
    },
}

CLASSIFIER_SYSTEM = (
    "You are a routing classifier for a reserving workbench. Given a user question, pick ONE specialist "
    "who is best placed to answer. Reply with ONLY a single-line JSON object, no prose: "
    '{"specialist_key": "<key>", "confidence": <0-1>, "reason": "<one short sentence>"}. '
    "If nothing is a strong match, pick senior_reserving.")


def _classify(question):
    catalogue = "\n".join(f"- {k}: {s['name']} — {s['scope']} Triggers: {s['triggers']}"
                          for k, s in SPECIALISTS.items())
    prompt = f"Available specialists:\n{catalogue}\n\nUser question:\n{question}\n\nReturn the JSON object."
    r = _fm(CLASSIFIER_SYSTEM, prompt, "supervisor_classifier", question)
    import re
    try:
        m = re.search(r"\{[^{}]+\}", r["text"])
        obj = json.loads(m.group(0))
        key = obj.get("specialist_key", "senior_reserving")
        if key not in SPECIALISTS:
            key = "senior_reserving"
        return key, float(obj.get("confidence", 0.6)), str(obj.get("reason", ""))[:200]
    except Exception:
        # keyword fallback
        ql = question.lower()
        for k, s in SPECIALISTS.items():
            if any(t.strip() in ql for t in s["triggers"].split(",")):
                return k, 0.5, "keyword match (classifier fallback)"
        return "senior_reserving", 0.4, "default"


def _prompt_for(key, facts):
    if key == "movement":
        return f"Roll-forward drivers (Commercial Property):\n{json.dumps(facts['roll'], indent=2)}\n\nWhy did reserves move?"
    if key == "data_quality":
        return f"Actual-vs-expected breaches:\n{json.dumps(facts['ave'], indent=2)}\n\nWhere should the actuary look and why?"
    if key == "committee_note":
        return (f"Judgements:\n{json.dumps(facts['judge'], indent=2)}\n\n"
                f"IBNR by line:\n{json.dumps(facts['spread'], indent=2)}\n\nDraft the committee note.")
    # senior_reserving
    return (f"Out-of-tolerance cohorts:\n{json.dumps(facts['ave'], indent=2)}\n\n"
            f"IBNR by line:\n{json.dumps(facts['spread'], indent=2)}\n\n"
            f"Judgements:\n{json.dumps(facts['judge'], indent=2)}\n\n"
            f"Reserve uncertainty (CoV):\n{json.dumps(facts['var'], indent=2)}\n\nBrief the committee.")


def ask(question=None, specialist=None):
    """Supervisor entry: classify (unless a specialist is named) → run → return with routing trace."""
    facts = _facts()
    if specialist and specialist in SPECIALISTS:
        key, conf, reason = specialist, 1.0, "explicitly selected"
    elif question:
        key, conf, reason = _classify(question)
    else:
        key, conf, reason = "senior_reserving", 1.0, "default brief"
    s = SPECIALISTS[key]
    prompt = _prompt_for(key, facts)
    r = _fm(s["system"], prompt, key, question or s["name"])
    # log the agent call
    try:
        det = sql.esc((question or s["name"])[:500])
        sql.query(f"INSERT INTO {F('5_gov_audit_event')} (event_id, event_type, entity_type, entity_id, detail, actor, created_at) "
                  f"VALUES ('AE-{_cache_key(key, prompt)[:8]}', 'agent_query', 'agent', '{key}', '{det}', '{s['name']}', current_timestamp())")
    except Exception:
        pass
    return {"specialist_key": key, "specialist_name": s["name"], "confidence": conf, "reason": reason,
            "text": r["text"], "model": r["model"], "cached": r.get("cached", False),
            "specialists": [{"key": k, "name": v["name"], "scope": v["scope"]} for k, v in SPECIALISTS.items()]}


def warm_cache():
    """Pre-run each specialist so the demo opens instantly. Returns count warmed."""
    facts = _facts(); n = 0
    for key, s in SPECIALISTS.items():
        prompt = _prompt_for(key, facts)
        _fm(s["system"], prompt, key, s["name"]); n += 1
    return n


# back-compat: the committee page's brief button
def senior_reserving_brief(period=None):
    r = ask(specialist="senior_reserving")
    return {"period": period or config.VALUATION_DATE, "brief": r["text"], "model": r["model"], "cached": r["cached"]}
