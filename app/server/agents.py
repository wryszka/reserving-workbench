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
import uuid
from . import config, sql

F = config.fqn


# --------------------------------------------------------------------- governance trace
def trace(surface, specialist_key, question, endpoint, served_by, confidence=None,
          it=None, ot=None, cached=False):
    """Record every AI call in 5_ai_routing_trace for governance."""
    try:
        tid = uuid.uuid4().hex
        q = sql.esc((question or "")[:2000])
        sql.query(
            f"INSERT INTO {F('5_ai_routing_trace')} (trace_id, surface, specialist_key, question, "
            f"endpoint, served_by, confidence, input_tokens, output_tokens, was_cached, created_at, created_by) "
            f"VALUES ('{tid}', '{sql.esc(surface)}', {('NULL' if not specialist_key else chr(39)+sql.esc(specialist_key)+chr(39))}, "
            f"'{q}', {('NULL' if not endpoint else chr(39)+sql.esc(endpoint)+chr(39))}, '{sql.esc(served_by)}', "
            f"{confidence if confidence is not None else 'NULL'}, {it if it is not None else 'NULL'}, "
            f"{ot if ot is not None else 'NULL'}, {'true' if cached else 'false'}, current_timestamp(), "
            f"'app-sp')")
    except Exception:
        pass


def _invoke_endpoint(question, specialist):
    """Invoke the registered reserving-agent serving endpoint via the SDK (which carries the app
    SP's OAuth auth — inside a Databricks App there is no static token to extract). Returns dict
    or None if unavailable/cold, so the caller falls back to inline FMAPI."""
    ep = config.resolve_agent_endpoint()
    if not ep:
        return None
    try:
        w = config.get_workspace_client()
        rec = {"messages": [{"role": "user", "content": question or "brief the committee"}]}
        if specialist:
            rec["custom_inputs"] = {"specialist": specialist}
        resp = w.serving_endpoints.query(name=ep, dataframe_records=[rec])
        preds = getattr(resp, "predictions", None)
        if preds is None and hasattr(resp, "as_dict"):
            preds = resp.as_dict().get("predictions")
        pred = preds[0] if isinstance(preds, list) and preds else preds
        if not isinstance(pred, dict):
            return None
        msgs = pred.get("messages") or []
        text = (msgs[0].get("content") if msgs and isinstance(msgs[0], dict) else "") or ""
        if not text:
            return None
        co = pred.get("custom_outputs") or {}
        return {"text": text, "endpoint": ep, "specialist_key": co.get("specialist_key"),
                "specialist_name": co.get("specialist_name"), "confidence": co.get("confidence"),
                "reason": co.get("reason"), "model": co.get("model") or ep,
                "it": co.get("input_tokens"), "ot": co.get("output_tokens")}
    except Exception:
        return None


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
# Pin the period in every system prompt. Without it the model invents one ("Q3
# committee briefing") and contradicts the app, which reports the 2026-Q4 close
# everywhere else — a small thing that costs credibility on a big screen.
_PERIOD = (f"The current valuation date is {config.VALUATION_DATE} — this is the "
           f"2026-Q4 reserving close, compared against the prior close at 2026-09-30 (Q3). "
           f"Always refer to this quarter as Q4 2026. All figures are GBP. ")

