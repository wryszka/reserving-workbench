"""Config — all portability via env vars (set in app.yaml). No hardcoded catalog/schema/IDs."""
import os
from functools import lru_cache

from databricks.sdk import WorkspaceClient


def _flag(name, default=True):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


CATALOG = os.getenv("CATALOG_NAME", "lr_dev_aws_us_catalog")
SCHEMA = os.getenv("SCHEMA_NAME", "reserving_workbench")
WAREHOUSE_ID = os.getenv("WAREHOUSE_ID", "a3b61648ea4809e3")
USE_CACHE = _flag("USE_CACHE", True)
GENIE_SPACE_ID = os.getenv("GENIE_SPACE_ID", "")
DASHBOARD_ID = os.getenv("DASHBOARD_ID", "")
FM_ENDPOINT = os.getenv("FM_ENDPOINT", "databricks-claude-sonnet-5")
HUB_APP_URL = os.getenv("HUB_APP_URL", "")
VALUATION_DATE = os.getenv("VALUATION_DATE", "2026-12-31")
ENTITY = os.getenv("ENTITY_NAME", "Bricksurance SE")
PROJECT = "reserving-workbench"


def fqn(table: str) -> str:
    return f"{CATALOG}.{SCHEMA}.`{table}`"


@lru_cache(maxsize=1)
def get_workspace_client() -> WorkspaceClient:
    return WorkspaceClient()


def workspace_host() -> str:
    h = os.getenv("DATABRICKS_HOST", "")
    if not h:
        try:
            h = get_workspace_client().config.host or ""
        except Exception:
            h = ""
    h = h.rstrip("/")
    if h and not h.startswith("http"):
        h = "https://" + h
    return h
