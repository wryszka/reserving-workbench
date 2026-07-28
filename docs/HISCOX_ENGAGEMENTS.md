# Hiscox engagements — one workbench, two back-to-back events

This workbench is the shared asset behind two Hiscox sessions on consecutive days.
Same build, two audiences, two framings.

## Aug 5, 2026 — Hiscox **Reserving team** workshop (Daniel Tully, Jay Bishop)
- All-day, ~10–12 reserving analysts. Databricks office (Tamika hosting). Prep
  check-in Tue **Aug 4** (Laurence + Daniel). Materials to Daniel/Jay beforehand.
- Agenda (from 21 Jul planning call):
  - **10:00–11:00 — "Databricks 101 & Reserving on Databricks" (visionary/high-level).**
    ← *This workbench is the centrepiece here: a "day in the life of a reserving
    actuary on Databricks" — the end-to-end governed process, Art of the Possible.*
  - 11:15–12:30 — hands-on worked examples (loss ratios, pipeline reporting layers).
  - Afternoon — technical deep-dive + attendees' own use cases.
- What Daniel has repeatedly asked for (use as design pressure):
  - **Practitioner-focused, real reserving workflows** — not toy notebooks. The
    workbench walks the actual quarterly process end to end.
  - **Excel/VBA migration** story — "this is what your spreadsheet did, governed."
  - **Entry-level AI agents + Genie** for semi-technical actuaries — the Senior
    Reserving Actuary agent + "Ask the Triangle" Genie space answer this directly.
- Framing for this room: **reserving proper** (booking reserves, quarterly close,
  committee, governance) — title it as reserving. This is their day job.

## Aug 6, 2026 — Hiscox **US Pricing** LDF review (John McGinn, Richard Derr)
- The **LDF-selection module** specifically: triangle → empirical LDFs →
  compare-to-prior → elect/override → audit. Plus R-integration options and the
  Federation-to-Discovery read path. See `HISCOX_LDF.md`.
- Framing for this room: **loss development for rate indications** — pricing
  actuaries develop losses to ultimate to compute loss cost / indicated rate.
  Same triangle machinery as reserving, different downstream consumer. Do NOT
  call it "reserving" to this audience.

## Why one asset serves both
Loss-development triangles + factor selection are a **shared technique**. The
reserving team books reserves off it; the pricing team feeds rate indications off
it. Building it once on the platform, governed identically, consumed by both, is
itself the story — and the gen2 single-producer thesis landed live on the account.

## Guardrails (both rooms)
- Bricksurance SE is fictional; synthetic data throughout; "About this demo"
  disclaimer visible. Never mirror Hiscox's real estate (see
  [[feedback-no-real-customer-parallels]]) — their real LMR unit was the reason
  the data-core "London Market & Re" unit was genericized.
- Runs for real on Databricks (Federation/Jobs/MLflow/UC/Apps), not faked.
