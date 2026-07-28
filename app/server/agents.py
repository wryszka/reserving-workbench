"""Senior Reserving Actuary agent — a real Foundation Model API call over live reserving data.

Not a mock: it pulls the current triangle diagnostics, method spread, out-of-tolerance
validation cohorts and open expert judgements from the warehouse, and asks Claude (via the
Databricks FMAPI serving endpoint) to surface emerging trends the way a senior reserving
actuary would in a committee. Deterministic structured facts in, narrative out.
"""
import json
from . import config, sql

SYSTEM = (
    "You are the Senior Reserving Actuary for Bricksurance SE, a commercial P&C insurer. "
    "You are briefing the quarterly reserving committee. Given the reserving diagnostics "
    "below, surface the emerging trends, the cohorts that need attention, and the judgement "
    "calls a committee should focus on. Be specific and quantitative, cite accident years, "
    "lines of business and figures. Be concise (a few short paragraphs). This is synthetic "
    "demo data for Bricksurance SE (fictional); do not add disclaimers."
)


def _facts(period: str) -> dict:
    q = sql.query_many({
        "ave_flags": (f"SELECT line_of_business_code, accident_year, variance, standardised_residual "
                      f"FROM {config.fqn('actual_vs_expected')} WHERE within_tolerance = false "
                      f"ORDER BY abs(standardised_residual) DESC LIMIT 10"),
        "method_spread": (f"SELECT line_of_business_code, "
                          f"round(sum(CASE WHEN reserving_method_code='CHAIN_LADDER' THEN ultimate_loss END),0) cl, "
                          f"round(sum(CASE WHEN reserving_method_code='BORNHUETTER_FERGUSON' THEN ultimate_loss END),0) bf, "
                          f"round(sum(ibnr),0) ibnr FROM {config.fqn('reserve_estimate')} "
                          f"GROUP BY line_of_business_code ORDER BY line_of_business_code"),
        "judgements": (f"SELECT line_of_business_code, category_code, magnitude, status_code, rationale "
                       f"FROM {config.fqn('expert_judgement')} ORDER BY abs(magnitude) DESC LIMIT 6"),
        "selections": (f"SELECT selection_id, source_code, status_code, rationale "
                       f"FROM {config.fqn('selected_development_pattern')} WHERE status_code='APPROVED' "
                       f"AND rationale IS NOT NULL LIMIT 6"),
    })
    return q


def senior_reserving_brief(period: str = None) -> dict:
    period = period or config.VALUATION_DATE
    facts = _facts(period)
    prompt = (
        f"Reserving diagnostics as at {period}:\n\n"
        f"Out-of-tolerance validation cohorts (actual-vs-expected):\n{json.dumps(facts['ave_flags'], indent=2)}\n\n"
        f"Ultimate & IBNR by line of business (chain-ladder vs Bornhuetter-Ferguson):\n{json.dumps(facts['method_spread'], indent=2)}\n\n"
        f"Expert judgements on the book:\n{json.dumps(facts['judgements'], indent=2)}\n\n"
        f"Approved development-factor selections with rationale:\n{json.dumps(facts['selections'], indent=2)}\n\n"
        f"Brief the committee."
    )
    try:
        from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
        w = config.get_workspace_client()
        resp = w.serving_endpoints.query(
            name=config.FM_ENDPOINT,
            messages=[
                ChatMessage(role=ChatMessageRole.SYSTEM, content=SYSTEM),
                ChatMessage(role=ChatMessageRole.USER, content=prompt),
            ],
            max_tokens=700,
        )
        text = resp.choices[0].message.content if resp.choices else ""
    except Exception as e:
        text = (f"(Agent endpoint unavailable: {e})\n\nDeterministic summary: "
                f"{len(facts['ave_flags'])} cohort(s) breached validation tolerance; "
                f"{len(facts['judgements'])} expert judgement(s) recorded.")
    return {"period": period, "facts": facts, "brief": text, "model": config.FM_ENDPOINT}
