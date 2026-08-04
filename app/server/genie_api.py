"""Genie via the Conversation API — server-side, no iframe. Starts a conversation in the
reserving Genie space, waits for the answer, and pulls the generated SQL + result rows.
Every call is traced for governance."""
from . import config
from .agents import trace


def ask(question):
    space = config.GENIE_SPACE_ID
    if not space:
        return {"ok": False, "answer": "Genie space not configured.", "sql": None, "columns": [], "rows": []}
    try:
        w = config.get_workspace_client()
        conv = w.genie.start_conversation_and_wait(space_id=space, content=question)
        texts, sql_text, columns, rows = [], None, [], []
        for att in (conv.attachments or []):
            if getattr(att, "text", None):
                try:
                    texts.append(att.text.content)
                except Exception:
                    pass
            if getattr(att, "query", None):
                sql_text = getattr(att.query, "query", None) or getattr(att.query, "description", None)
                try:
                    res = w.genie.get_message_query_result(
                        space_id=space, conversation_id=conv.conversation_id, message_id=conv.id)
                    sr = res.statement_response
                    if sr and sr.manifest and sr.manifest.schema and sr.manifest.schema.columns:
                        columns = [c.name for c in sr.manifest.schema.columns]
                    if sr and sr.result and sr.result.data_array:
                        rows = [list(r) for r in sr.result.data_array[:50]]
                except Exception:
                    pass
        answer = "\n".join(texts) if texts else ("Query executed." if rows else "No response from Genie.")
        trace("genie", None, question, f"genie/{space}", "genie", None, None, None, False)
        return {"ok": True, "answer": answer, "sql": sql_text, "columns": columns, "rows": rows,
                "conversation_id": getattr(conv, "conversation_id", None)}
    except Exception as e:
        return {"ok": False, "answer": f"Genie unavailable: {e}", "sql": None, "columns": [], "rows": []}
