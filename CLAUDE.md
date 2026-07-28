# reserving-workbench — build notes

## What this is
Free-standing (**gen1**) governed reserving workbench for Bricksurance SE, tiled
into the Actuarial Workbench hub. Authored **gen2-ready** (convertible into
`bricksurance-data-core` via `import_ontology.py`, no business-level data
duplication). First-built capability = **LDF selection** (the Hiscox US Pricing
hook, review 6 Aug 2026). See `README.md` and `docs/`.

## Non-negotiables (user instructions)
- **Runs for real on Databricks.** Real Federation/Jobs/MLflow/UC/Apps — never fake.
- **Asset labelling** (`docs/ASSET_LABELLING.md`): every object announces it belongs
  to reserving-workbench (rich schema comment, `[reserving-workbench]` comment prefix,
  `bxc_*` UC tags, in-app Assets panel). Enforced by smoke test.
- **No business-level data duplication.** Triangle = derived view over a claim ledger,
  never a stored parallel dataset. Synthetic data reconciles to golden-thread heroes
  (`CLM-2026-000001` = £270k outstanding) so it merges into gen2 cleanly.
- **Gen2-format specs.** `model/reserving/*.yaml` identical format to
  `bricksurance-data-core/model/reserving/` (kind: entity/view/metric_view/function;
  owner=Chief Actuary; certification; standards crosswalk).
- **ResQ seam.** selection/method step is a pluggable boundary; `selected_development_pattern.source`
  ∈ {DATABRICKS_EMPIRICAL, RESQ, PRIOR_SELECTION, MANUAL}.
- uv `--native-tls` not pip/npm. Every page: "what am I seeing" explainer + demo disclaimer.
  Use Claude via FMAPI (`databricks-claude-sonnet-5`), not Llama.

## Target
DEV `fevm-lr-dev-aws-us` (profile DEV, valid) · catalog `lr_dev_aws_us_catalog` ·
schema `reserving_workbench` · warehouse `a3b61648ea4809e3` (Serverless Starter, RUNNING).

## Reuse map (proven patterns — do NOT reinvent)
From **solvency-ii-qrt-demo-pnc-agentic** (same domain, same catalog/schema conventions):
- Table naming `0_cfg_ / 1_raw_ / 2_stg_ / 3_ / 4_eng_ / 5_mon_ / 6_gov_`.
- **Expert-judgement repository** ≈ its `6_gov_overlays` (magnitude→approval-role routing:
  senior_actuary/chief_actuary/board; `linked_qrt_cells ARRAY<STRING>` = reserve→QRT lineage;
  rationale ≥20 chars). `routes/overlays.py` + `CreateOverlayModal.tsx`.
- **Methodology library governance** ≈ its `6_gov_promotions` + MLflow pyfunc in UC with
  `production`/`candidate` aliases. `register_reserving_models.py`, `routes/model_governance.py`.
- **Audit panel** = 5-tab (data/code/models/approvals+overlays/lineage). `routes/audit.py` + `lineage.py`
  (hand-curated QRT dependency map for demo reliability).
- **Senior Reserving Actuary agent** already exists there (`agent_senior_reserving`) — mirror it.
- Stack: FastAPI (async, per-domain routers, request-user audit) + React 19 + Vite + Tailwind + lucide.

From **ifrs17-workbench** (closest structural sibling): DAB shape, thin `app/` (app.py + app.yaml +
requirements.txt), `notebooks/` engines as driver-pandas batch (NOT DLT for engines), `resources/*.yml`
jobs, `scripts/` (create_genie_space, create_dashboard, grant_app_sp), `98_smoke_test` = executable QA.

From **bricksurance-data-core** `model/reserving/`: exact spec format. Existing gen2 reserving domain =
loss_development view + reserve_estimate entity + reserving_metrics metric view + reserving_method code set
(CHAIN_LADDER/BF/ELR/CAPE_COD). Our specs must be a SUPERSET that imports cleanly.

## Hub tile registration (verified checklist — repo /Users/laurence.ryszka/vibe/actuarial-workbench)
1. `src/app/frontend/src/lib/workbench-tiles.ts` — add TILES entry (slug 'reserving', status 'live',
   icon, to '/demo/reserving') + `DEFAULT_RESERVING_APP_URL` const.
2. `databricks.yml` — add `reserving_app_url` var (derive from apps_domain_number) + dev/serverless overrides.
3. `src/app/app.yaml` — add env `RESERVING_APP_URL: ${var.reserving_app_url}`.
4. `src/app/server/config.py` — `get_reserving_app_url()` + add to `hub_config()` dict.
5. `src/app/frontend/src/lib/config.ts` — add `reserving_app_url: string` to HubConfig.
6. `src/app/frontend/src/lib/demo-pages.ts` — add DEMO_PAGES.reserving (blurb, appUrlKey, runDocUrl).
7. Deploy: `make deploy-dev` (React build → bundle deploy → render_app_yaml.py → apps deploy).
Status badge renders automatically from `status` field (live/in_progress/roadmap).

## Deploy order gotcha (from data-core + ifrs17)
generate specs → world_engine (synthetic data) → deploy. Big INSERTs can hang the deploy loop.
`CREATE TABLE IF NOT EXISTS` won't evolve columns → DROP+recreate on schema change (serverless Table ACLs).
gh CLI: `gh auth switch -u wryszka` for the public repo, switch back after.

## Status (updated 2026-07-28)
- [x] Repo scaffold, README, ASSET_LABELLING, HISCOX_ENGAGEMENTS, DAB, CLAUDE.md
- [x] Specs — 21 files (10 code sets, 8 entities, 1 view, 1 metric view, 2 fns), gen2-format, compile clean
- [x] Vendored compiler tools/generate.py (backticks numbered tables, one rich-commented schema, bxc_ tags)
      + model/model.yaml + bindings/databricks.yaml (single-schema binding). Ontology JSON emitted.
- [x] tools/world_engine.py — deterministic ledger (seed 20260728): 361 claims / 4679 txns. Hero
      CLM-2026-000001 reconciles 180k/270k/450k. Seeded anomaly: CP AY2023 dev0->dev1 = 3.627 vs 1.667
      all other years (the override moment's reason).
- [x] tools/deploy_databricks.py — DEPLOYED FOR REAL to DEV: 183 DDL stmts, ledger loaded. Triangle view,
      metric view MEASURE(), fn_empirical_ldf all verified live. Schema comment carries [reserving-workbench] label.
- [ ] Notebooks (methods CL/BF/Mack/GLM → reserve_estimate, cashflow, AvE, methodology registry, agent) — task 5
- [ ] App (backend routers + React SPA) — task 6
- [ ] Smoke test + Genie space + hub tile — task 7
- Waiting on Hiscox: split LDF script (3 parts) + synthetic R indication code. Build proceeds on synthetic.
- DEPLOY CMD: `uv run --native-tls --with databricks-sdk --with pyyaml tools/deploy_databricks.py --profile DEV --warehouse-id a3b61648ea4809e3`
