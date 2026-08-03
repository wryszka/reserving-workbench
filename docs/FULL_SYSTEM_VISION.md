# Reserving Workbench — the full end-to-end system

The LDF-selection ask is one step in a quarterly reserving *process*. This is the
fuller system it sits inside — the reserving analogue of what pricing-workbench
does for pricing (ingestion → factors → model factory → deployment → review →
monitoring → governance). The point: **one platform does it all — data, engines,
agents, governance** — and where a customer already runs an external reserving
tool (LCP ResQ, Icecap, ResQ), we orchestrate and govern it rather than replace it.

## The lifecycle (8 stages, mirrors pricing-workbench)

| # | Stage | What it answers | Status |
|---|---|---|---|
| 1 | **Ingestion & triangle construction** | "Where does my triangle come from?" — ingest claims/premium (Federation to One Shield / Discovery), DQ expectations, versioned snapshots | next |
| 2 | **Triangle & LDF selection** | View triangle + empirical factors, compare to prior, elect/override — audited | ✅ built |
| 3 | **Methodology library** | CL / BF / Mack / GLM / peer, each a governed UC model | ✅ built |
| 4 | **Reserve estimates** | Ultimate / IBNR / outstanding per method, reconciling to the penny | ✅ built |
| 5 | **Validation & diagnostics** | Actual-vs-expected, tail-fit, residuals — the workbench validates its own methods | ✅ built |
| 6 | **Expert judgement** | Overlays, audit-trailed, magnitude-routed approval | ✅ built |
| 7 | **Roll-forward, ranges & committee sign-off** | "How do I get to a signed number?" — prior→new ultimate walk with drivers, stochastic reserve ranges (best estimate vs distribution), committee/board pack | partial → next |
| 8 | **Downstream & close** | Single-producer contract to SII technical provisions, IFRS 17 LIC, GL recon, capital model (e.g. Tyche); the reserving *close* cockpit (feeds SLA, run status, quarterly cadence) | specced (cashflow) → next |

Governance (audit, lineage, attestation) is a cross-cutting plane over all stages, not a stage.

**Built today:** the core modelling spine (2–6) + governance + the Senior Reserving Actuary agent
+ the reserve→QRT lineage. **The fuller system adds the bookends:** ingestion/DQ upstream (1),
and roll-forward + ranges + close-cockpit + board pack + regulatory/capital handoff downstream (7–8).

## The two talk tracks

### Primary — "we do it all"
Databricks reserving workbench = **data** (governed triangles derived from the claim ledger,
reconciling to the penny) + **engines** (the methodology library) + **agents** (Senior Reserving
Actuary, grounded on live tables) + **governance** (audit trail, lineage, expert judgement,
attestation). End to end, one platform, no data islands. This is the default pitch and what the
app demonstrates live.

### Secondary — "if you have ResQ, this is how we enrich your flow"
Don't rip out the tool the team knows. Databricks wraps it in three planes:

```
DATA plane (Databricks)         ORCHESTRATION                 GOVERNANCE plane (Databricks)
ingest → governed triangle  →   run ResQ as a job step:   →   ResQ's pick lands in
+ DQ expectations               hand it the prepared          selected_development_pattern
                                triangle, trigger the run,    (source_code = RESQ), same
                                read the pattern/ultimates    audit trail, lineage,
                                back                          attestation → same downstream
                                                              (SII / IFRS 17 / capital)
```

- **Databricks owns the data plane** — ingests, builds the governed triangle, applies DQ. ResQ
  reads a clean, versioned triangle instead of the team hand-assembling one.
- **Databricks orchestrates ResQ** as a task in the reserving workflow (Databricks Job / Workflow):
  pass the triangle (ODBC / file / API), trigger the ResQ run, read the selected pattern and
  ultimates back. ResQ becomes "just another engine" behind the platform.
- **Databricks owns the governance plane** — the ResQ-produced selection is a first-class citizen:
  same `selected_development_pattern` shape, `source_code = RESQ`, same audit trail, lineage,
  attestation, and the same single-producer contract downstream. The actuary keeps their tool;
  Databricks makes it governed, orchestrated and connected.

The data model already supports this: `development_selection_source` carries `RESQ` as a value,
so a ResQ pick needs no new schema — the writeback, governance and downstream code never care
which engine produced it. That is the whole point of the engine seam.

## Why this wins on the Hiscox account
- **Reserving team** (moved to LCP ResQ): "keep ResQ, we govern and orchestrate it, and give you
  the data + reporting + AI around it" — non-threatening, meets them where they are.
- **US Pricing team** (LDF off Discovery): the same triangle/selection machinery, framed for rate
  indications — build once, both teams consume, one governed platform.
- **The estate story:** reserving's reserve+cashflow is the single producer of technical provisions
  the Solvency II and IFRS 17 workbenches consume — kill the duplicated chain-ladder across three
  workbenches. That is the gen2 thesis, landed live.
