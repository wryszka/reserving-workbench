"""Thin SQL helper — runs statements on the warehouse via the app SP (SDK statement execution)."""
from concurrent.futures import ThreadPoolExecutor
from . import config

_POOL = ThreadPoolExecutor(max_workers=8)


def query(statement: str):
    """Return list[dict] rows. Values come back as strings from the API — cast in callers."""
    w = config.get_workspace_client()
    resp = w.statement_execution.execute_statement(
        statement=statement, warehouse_id=config.WAREHOUSE_ID,
        catalog=config.CATALOG, schema=config.SCHEMA, wait_timeout="50s")
    result = resp.result
    if result is None or result.data_array is None:
        return []
    cols = [c.name for c in resp.manifest.schema.columns]
    return [dict(zip(cols, row)) for row in result.data_array]


def query_one(statement: str):
    rows = query(statement)
    return rows[0] if rows else None


def query_many(statements: dict):
    """Run a {key: statement} map concurrently. A failing statement yields [] for that key."""
    def _safe(s):
        try:
            return query(s)
        except Exception:
            return []
    futures = {k: _POOL.submit(_safe, s) for k, s in statements.items()}
    return {k: f.result() for k, f in futures.items()}


def esc(s: str) -> str:
    return (s or "").replace("'", "''")
