# Demo Run — Aug 6, 2026 · Hiscox US Pricing — LDF Review

**Audience:** Hiscox US Pricing (John McGinn, Richard Derr; +Scott Klepetka, Imogen Hirsh).
**Origin:** 23 Jul call — migrate the LDF process off the "Discovery" SQL-Server monolith
into a staged, transparent, stoppable workflow with a human override. **Review agreed for
today.** **App:** https://reserving-workbench-7474656169654171.aws.databricksapps.com

> **Framing for THIS room: loss development for RATE INDICATIONS, not reserving.**
> Pricing actuaries develop historical losses to ultimate to compute the loss cost /
> indicated rate. Same triangle machinery as the reserving team uses — that shared-tool
> point is a feature, not a coincidence — but do NOT call this "reserving" to John's team.

## What John asked for (map every ask to a beat)
1. **Triangle visualization** — view losses + empirical LDFs before selection → §1.
2. **Comparison capability** — empirical vs a previously-selected set → §2.
3. **Decision module** — elect empirical vs hold prior → §2.
Plus: **R integration** for indications, and **Federation** to read Discovery loss data.

## Opinionated spine (ONE architecture, not the five options from discovery)
**Federation reads Discovery → triangle & empirical LDFs in Databricks → select
(Databricks or ResQ) → elect/override, audited → feeds the indication.** Name the
runners-up (Lakeflow Designer for visual-first; notebook widgets for analysts) as
*persona choices*, not undecided options.

## Pre-flight
- App warm (open ~1 min ahead). Genie tab open. Have the `fn_empirical_ldf` SQL handy
  in a workspace query tab for the "it's governed SQL" beat.

## The run (≈15 min)

### 0 · Reframe up front (1 min)
"You develop losses to ultimate to price. The LDF selection is an *assumption feeding the
indicated rate* — and today it's a giant Discovery SQL script you can't stop or see into.
Here's that same step, staged and stoppable, on Databricks."

### 1 · Triangle & empirical LDFs — ask #1 (3 min)
Open **Triangle & LDF selection** (Commercial Property).
- Cumulative-paid triangle (shaded = observed) + the **vol-wtd LDF** row. "Your triangle
  and your empirically-calculated factors, before anyone picks anything."
- "This triangle is a *view* over the loss ledger — reconciles to the penny, no giant
  script, no copy to drift. Today it reads synthetic data; via **Lakehouse Federation**
  it reads Discovery directly — no ingestion project, no waiting on One Shield validation."

### 2 · Compare vs prior + decide — asks #2 and #3 (4 min)
- **Individual age-to-age factors**: AY2023 at **3.63×** (red) vs ~1.67× elsewhere. "A
  single late-reported large loss distorts the empirical factor for that year."
- **Selection decision & audit trail**: prior → empirical (draft) → **elected: held prior**.
  "Here's your comparison of the empirical pattern against the previously-selected set —
  and the decision module: elect the empirical factors, or hold the prior. This one held
  the prior for the anomalous step, with a logged reason. That's the stop-and-override
  moment your current process can't do."
- Every election is a row: who / when / source / old vs new / why. "Fully audited."

### 3 · The ResQ / external-tool seam (2 min)
Point at the **engine seam** diagram. "The selection step is pluggable. If Pricing wants
to keep an external tool, Databricks preps the triangle, the tool makes the pick, and we
read it back with the same governance — `source = RESQ`. You're not locked in either way."

### 4 · Governed, not a black box (2 min)
In the workspace query tab: `SELECT lr_dev_aws_us_catalog.reserving_workbench.fn_empirical_ldf('COMMERCIAL_PROPERTY', 1)`.
"The empirical factor is a governed UC function — callable from SQL, the app, Genie —
so 'the factor' means one thing everywhere, versioned in Unity Catalog. Contrast one
5,000-line script where you can't find where anything happens."

### 5 · R integration (2 min)
"You build indications in R. Databricks runs R natively — as a notebook or a task in the
job — so your indication code runs unchanged, reading the *selected* pattern from the same
governed table." *(If John sent the sample R code: show it running as a task. If not:
show the pattern and confirm we'll wire their code next — the seam is ready.)*

### 6 · Ask the Triangle (1 min, optional)
Genie: *"Show the cumulative paid triangle for Commercial Property"* — "self-serve for the
analysts, governed SQL under the hood."

## Close
"Federation → triangle & empirical LDFs → compare & elect (audited) → your R indication —
one staged, transparent, stoppable flow. Next: you send the script split into the three
parts and a sample R indication, and we wire this to Discovery for real."

## Open items to confirm live
- [ ] Split LDF script (3 parts: ingest/prep · selection · output) — **still owed by John/Richard.**
- [ ] Sample R indication code — **still owed.** (Chase via Tamika; no emails per Laurence.)
- [ ] Federation connection to Discovery — demo shows the pattern on synthetic; live wire-up
      is the follow-up once loss data / access is confirmed.

## Q&A armour
- *"This looks like reserving."* — Same triangle math; you're using it for indications, they
  for booked reserves. Build it once, both consume it — that's the point.
- *"Our loss data can't move yet."* — Correct; Federation reads Discovery in place, no
  ingestion. The triangle view sits on top of whatever it reads.
- *"Can we keep our R / external tool?"* — Yes. R runs natively; the selection step is a
  pluggable seam for ResQ/equivalent.

## About this demo
Bricksurance SE is fictional; all data synthetic; methodology illustrative, not certified.
Every panel reads a real Unity Catalog table, view or function.
