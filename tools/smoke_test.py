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
    # gross-to-net (A5): net must exist, be below gross, and be a sane proportion (not <50% or >gross)
    row = q(f"SELECT round(sum(ultimate_loss),0), round(sum(ultimate_net),0) FROM {FQ}.reserve_estimate "
            f"WHERE reserving_method_code='CHAIN_LADDER' AND ultimate_net IS NOT NULL")[0]
    g, net = float(row[0] or 0), float(row[1] or 0)
    check("net ultimate exists and is a sane fraction of gross", g > 0 and 0.55*g < net < g,
          f"gross {g:,.0f} net {net:,.0f} ({(net/g*100 if g else 0):.0f}%)")
    n = int(q(f"SELECT COUNT(*) FROM {FQ}.reinsurance_programme")[0][0])
    check("reinsurance programme seeded", n >= 3, f"{n} lines")
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

    print("\nIngestion control surface (the 'trust the data' front door):")
    n = int(q(f"SELECT COUNT(*) FROM {FQ}.`1_raw_data_movement`")[0][0])
    check("data movement since prior close populated", n > 0, f"{n} rows")
    # the narrative row: the backdated large loss that restates a reported cell
    n = int(q(f"SELECT COUNT(*) FROM {FQ}.`1_raw_data_movement` "
              f"WHERE movement_type_code='BACKDATED_TRANSACTION' AND affects_reported_triangle")[0][0])
    check("backdated transaction restating a reported cell present", n >= 1, f"{n} rows")
    # reopens must be REAL in the ledger, not asserted downstream
    n = int(q(f"SELECT COUNT(*) FROM {FQ}.`1_raw_data_movement` WHERE movement_type_code='REOPENED'")[0][0])
    check("reopened claims present in the movement diff", n >= 1, f"{n} cohort rows")
    # the claims-to-ledger control must actually tie, or the demo's core claim is false
    row = q(f"SELECT ties, difference FROM {FQ}.`1_raw_ingestion_reconciliation` "
            f"WHERE reconciliation_id='REC-CLAIMS-GL'")
    check("claims paid reconciliation ties to the penny",
          bool(row) and str(row[0][0]).lower() == "true", f"difference={row[0][1] if row else 'missing'}")
    # ... and exactly one break should exist, explained (the bordereau)
    n = int(q(f"SELECT COUNT(*) FROM {FQ}.`1_raw_ingestion_reconciliation` "
              f"WHERE ties=false AND explanation IS NOT NULL")[0][0])
    check("the one reconciliation break is explained and owned", n >= 1, f"{n} explained break(s)")
    # the data sign-off gate must have a genuinely BLOCKED domain to demo the refusal
    n = int(q(f"SELECT COUNT(*) FROM {FQ}.`1_raw_data_signoff` WHERE status_code='BLOCKED'")[0][0])
    check("data sign-off gate has a blocked domain (the refusal beat)", n >= 1, f"{n} blocked")
    # DQ checks carry their Solvency II dimension (Article 19 evidence, not just tests)
    n = int(q(f"SELECT COUNT(DISTINCT dq_dimension_code) FROM {FQ}.`1_raw_dq_expectation` "
              f"WHERE dq_dimension_code IS NOT NULL")[0][0])
    check("DQ checks tagged with all 3 Solvency II dimensions", n == 3, f"{n} dimensions")
    # the silent triangle-breaker
    n = int(q(f"SELECT COUNT(*) FROM {FQ}.`1_raw_class_mapping` WHERE changed_since_prior")[0][0])
    check("a class-mapping change is flagged", n >= 1, f"{n} changed")
    # completeness/timeliness must be populated, or tab 5 is empty on screen
    n = int(q(f"SELECT COUNT(*) FROM {FQ}.`1_raw_data_feed` "
              f"WHERE months_expected IS NOT NULL AND sla_due_at IS NOT NULL")[0][0])
    check("feeds carry completeness + SLA fields", n >= 1, f"{n} feeds")

    print("\nMethodology models (the 'registered and version-controlled' claim):")
    # every method the app indexes must EXIST as a UC model, or the claim is a label
    indexed = {r[0] for r in q(f"SELECT uc_model_name FROM {FQ}.reserving_methodology")}
    try:
        existing = {m.full_name for m in w.registered_models.list(catalog_name=CAT, schema_name=SCH)}
        missing = sorted(indexed - existing)
        check("every indexed method exists as a UC registered model", not missing,
              f"missing: {missing[:4]}" if missing else f"{len(indexed)} models")
    except Exception as e:
        check("every indexed method exists as a UC registered model", False, f"registry error: {e}")
    n = int(q(f"SELECT COUNT(*) FROM {FQ}.reserving_methodology "
              f"WHERE reserving_method_code='INHOUSE_FREQUENCY_SEVERITY'")[0][0])
    check("customer's own model registered as a first-class method", n == 1, f"{n} rows")

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
