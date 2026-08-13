# Databricks notebook source
# MAGIC %md
# MAGIC # Close job — ODP bootstrap reserve distribution
# MAGIC
# MAGIC `[reserving-workbench]` A task in the scheduled quarterly close. Thin wrapper over the
# MAGIC tested `tools/run_bootstrap.py` — thousands of simulations per line, which is exactly why
# MAGIC it belongs in a Job and not the app. Same logic as the CLI, no duplication.

# COMMAND ----------
dbutils.widgets.text("warehouse_id", "a3b61648ea4809e3")
dbutils.widgets.text("tools_path", "/Workspace/Shared/reserving_workbench/close_tools")
WID = dbutils.widgets.get("warehouse_id")
TOOLS = dbutils.widgets.get("tools_path")

import sys
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

from databricks.sdk import WorkspaceClient
import run_bootstrap

run_bootstrap.run(WorkspaceClient(), WID)
print("40_bootstrap complete.")
