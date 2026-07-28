#!/usr/bin/env python3
"""Deploy reserving-workbench to a Databricks workspace (for real).

1. Runs every build/databricks/*.sql in order (schema, reference+seeds,
   entities, views, metric views, functions, relationships) via the SQL
   Statement Execution API.
2. Loads the synthetic world (claim ledger) from tools/world_engine.py by
   batched INSERT OVERWRITE, so the triangle view reconciles to the penny.

Idempotent: tables use IF NOT EXISTS, seeds/loads use INSERT OVERWRITE,
existing-constraint errors are skipped.

Usage:
    uv run --native-tls --with databricks-sdk --with pyyaml tools/deploy_databricks.py \
        --profile DEV --warehouse-id a3b61648ea4809e3
"""

import argparse
import sys
from pathlib import Path

from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "databricks"
SKIPPABLE = ("already exists", "ALREADY_EXISTS", "CONSTRAINT_ALREADY_EXISTS",
             "already has a primary key", "FOREIGN KEY")

CATALOG = "lr_dev_aws_us_catalog"
SCHEMA = "reserving_workbench"


def statements(path):
    text = "\n".join(l for l in path.read_text().splitlines() if not l.startswith("--"))
    parts = [p.strip().rstrip(";").strip() for p in text.split(";\n\n")]
    return [p + ";" for p in parts if p]


def run(w, wid, stmt):
    resp = w.statement_execution.execute_statement(
        statement=stmt, warehouse_id=wid, wait_timeout="50s")
    while resp.status.state.value in ("PENDING", "RUNNING"):
        resp = w.statement_execution.get_statement(resp.statement_id)
    return resp


def sql_val(v):
    if v is None or v == "":
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def load_world(w, wid):
    """Generate the world in-process and INSERT OVERWRITE the ledger tables."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("world_engine", ROOT / "tools" / "world_engine.py")
    we = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(we)
    claims, txns = we.generate()

    def batch_insert(table, cols, rows, chunk=500):
        fq = f"{CATALOG}.{SCHEMA}.`{table}`"
        # first chunk uses INSERT OVERWRITE (idempotent reset), rest append
        first = True
        for i in range(0, len(rows), chunk):
            part = rows[i:i + chunk]
            values = ",\n".join("(" + ", ".join(sql_val(r[c]) for c in cols) + ")" for r in part)
            verb = "INSERT OVERWRITE" if first else "INSERT INTO"
            stmt = f"{verb} {fq} ({', '.join(cols)}) VALUES\n{values};"
            resp = run(w, wid, stmt)
            if resp.status.state.value != "SUCCEEDED":
                sys.exit(f"World load FAILED on {table} chunk {i}:\n{resp.status.error.message}")
            first = False
        return len(rows)

    n1 = batch_insert("1_raw_claim",
                      ["claim_id", "policy_id", "accident_year", "loss_date",
                       "line_of_business_code", "report_date"], claims)
    n2 = batch_insert("1_raw_claim_transaction",
                      ["claim_transaction_id", "claim_id", "transaction_year",
                       "transaction_date", "claim_transaction_type_code", "amount",
                       "currency_code"], txns)
    print(f"  loaded {n1} claims, {n2} transactions")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="DEV")
    ap.add_argument("--warehouse-id", default="a3b61648ea4809e3")
    ap.add_argument("--skip-world", action="store_true", help="DDL only, don't reload the ledger")
    args = ap.parse_args()

    w = WorkspaceClient(profile=args.profile)
    wid = args.warehouse_id
    print(f"Workspace: {w.config.host}\nWarehouse: {wid}\n")

    ok = skipped = 0
    for path in sorted(BUILD.glob("*.sql")):
        stmts = statements(path)
        print(f"{path.name}: {len(stmts)} statements")
        for stmt in stmts:
            resp = run(w, wid, stmt)
            if resp.status.state.value == "SUCCEEDED":
                ok += 1
            else:
                message = (resp.status.error.message or "") if resp.status.error else ""
                if any(s in message for s in SKIPPABLE):
                    skipped += 1
                else:
                    sys.exit(f"FAILED on: {stmt.splitlines()[0]}\n{message}")
    print(f"DDL: {ok} succeeded, {skipped} skipped (already existed).\n")

    if not args.skip_world:
        print("Loading synthetic world (claim ledger)...")
        load_world(w, wid)
    print("\nDeploy complete.")


if __name__ == "__main__":
    main()
