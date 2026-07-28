# Asset labelling — every asset says what it belongs to

**Why this exists.** The workspace holds many demos' assets side by side. Opening
Catalog Explorer or the workspace tree and *not being able to tell which asset
belongs to which project* is a real problem. This workbench makes ownership
self-evident, at every layer, with no lookup required.

## The convention

### 1. Schema (one schema, richly commented)

- Single schema `reserving_workbench` (one-schema-per-demo rule).
- The schema's UC **comment** is a full ownership statement — project, purpose,
  repo, gen tier, "synthetic data" disclaimer. (Contrast: `ifrs17_workbench` and
  `solvency2_workbench` ship with *blank* schema comments — exactly the
  "what is this?" gap we are fixing.)

### 2. Tables / views / functions (comment prefix + numbered names)

- Every object's UC comment starts with **`[reserving-workbench]`** so the owning
  project is the first thing you read in Catalog Explorer.
- Numbered table prefixes for pipeline layers (`1_`, `2_`, `3_`) per house convention.
- Views and metric views are derived (never store business data twice).

### 3. UC tags (queryable ownership)

Applied to schema + every table/view/function/registered model:

| Tag key | Value(s) | Meaning |
|---|---|---|
| `bxc_project` | `reserving-workbench` | The owning project — the master label |
| `bxc_layer` | `raw` / `curated` / `semantic` / `engine` / `governance` | Pipeline role |
| `bxc_gen` | `gen1` | Tier — **flip to `gen2` on migration into the core** |
| `bxc_domain` | `reserving` | Business domain (matches the gen2 domain) |

> The workspace has a governed tag policy (reserving key `domain`); we namespace
> with the `bxc_` prefix to avoid colliding with it — same lesson as
> bricksurance-data-core's `bxc_` tag prefix.

Because ownership is a **tag**, "show me everything belonging to
reserving-workbench" is one query against `information_schema` /
`system.information_schema.*` tag views — not tribal knowledge.

### 4. In-product (the app tells you too)

`tools/build_asset_manifest.py` emits `app/server/data/asset_manifest.json`
(every deployed object: name, layer, gen, comment, tag set). The app's **About /
Assets** panel renders it, so a viewer inside the workbench sees exactly which
UC objects, jobs, Genie space, and serving endpoints this workbench owns.

### 5. Non-UC assets

- **App**: `reserving-workbench` (name carries the project).
- **Jobs / pipelines**: DAB `bundle.name: reserving-workbench` → dev-mode prefixes
  runs; job names prefixed `reserving-workbench —`.
- **Genie space / dashboard / serving endpoints**: names prefixed
  `Reserving Workbench —`.
- **MLflow experiment**: `/Shared/reserving_workbench`.

## Enforcement

`tools/smoke_test.py` asserts the convention holds: schema comment non-empty,
every object comment starts with `[reserving-workbench]`, `bxc_project` tag
present on all objects. A missing label fails the smoke test — labelling is part
of "done", not an afterthought.
