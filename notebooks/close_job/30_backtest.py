# Databricks notebook source
# MAGIC %md
# MAGIC # Close job — Champion/challenger back-test — replay every method at past valuations
# MAGIC
# MAGIC `[reserving-workbench]` A task in the scheduled quarterly close. This is a THIN wrapper:
# MAGIC it imports the tested `tools/run_backtest.py` and calls its `run(w, wid)` — the exact same
# MAGIC logic the CLI runs, so the automated close and a hand-run produce identical, governed
# MAGIC output. No logic is duplicated here.

# COMMAND ----------
dbutils.widgets.text("warehouse_id", "a3b61648ea4809e3")
dbutils.widgets.text("tools_path", "/Workspace/Shared/reserving_workbench/close_tools")
WID = dbutils.widgets.get("warehouse_id")
TOOLS = dbutils.widgets.get("tools_path")

import sys
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

from databricks.sdk import WorkspaceClient
import run_backtest

run_backtest.run(WorkspaceClient(), WID)
print("30_backtest complete.")
