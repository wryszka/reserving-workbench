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

    return router
