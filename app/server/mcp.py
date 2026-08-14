"""MCP server — operate the reserving workbench by chat, over the SAME governed paths.

An outside assistant (Claude Desktop, a Genie-driven agent, the user's own copilot)
speaks MCP here and can read the triangle, compare the prior, run a what-if — and
PROPOSE and APPROVE a selection. The point of the demo beat: a selection proposed
from chat lands as the identical PENDING_APPROVAL row the app / notebook / SQL write,
visible in the same audit trail. The governance lives in the platform, not the UI —
so it's reachable from any door.

Non-negotiable: the write tools call the EXACT SAME app functions the UI calls
(reserving.compute, the elect/approve endpoints' logic). No rule is re-implemented
here — rationale-required-on-override, magnitude-routed approval, the stage-3 guard
all still apply, because it's the same code. An MCP that bypassed them would be a
governance hole, which would discredit the whole thesis.

Transport: JSON-RPC 2.0 over one POST (MCP streamable-HTTP), plus a GET manifest —
mirrors pricing-workbench/routes/mcp.py. Auth is whatever the Databricks App already
enforces in front of the container; no separate credential path.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Request

from . import reserving

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mcp", tags=["mcp"])

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "bricksurance-reserving-workbench", "version": "1.0.0"}

# The tool contract an unfamiliar agent reads. Read tools are safe; write tools are
# governed and human-in-the-loop (propose != approve, and neither bypasses a control).
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "get_triangle",
        "description": ("The cumulative-paid loss-development triangle and the empirical "
                        "age-to-age factors for a line of business. Call this to see the data "
                        "before proposing anything."),
        "inputSchema": {"type": "object", "properties": {
            "line_of_business": {"type": "string",
                "description": "e.g. COMMERCIAL_PROPERTY, GENERAL_LIABILITY, COMMERCIAL_MOTOR, PROFESSIONAL_INDEMNITY, MARINE"}},
            "required": ["line_of_business"]},
    },
    {
        "name": "compare_prior",
        "description": ("The prior approved pattern, the current empirical factors, and the "
                        "resulting ultimate — factor by factor. This is the actuary's core "
                        "comparison: what was held last quarter vs what the data says now."),
        "inputSchema": {"type": "object", "properties": {
            "line_of_business": {"type": "string"}}, "required": ["line_of_business"]},
    },
    {
        "name": "what_if",
        "description": ("A scratch-pad scenario — inflation points, tail, an extra large loss — "
                        "against the live triangle. Writes NOTHING; the governed number is "
                        "untouched. For exploration only."),
        "inputSchema": {"type": "object", "properties": {
            "line_of_business": {"type": "string"},
            "inflation_pts": {"type": "number", "description": "points added to claims inflation, e.g. 2"},
            "tail": {"type": "number", "description": "tail factor, default 1.01"},
            "large_loss_load": {"type": "number", "description": "extra large loss to load, GBP"}},
            "required": ["line_of_business"]},
    },
    {
        "name": "propose_selection",
        "description": ("Propose a development-factor selection. Writes a PENDING_APPROVAL row to "
                        "the SAME governed table the app writes — it does NOT approve or book "
                        "anything. If you override the empirical factors you MUST supply a "
                        "rationale (>=10 chars) or it is refused, exactly as in the app."),
        "inputSchema": {"type": "object", "properties": {
            "line_of_business": {"type": "string"},
            "factors": {"type": "array", "items": {"type": "number"},
                        "description": "the selected development-factor array"},
            "tail": {"type": "number", "description": "tail factor, default 1.01"},
            "overrode": {"type": "boolean", "description": "true if you departed from the empirical pattern"},
            "rationale": {"type": "string", "description": "required (>=10 chars) when overrode is true"}},
            "required": ["line_of_business", "factors"]},
    },
    {
        "name": "approve_selection",
        "description": ("Approve a pending selection (maker/checker: a different act from proposing) "
                        "and resume the pipeline — stage 3 runs on the approved pattern. Names the "
                        "approver in the audit trail."),
        "inputSchema": {"type": "object", "properties": {
            "line_of_business": {"type": "string"},
            "selection_id": {"type": "string", "description": "optional; defaults to the latest pending selection for the line"}},
            "required": ["line_of_business"]},
    },
    {
        "name": "method_accuracy",
        "description": ("The champion/challenger back-test: mean absolute error by method and line, "
                        "so an agent can say which method has been most accurate where."),
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# --- tool implementations — every write reuses the app's own governed functions ---
def _lob(args):
    return (args.get("line_of_business") or "COMMERCIAL_PROPERTY").upper()


def _t_get_triangle(args, app):
    return app.triangle(_lob(args))


def _t_compare_prior(args, app):
    lob = _lob(args)
    c = reserving.compute(lob, "VOLUME_WEIGHTED", 5, 1.01, None)
    prior = reserving.prior_selection(lob)
    return {"line_of_business": lob, "empirical_factors": c["empirical_factors"],
            "prior_selection": prior, "empirical_ultimate": c["reserve"]["ultimate"],
            "prior_ultimate": (reserving.prior_reserve(lob) or {}).get("ultimate")}


def _t_what_if(args, app):
    return app.whatif({"lob": _lob(args), "inflation_pts": args.get("inflation_pts", 0),
                       "tail": args.get("tail", 1.01), "large_loss_load": args.get("large_loss_load", 0)})


def _t_propose(args, app):
    # SAME endpoint logic as the app's Select & save — rationale/override rules enforced there
    return app.selection_elect({"lob": _lob(args), "factors": args.get("factors") or [],
                               "tail": args.get("tail", 1.01), "basis": "VOLUME_WEIGHTED",
                               "overrode": bool(args.get("overrode")),
                               "rationale": args.get("rationale") or ""})


def _t_approve(args, app):
    return app.selection_approve({"lob": _lob(args), "selection_id": args.get("selection_id")})


def _t_method_accuracy(args, app):
    return app.backtest()


TOOL_IMPLS = {
    "get_triangle": _t_get_triangle,
    "compare_prior": _t_compare_prior,
    "what_if": _t_what_if,
    "propose_selection": _t_propose,
    "approve_selection": _t_approve,
    "method_accuracy": _t_method_accuracy,
}


def _ok(rpc_id, result):
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def _err(rpc_id, code, message):
    return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}


# --- hands-on chat: drive the SAME tools from an in-app assistant --------------
# The demo point: type in plain English, watch Claude call the governed MCP tools,
# and see a proposed selection land in the app's audit trail — no external client
# needed to show the "operate it by chat" beat. The tools are the identical
# TOOL_IMPLS the JSON-RPC endpoint exposes, so nothing is re-implemented and the
# governance (rationale-on-override, propose≠approve) holds exactly.
CHAT_MAX_HOPS = 6
CHAT_SYSTEM = (
    "You are the reserving-workbench assistant for Bricksurance SE (commercial P&C), "
    "operating the workbench for a reserving actuary over the valuation at Q4 2026. "
    "You have tools that read the loss triangle, compare the prior approved pattern, run a "
    "scratch what-if, propose a development-factor selection, approve a pending selection, and "
    "report method back-test accuracy. Rules you must respect, because they are enforced by the "
    "same governed code the app uses:\n"
    "- ALWAYS read the triangle and/or compare the prior before you propose anything.\n"
    "- propose_selection writes a PENDING_APPROVAL row in the SAME audit trail as the app; it does "
    "NOT book anything. If you depart from the empirical factors you MUST pass overrode=true AND a "
    "rationale of at least 10 characters, or the tool refuses it.\n"
    "- approve_selection is a SEPARATE maker/checker step; only approve when the actuary asks.\n"
    "- Never invent a number: every figure you state must have come back from a tool. "
    "Be concise and specific; name the line of business and the factors you used."
)


def _fmapi_tools():
    """The MCP tool schemas in FMAPI/OpenAI function-calling shape."""
    return [{"type": "function", "function": {
        "name": t["name"], "description": t["description"],
        "parameters": t.get("inputSchema") or {"type": "object", "properties": {}}}}
        for t in TOOL_SCHEMAS]


def _fm_chat(w, fm_endpoint, messages):
    """One FMAPI chat completion WITH tools, via the raw invocations API so tool_calls
    come back unflattened (the typed SDK ChatMessage drops them)."""
    # NB: claude-sonnet-5 rejects the `temperature` parameter — omit it.
    return w.api_client.do("POST", f"/serving-endpoints/{fm_endpoint}/invocations",
        body={"messages": messages, "tools": _fmapi_tools(), "max_tokens": 900})


def _flatten_content(content):
    """claude-sonnet-5 returns content as either a plain string or a list of typed
    blocks (reasoning / text / …). Flatten to the visible prose for display."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                parts.append(b["text"])
        return "\n".join(parts).strip()
    return ""


