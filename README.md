# Reserving Workbench

A governed, end-to-end **actuarial reserving** workbench on Databricks — for
Bricksurance SE (fictional commercial P&C insurer). Deeper than the
chain-ladder + BF worked examples elsewhere in the estate: a **methodology
library**, a **model-validation framework**, an **expert-judgement repository**,
a **quarter-over-quarter reserving-committee view**, and **direct lineage from
each reserve estimate to the regulatory (QRT) cells it produces**.

> **About this demo.** Bricksurance SE is fictional; all data is synthetic.
> The workbench demonstrates the *platform pattern* for reserving on Databricks —
> the methodology is illustrative, not a certified actuarial model.

## What this workflow covers

- **Methodology library** — chain-ladder, Bornhuetter-Ferguson, Mack, GLM-based,
  peer-comparison — each registered in Unity Catalog and governed identically.
- **Validation framework** — actual-vs-expected on a rolling cohort, automated
  tail-fit assessment, residual diagnostics — surfaced in a Diagnostics tab.
- **Expert-judgement repository** — every judgement audit-trailed with rationale
  and magnitude (the "overlays register" pattern, shared with the Solvency II app).
- **Reserving-committee view** — quarter-over-quarter movements with a Senior
  Reserving Actuary agent surfacing emerging trends.
- **Reserve → QRT lineage** — each reserve estimate traced to the QRT cells it
  produces (S.19.01 non-life triangles, etc.), surfaced in an audit panel.

## Development-factor selection (the Hiscox US hook)

The **loss-development-factor (LDF) selection** module is the first-built,
demo-critical capability: view a triangle of losses and empirical LDFs, compare
against a previously-selected set, and **elect** whether to use the empirical
pick or hold the prior — every override audited (who / when / old / new / why).
This is what Hiscox US Pricing asked for (call 23 Jul 2026; review 6 Aug 2026).
See `docs/HISCOX_LDF.md`. Note: LDFs are a **shared** technique — pricing teams
develop losses to ultimate for *rate indications*; reserving teams for *booked
reserves*. Same triangle machinery, different downstream consumer.

## The ResQ (external-tool) seam

The selection/method step is built as a **pluggable boundary** so a client using
LCP ResQ / Icecap / equivalent can slot their tool in without losing the rest:

```
Databricks (data + triangle prep)  →  [ Databricks OR ResQ ] selection  →  Databricks (consume + govern + downstream)
```

The `selected_development_pattern` table carries a `source` field
(`DATABRICKS_EMPIRICAL` / `RESQ` / `PRIOR_SELECTION` / `MANUAL`) — a
ResQ-produced selection is a first-class citizen with the same shape, so the
writeback, governance and downstream code never cares which tool made the pick.

## Gen1 now, gen2-ready by construction

This is a **free-standing (gen1)** workbench — its own repo, schema, and app,
tiled into the Actuarial Workbench hub — deliverable on its own timeline.

It is authored to be **cleanly convertible into gen2** (`bricksurance-data-core`,
the shared semantic layer): the domain model lives as **ontology-format
model-as-code** (`model/reserving/*.yaml`, identical format to
`bricksurance-data-core/model/reserving/`), so folding it into the core is
`import_ontology.py`, not a rewrite. Two hard rules protect that:

1. **No business-level data duplication.** The triangle is a *derived view* over
   a claim-transaction ledger, never a stored parallel dataset. Synthetic data is
   generated to reconcile to the same golden-thread heroes as the core
   (`CLM-2026-000001` = £270k outstanding), so it merges without collision.
2. **Semantics travel.** Every entity/view/metric-view/function carries owner
   (Chief Actuary) + certification + standards crosswalk, so meaning survives the
   move into the core.

## Where does this asset belong? (asset labelling)

Every deployed asset announces its owner — see `docs/ASSET_LABELLING.md`. In
short: schema `reserving_workbench` with a rich UC comment; every table/view/
function comment prefixed `[reserving-workbench]`; UC tags `bxc_project`,
`bxc_layer`, `bxc_gen` on all objects. The app's About page reads the asset
manifest so ownership is visible in-product too.

## Layout

| Path | What |
|---|---|
| `model/` | Ontology-format model-as-code (gen2-compatible specs) |
| `tools/` | Spec compiler, synthetic-world generator, deploy, smoke test |
| `notebooks/` | Reserving engines (triangle → factor selection → methods → estimates) |
| `app/` | Thin FastAPI + React SPA (Bricksurance house style) |
| `resources/` | DAB job/app/pipeline YAMLs |
| `docs/` | Design, deploy, demo run, Hiscox LDF, asset labelling |

## Target

DEV workspace `fevm-lr-dev-aws-us` · catalog `lr_dev_aws_us_catalog` · schema
`reserving_workbench` · warehouse `a3b61648ea4809e3` (Serverless Starter). All
serverless, scale-to-zero. Catalog is the portability anchor (one `--var`).
