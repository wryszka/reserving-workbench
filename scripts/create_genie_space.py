#!/usr/bin/env python3
"""Create the 'Reserving Workbench — Ask the Triangle' Genie space over the reserving
tables + metric view. Reproducible. Prints the space_id on success.
Usage: python3 scripts/create_genie_space.py [profile] [warehouse_id] [catalog] [schema]
Uses the genie-rooms skill's GenieSpaceBuilder."""
import json
import pathlib
import subprocess
import sys

prof = sys.argv[1] if len(sys.argv) > 1 else "DEV"
wh = sys.argv[2] if len(sys.argv) > 2 else "a3b61648ea4809e3"
cat = sys.argv[3] if len(sys.argv) > 3 else "lr_dev_aws_us_catalog"
sch = sys.argv[4] if len(sys.argv) > 4 else "reserving_workbench"

BUILDER = pathlib.Path.home() / ".vibe/marketplace/plugins/fe-internal-tools/skills/genie-rooms/resources"
sys.path.insert(0, str(BUILDER))
from genie_space_builder import GenieSpaceBuilder  # noqa: E402

fqn = f"{cat}.{sch}"
TITLE = "Reserving Workbench — Ask the Triangle (Bricksurance SE)"
space = GenieSpaceBuilder(
    title=TITLE,
    description=("Natural-language analytics over the reserving process: loss-development triangles, "
                 "development-factor selection, reserve estimates by method, IBNR and ultimate by "
                 "accident year, actual-vs-expected validation, and the expert-judgement repository."),
    warehouse_id=wh,
)
space.set_instructions(
    "You answer questions about a commercial P&C insurer's reserving process (Bricksurance SE; synthetic "
    "data; GBP; valuation date 2026-12-31). TERMINOLOGY & MODEL: a loss-development TRIANGLE has rows = "
    "accident_year (year of loss) and columns = development_lag (years since the accident year); it is the "
    "view loss_development, derived from the claim ledger and reconciling to the penny. An age-to-age or "
    "development factor (LDF) is next-period cumulative over current-period cumulative. reserve_estimate has "
    "one row per accident_year x line_of_business x method (reserving_method_code: CHAIN_LADDER, "
    "BORNHUETTER_FERGUSON, EXPECTED_LOSS_RATIO, MACK, GLM, PEER_COMPARISON); paid_to_date + case_reserves + "
    "ibnr = ultimate_loss by construction; MACK carries ultimate_std_error. reserving_metrics is the "
    "certified metric view (query measures with MEASURE(paid_to_date), MEASURE(incurred_to_date), "
    "MEASURE(paid_ratio)); always GROUP BY or filter currency_code before summing money. "
    "selected_development_pattern is the AUDIT TRAIL of factor selection: source_code is "
    "DATABRICKS_EMPIRICAL / RESQ / PRIOR_SELECTION / MANUAL, status_code draft/pending_approval/approved/"
    "rejected/retired; an override HELDS the prior pattern when a data anomaly distorts the empirical pick. "
    "actual_vs_expected is validation: within_tolerance=false flags a cohort (the standardised_residual is "
    "the diagnostic; the AY2023 Commercial Property cohort is the seeded anomaly). expert_judgement is the "
    "audit-trailed overlay repository (magnitude signed in GBP, linked_qrt_cells to S.19.01, approval role "
    "routed by magnitude). Resolve *_code columns to labels by joining the reference tables; never show raw "
    "codes unless asked. Report money in GBP."
)
# tables (loss_development is a view; reserving_metrics is a metric view — added via their methods)
TABLES = [
    "reserve_estimate", "reserve_cashflow_pattern", "selected_development_pattern",
    "reserving_methodology", "expert_judgement", "actual_vs_expected",
    "1_raw_claim", "1_raw_claim_transaction",
    "line_of_business", "reserving_method", "development_selection_source", "ldf_averaging_method",
    "judgement_category", "judgement_status", "approval_role", "currency",
]
for t in TABLES:
    space.add_table(f"{fqn}.{t}")
space.add_view(f"{fqn}.loss_development")
space.add_metric_view(f"{fqn}.reserving_metrics")

# example question + SQL pairs (sorted by id is handled by the builder)
space.add_example_sql(
    "Total IBNR by line of business (chain-ladder)",
    f"SELECT line_of_business_code, round(sum(ibnr),0) AS ibnr FROM {fqn}.reserve_estimate "
    f"WHERE reserving_method_code='CHAIN_LADDER' GROUP BY line_of_business_code ORDER BY ibnr DESC", item_id="00000000000000000000000000000001")
space.add_example_sql(
    "Cumulative paid triangle for Commercial Property",
    f"SELECT accident_year, development_lag, cumulative_paid FROM {fqn}.loss_development "
    f"WHERE line_of_business_code='COMMERCIAL_PROPERTY' ORDER BY accident_year, development_lag", item_id="00000000000000000000000000000002")
space.add_example_sql(
    "Cohorts that breached actual-vs-expected validation",
    f"SELECT line_of_business_code, accident_year, variance, standardised_residual FROM {fqn}.actual_vs_expected "
    f"WHERE within_tolerance = false ORDER BY abs(standardised_residual) DESC", item_id="00000000000000000000000000000003")
space.add_example_sql(
    "Chain-ladder vs Bornhuetter-Ferguson ultimates for General Liability",
    f"SELECT accident_year, reserving_method_code, round(ultimate_loss,0) ultimate FROM {fqn}.reserve_estimate "
    f"WHERE line_of_business_code='GENERAL_LIABILITY' AND reserving_method_code IN "
    f"('CHAIN_LADDER','BORNHUETTER_FERGUSON') ORDER BY accident_year, reserving_method_code", item_id="00000000000000000000000000000004")
space.add_example_sql(
    "Expert judgements applied this quarter",
    f"SELECT line_of_business_code, category_code, magnitude, rationale FROM {fqn}.expert_judgement "
    f"WHERE status_code='APPROVED' ORDER BY abs(magnitude) DESC", item_id="00000000000000000000000000000005")
try:
    space.validate()
except Exception as e:  # noqa: BLE001
    print("validate warning:", e)

payload = {
    "title": TITLE,
    "description": "Reserving analytics: triangles, LDF selection, estimates by method, IBNR/ultimate, validation, judgement.",
    "parent_path": "/Workspace/Users/laurence.ryszka@databricks.com",
    "warehouse_id": wh,
    "serialized_space": space.to_json(),
}
open("/tmp/create_genie_space_rwb.json", "w").write(json.dumps(payload))
out = subprocess.run(["databricks", "api", "post", "/api/2.0/genie/spaces", "--profile", prof,
                      "--json", "@/tmp/create_genie_space_rwb.json"], capture_output=True, text=True)
print(out.stdout[:800] or out.stderr[:800])
try:
    print("SPACE_ID:", json.loads(out.stdout)["space_id"])
except Exception:  # noqa: BLE001
    pass