def _assistant_msg(resp):
    choices = (resp or {}).get("choices") or []
    if not choices:
        return {"role": "assistant", "content": ""}
    m = choices[0].get("message") or {}
    # keep the ORIGINAL content shape in the message we feed back to the model (it may
    # carry reasoning signatures the API needs), but expose flattened text separately.
    out = {"role": "assistant", "content": m.get("content") or ""}
    if m.get("tool_calls"):
        out["tool_calls"] = m["tool_calls"]
    out["_text"] = _flatten_content(m.get("content"))
    return out


def register(app_module):
    """Wire the router to the app module so tools can call its endpoint functions."""

    @router.post("")
    async def jsonrpc(request: Request):
        try:
            body = await request.json()
        except Exception:
            return _err(None, -32700, "Parse error: body is not valid JSON")
        rpc_id = body.get("id"); method = body.get("method"); params = body.get("params") or {}

        if method == "initialize":
            return _ok(rpc_id, {
                "protocolVersion": PROTOCOL_VERSION, "serverInfo": SERVER_INFO,
                "capabilities": {"tools": {}},
                "instructions": (
                    "Reserving workbench services. Read the triangle and compare the prior "
                    "before proposing. propose_selection writes a PENDING_APPROVAL row — it does "
                    "not book anything; approve_selection is the separate maker/checker step. "
                    "Every write lands in the same governed table and audit trail as the app.")})
        if method in ("notifications/initialized", "notifications/cancelled"):
            return _ok(rpc_id, {})
        if method == "tools/list":
            return _ok(rpc_id, {"tools": TOOL_SCHEMAS})
        if method == "tools/call":
            name = params.get("name"); args = params.get("arguments") or {}
            impl = TOOL_IMPLS.get(name)
            if impl is None:
                return _err(rpc_id, -32601, f"Unknown tool: {name}")
            try:
                payload = impl(args, app_module)
            except Exception as e:
                logger.exception("mcp tool %s failed", name)
                return _err(rpc_id, -32603, f"Tool execution failed: {str(e)[:200]}")
            return _ok(rpc_id, {
                "content": [{"type": "text", "text": json.dumps(payload, default=str)}],
                "structuredContent": payload,
                "isError": isinstance(payload, dict) and payload.get("ok") is False})
        return _err(rpc_id, -32601, f"Method not found: {method}")

    @router.get("/manifest")
    async def manifest():
        return {"server": SERVER_INFO, "protocol_version": PROTOCOL_VERSION,
                "tools": [{"name": t["name"], "description": t["description"]} for t in TOOL_SCHEMAS]}

    @router.post("/chat")
    async def chat(request: Request):
        """Hands-on: one turn of a Claude tool-use loop over the SAME governed MCP tools.
        Returns the assistant reply plus a log of every tool call (name, args, ok, result
        preview) so an audience watches the tools fire and a proposal land in the audit trail."""
        from . import config
        try:
            body = await request.json()
        except Exception:
            body = {}
        message = (body.get("message") or "").strip()
        history = body.get("history") or []
        if not message:
            return {"ok": False, "error": "empty message"}
        fm = config.FM_ENDPOINT
        try:
            w = config.get_workspace_client()
        except Exception as e:
            return {"ok": False, "error": f"workspace client unavailable: {str(e)[:160]}"}
        messages = [{"role": "system", "content": CHAT_SYSTEM}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        tool_log = []
        # per-turn memo of READ-tool results: a model sometimes calls the same read twice
        # in one turn (e.g. method_accuracy x2). Serve the repeat from memo so the tool
        # doesn't re-query and the duplicate doesn't clutter the visible log. Write tools
        # (propose/approve) are never memoised — each is a distinct governed action.
        _READ_TOOLS = {"get_triangle", "compare_prior", "what_if", "method_accuracy"}
        memo = {}
        reply = ""
        try:
            for _ in range(CHAT_MAX_HOPS):
                resp = _fm_chat(w, fm, messages)
                assistant = _assistant_msg(resp)
                messages.append(assistant)
                calls = assistant.get("tool_calls") or []
                if not calls:
                    reply = assistant.get("_text") or _flatten_content(assistant.get("content"))
                    break
                for call in calls:
                    fn = call.get("function") or {}
                    name = fn.get("name") or ""
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    memo_key = (name, json.dumps(args, sort_keys=True)) if name in _READ_TOOLS else None
                    if memo_key is not None and memo_key in memo:
                        result = memo[memo_key]        # repeat read — reuse, don't re-run or re-log
                        messages.append({"role": "tool", "tool_call_id": call.get("id"),
                                         "content": json.dumps(result, default=str)[:4000]})
                        continue
                    impl = TOOL_IMPLS.get(name)
                    if impl is None:
                        result = {"error": f"unknown tool {name}"}
                    else:
                        try:
                            result = impl(args, app_module)
                        except Exception as e:
                            logger.exception("mcp chat tool %s failed", name)
                            result = {"error": str(e)[:200]}
                    if memo_key is not None:
                        memo[memo_key] = result
                    ok = not (isinstance(result, dict) and (result.get("ok") is False or result.get("error")))
                    tool_log.append({"tool": name, "args": args, "ok": ok,
                                     "result": (result if isinstance(result, dict) else {"value": result})})
                    messages.append({"role": "tool", "tool_call_id": call.get("id"),
                                     "content": json.dumps(result, default=str)[:4000]})
            else:
                reply = reply or "I made several tool calls without settling — try asking one step at a time."
        except Exception as e:
            logger.exception("mcp chat turn failed")
            return {"ok": False, "error": str(e)[:300], "tool_log": tool_log,
                    "reply": "The assistant is briefly unavailable — try again in a moment."}
        # trim history for the client to send back next turn (drop the system prompt +
        # the display-only _text field so the model gets clean turns back).
        hist = [{k: v for k, v in m.items() if k != "_text"}
                for m in messages if m.get("role") != "system"]
        return {"ok": True, "reply": reply, "tool_log": tool_log,
                "history": hist[-12:], "model": fm}

    return router
