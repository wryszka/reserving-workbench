#!/usr/bin/env python3
"""Executable QA for reserving-workbench. Asserts the data reconciles AND the
asset-labelling convention holds (labelling is part of 'done', not an afterthought).

Usage:
    uv run --native-tls --with databricks-sdk tools/smoke_test.py --profile DEV
"""
import argparse, sys
from databricks.sdk import WorkspaceClient

CAT, SCH = "lr_dev_aws_us_catalog", "reserving_workbench"
FQ = f"{CAT}.{SCH}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="DEV")
    ap.add_argument("--warehouse-id", default="a3b61648ea4809e3")
    args = ap.parse_args()
    w = WorkspaceClient(profile=args.profile); wid = args.warehouse_id

    def q(sql):
        r = w.statement_execution.execute_statement(statement=sql, warehouse_id=wid, wait_timeout="50s")
        while r.status.state.value in ("PENDING", "RUNNING"):
            r = w.statement_execution.get_statement(r.statement_id)
        if r.status.state.value != "SUCCEEDED":
            raise RuntimeError(r.status.error.message if r.status.error else "?")
        return r.result.data_array or []

    checks = []
    def check(name, ok, detail=""):
        checks.append((name, ok, detail))
        print(f"  {'PASS' if ok else 'FAIL'}  {name}{(' — ' + detail) if detail else ''}")

    print("Reconciliation & content:")
    n = int(q(f"SELECT COUNT(*) FROM {FQ}.reserve_estimate WHERE abs((paid_to_date+case_reserves+ibnr)-ultimate_loss)>=1.0")[0][0])
    check("reserve estimates reconcile (paid+case+ibnr=ultimate)", n == 0, f"{n} breaks")
    n = int(q(f"SELECT COUNT(*) FROM {FQ}.reserve_estimate")[0][0])
    check("reserve_estimate populated", n > 0, f"{n} rows")
    n = int(q(f"SELECT COUNT(DISTINCT reserving_method_code) FROM {FQ}.reserve_estimate")[0][0])
    check("multiple methods present", n >= 3, f"{n} methods")
    n = int(q(f"SELECT COUNT(*) FROM {FQ}.reserving_methodology")[0][0])
    check("methodology library registered", n >= 5, f"{n} methods")
    n = int(q(f"SELECT COUNT(*) FROM {FQ}.actual_vs_expected WHERE within_tolerance=false")[0][0])
    check("validation flags the seeded anomaly", n >= 1, f"{n} breaches")
    n = int(q(f"SELECT COUNT(*) FROM {FQ}.selected_development_pattern")[0][0])
    check("LDF selection audit trail present", n >= 3, f"{n} selections")
    n = int(q(f"SELECT COUNT(*) FROM {FQ}.expert_judgement WHERE status_code='APPROVED'")[0][0])
    check("expert judgements recorded", n >= 1, f"{n} approved")
    # triangle reconciles to ledger
    tri = q(f"SELECT round(SUM(incremental_paid),2) FROM {FQ}.loss_development")[0][0]
    led = q(f"SELECT round(SUM(amount),2) FROM {FQ}.`1_raw_claim_transaction` WHERE claim_transaction_type_code IN ('INDEMNITY_PAYMENT','EXPENSE_PAYMENT','RECOVERY')")[0][0]
    check("triangle paid reconciles to ledger", abs(float(tri) - float(led)) < 1.0, f"tri={tri} ledger={led}")
    # lineage function
    cells = q(f"SELECT {FQ}.fn_reserve_to_qrt('RES-2026-COMM-2023-CH')")[0][0]
    check("reserve→QRT lineage function returns cells", bool(cells), str(cells))

    print("\nAsset labelling (enforced):")
    com = q(f"DESCRIBE SCHEMA EXTENDED {FQ}")
    schema_comment = next((r[1] for r in com if r[0] == "Comment"), "")
    check("schema comment carries [reserving-workbench]", "[reserving-workbench]" in schema_comment)
    # every table comment prefixed — excluding agent-framework auto-created payload/inference
    # tables (agents.deploy makes e.g. reserving_agent_payload; Databricks owns those, not our model).
    _AGENT_AUTO = ("_payload", "_payload_assessment_logs", "_inference")
    rows = q(f"SELECT table_name, comment FROM system.information_schema.tables WHERE table_catalog='{CAT}' AND table_schema='{SCH}'")
    unlabelled = [r[0] for r in rows
                  if not (r[1] or "").startswith("[reserving-workbench]")
                  and not any(r[0].endswith(sfx) for sfx in _AGENT_AUTO)]
    check("every table/view comment prefixed [reserving-workbench]", not unlabelled,
          f"unlabelled: {unlabelled[:5]}" if unlabelled else "all labelled")
    # bxc_project tag on tables
    try:
        tagged = q(f"SELECT COUNT(DISTINCT table_name) FROM system.information_schema.table_tags WHERE catalog_name='{CAT}' AND schema_name='{SCH}' AND tag_name='bxc_project'")[0][0]
        check("bxc_project tag present on objects", int(tagged) > 0, f"{tagged} tagged")
    except Exception as e:
        check("bxc_project tag present on objects", False, f"tag view error: {e}")

    passed = sum(1 for _, ok, _ in checks if ok)
    print(f"\n{passed}/{len(checks)} checks passed.")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