SPECIALISTS = {
    "senior_reserving": {
        "name": "Senior Reserving Actuary",
        "scope": "Committee brief — emerging trends, cohorts needing attention, the judgement calls.",
        "triggers": "brief, committee, emerging, trends, overall, summary, what should I look at",
        "system": (_PERIOD + "You are the Senior Reserving Actuary for Bricksurance SE (commercial P&C). Brief the "
                   "quarterly reserving committee: emerging trends, cohorts needing attention, judgement "
                   "calls. Be specific and quantitative, cite AYs, lines and figures. Concise. Synthetic "
                   "demo data; no disclaimers."),
    },
    "movement": {
        "name": "Movement Explainer",
        "scope": "Explains the reserve roll-forward — why reserves moved this quarter, by driver.",
        "triggers": "why did reserves move, movement, roll-forward, change, driver, increase, decrease",
        "system": (_PERIOD + "You explain reserve movements for Bricksurance SE. Given the roll-forward drivers "
                   "(opening → expected run-off → experience → assumption change → large loss → expert "
                   "judgement → closing), narrate WHY reserves moved, quantifying each driver. Concise."),
    },
    "data_quality": {
        "name": "Data-Quality Investigator",
        "scope": "Validation and actual-vs-expected breaches — which cohorts, why, where to look.",
        "triggers": "validation, breach, tolerance, data quality, anomaly, outlier, actual vs expected, residual",
        "system": (_PERIOD + "You are a reserving data-quality investigator for Bricksurance SE. Given the "
                   "actual-vs-expected breaches, point the actuary at the cohorts that need attention, "
                   "quantify the residuals, and hypothesise the likely cause (e.g. a large loss). Concise."),
    },
    "committee_note": {
        "name": "Committee-Note Drafter",
        "scope": "Drafts the committee memo for a reserving decision / judgement.",
        "triggers": "draft, note, memo, write up, minute, document, rationale, paper",
        "system": (_PERIOD + "You draft concise reserving-committee notes for Bricksurance SE. Given the judgements "
                   "and selections, write a short, professional committee note: decision, rationale, "
                   "quantified impact, and the basis. Ready for an actuary to edit, not to author from scratch."),
    },
    "reviewer": {
        "name": "Reserving Peer Reviewer",
        "scope": "Independently reviews the actuary's own factor selection / overlay — a second set of eyes.",
        "triggers": "review, check, second opinion, sense check, is this reasonable, peer review, challenge",
        "system": (_PERIOD + "You are an independent reserving peer reviewer for Bricksurance SE — a senior actuary "
                   "giving a colleague a second opinion on THEIR selection or overlay. Be constructive and "
                   "specific: (1) does the selected pattern look reasonable vs the empirical and prior? "
                   "(2) is any override justified and adequately documented? (3) what would you challenge or "
                   "ask for before sign-off? Cite figures. End with a one-line verdict: SUPPORT / SUPPORT WITH "
                   "CONDITIONS / CHALLENGE. You advise; the actuary decides."),
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


def catalogue():
    """The specialist list as static metadata — no model call, so a page can draw
    its tiles instantly instead of waiting on a cold serving endpoint."""
    return [{"key": k, "name": v["name"], "scope": v["scope"]} for k, v in SPECIALISTS.items()]


def ask(question=None, specialist=None):
    """Supervisor entry. Tries the REGISTERED reserving-agent serving endpoint first (Agent
    Framework); falls back to inline FMAPI if the endpoint is cold/undeployed. Every call is
    traced in 5_ai_routing_trace for governance, honestly tagged with how it was served."""
    spec_list = catalogue()
    # 1) try the registered agent endpoint (the real Databricks agent)
    ep = _invoke_endpoint(question, specialist if specialist in SPECIALISTS else None)
    if ep and ep.get("text"):
        key = ep.get("specialist_key") or (specialist if specialist in SPECIALISTS else "senior_reserving")
        trace("supervisor", key, question, ep.get("endpoint"), "agent_endpoint",
              ep.get("confidence"), ep.get("it"), ep.get("ot"), False)
        return {"specialist_key": key, "specialist_name": ep.get("specialist_name") or SPECIALISTS.get(key, {}).get("name", key),
                "confidence": ep.get("confidence"), "reason": ep.get("reason") or "routed by the agent endpoint",
                "text": ep["text"], "model": ep.get("model"), "cached": False,
                "served_by": "agent_endpoint", "specialists": spec_list}
    # 2) fallback: inline FMAPI (cache-first)
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
    served = "cache" if r.get("cached") else "fmapi_fallback"
    trace("supervisor", key, question, config.FM_ENDPOINT, served, conf, cached=r.get("cached", False))
    try:
        det = sql.esc((question or s["name"])[:500])
        sql.query(f"INSERT INTO {F('5_gov_audit_event')} (event_id, event_type, entity_type, entity_id, detail, actor, created_at) "
                  f"VALUES ('AE-{_cache_key(key, prompt)[:8]}', 'agent_query', 'agent', '{key}', '{det}', '{s['name']}', current_timestamp())")
    except Exception:
        pass
    return {"specialist_key": key, "specialist_name": s["name"], "confidence": conf, "reason": reason,
            "text": r["text"], "model": r["model"], "cached": r.get("cached", False),
            "served_by": served, "specialists": spec_list}


def warm_cache():
    """Pre-run each specialist so the demo opens instantly. Returns count warmed."""
    facts = _facts(); n = 0
    for key, s in SPECIALISTS.items():
        prompt = _prompt_for(key, facts)
        _fm(s["system"], prompt, key, s["name"]); n += 1
    return n


def review_selection(lob, proposed_factors, empirical_factors, prior_factors, overrode, rationale):
    """The peer-reviewer agent applied to a specific in-progress selection — the
    'AI reviews the actuary's decision' beat. Live, grounded on the actual numbers
    the actuary is looking at, not a canned table."""
    prompt = (
        f"Line of business: {lob}. The actuary is selecting loss-development factors.\n"
        f"Empirical (volume-weighted) factors: {json.dumps(empirical_factors)}\n"
        f"Prior approved selection: {json.dumps(prior_factors)}\n"
        f"Actuary's PROPOSED factors: {json.dumps(proposed_factors)}\n"
        f"Overrode empirical? {'yes' if overrode else 'no'}. "
        f"Rationale given: {rationale or '(none)'}\n\n"
        f"Review their selection as an independent peer. Flag any factor that departs materially from both "
        f"the empirical and the prior without documentation. Give your verdict.")
    r = _fm(SPECIALISTS["reviewer"]["system"], prompt, "reviewer",
            f"review {lob} selection")
    return {"specialist_name": SPECIALISTS["reviewer"]["name"], "text": r["text"],
            "model": r["model"], "cached": r.get("cached", False)}


# back-compat: the committee page's brief button
def senior_reserving_brief(period=None):
    r = ask(specialist="senior_reserving")
    return {"period": period or config.VALUATION_DATE, "brief": r["text"], "model": r["model"], "cached": r["cached"]}
