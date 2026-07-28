# Demo Run — Aug 5, 2026 · Hiscox Reserving Team Workshop

**Audience:** ~10–12 Hiscox reserving analysts (Daniel Tully, Jay Bishop). **Slot:**
10:00–11:00 "Databricks 101 & Reserving on Databricks (visionary / high-level)".
**Frame:** *A day in the life of a reserving actuary on Databricks* — reserving proper.
**App:** https://reserving-workbench-7474656169654171.aws.databricksapps.com

> This is the "art of the possible" beat — show the end-state, then (11:15+) the
> hands-on worked examples take over. Keep it a narrative, not a feature tour.

## One-line pitch
"Your whole quarterly reserving process — triangle to committee sign-off — as one
governed flow over a single source of truth, with the spreadsheet's flexibility but
none of its key-person risk, and an AI second set of eyes."

## Pre-flight (2 min before)
- App is live (scale-to-zero; open it once ~1 min ahead so compute is warm).
- Confirm the DEV workspace tab is open at Catalog Explorer →
  `lr_dev_aws_us_catalog.reserving_workbench` (for the "it's all real, governed" beat).
- Genie space "Ask the Triangle" open in a second tab.

## The run (≈12–15 min, leaves room for questions)

### 0 · Home — "the process, on the platform" (1 min)
Open **Day in the life**. Walk the 7-step table once: triangle → selection → methods →
estimates → validation → judgement → committee. "Every step governed, every number
reconciling, nothing in a spreadsheet nobody can audit." Point at the four headline
tiles (ultimate, IBNR, outstanding, validation breaches).

### 1 · The triangle is DERIVED, not stored (2 min)
Open **Triangle & LDF selection** (Commercial Property). 
- "This triangle isn't a copy — it's a *view* over the claim ledger, so it reconciles
  to the penny and can never drift. Change a claim, the triangle changes."
- Show the cumulative-paid grid (shaded = observed) and the **vol-wtd LDF** row.

### 2 · The override moment — THE beat (3 min)
Scroll to **Individual age-to-age factors**. 
- "Every accident year develops at ~1.67× at 12–24 months… except **AY2023 at 3.63×**"
  (the red cell). "One late-reported large loss distorts the empirical factor."
- Scroll to **Selection decision & audit trail**: prior → empirical (draft) → **elected
  (held prior)**. "The actuary overrode the empirical pick, held the prior pattern, and
  reserved the large loss individually — and every step is logged: who, when, why."
- "A black-box SQL script can't stop and let you do this. This can."
- Gesture at the **engine seam**: "and if your team prefers ResQ, the selection step
  is pluggable — Databricks preps the triangle, ResQ makes the pick, Databricks governs
  it. Same contract."

### 3 · Methods, side by side (1.5 min)
**Methodology library**: "Chain-ladder, BF, Mack, GLM, peer — each a governed model in
Unity Catalog, versioned and aliased. Swapping method writes a new estimate, never
overwrites — so bases are comparable." Then **Reserve estimates**: "Mack carries a
standard error that widens for the greenest years — that's your uncertainty for the
risk margin / risk adjustment."

### 4 · The workbench validates itself (1.5 min)
**Validation diagnostics**: "Actual-vs-expected on a rolling cohort. AY2023 Commercial
Property breaches tolerance (residual −3.05) — the same anomaly, surfaced automatically.
The platform tells you where to look."

### 5 · Judgement + committee + the AI actuary (3 min)
**Expert judgement**: "Every overlay audit-trailed — magnitude, rationale, the QRT cells
it touches, and approval routed by size (senior actuary / chief / board)."
**Committee & agent** → click **Generate committee brief**: the Senior Reserving Actuary
agent (real Claude, grounded on these tables) narrates the emerging trends. "Not a
chatbot — it reads the live diagnostics and briefs you like a colleague would. A second
set of eyes, not a replacement."

### 6 · Ask the Triangle (1.5 min)
**Ask the Triangle** (Genie): type *"Which cohorts breached validation tolerance?"* and
*"Total IBNR by line of business"*. "Plain English, governed SQL, same certified numbers
— for the semi-technical analyst who doesn't want to write code yet."

### 7 · It's all real & governed (1 min)
Flip to Catalog Explorer. Show the schema comment and the `bxc_*` tags on the tables.
"Everything you saw is a governed Unity Catalog object — commented, tagged, owned. In a
crowded workspace you always know what belongs to what."

## Talk-track anchors (Daniel's stated needs)
- **Practitioner workflows, not toy notebooks** → this IS the quarterly process.
- **Excel migration** → "this is what your workbook did — the triangle, the selection,
  the overlays — but governed, reproducible and answerable in Genie."
- **Entry-level AI for semi-technical actuaries** → the agent + Genie beats.

## Q&A armour
- *"Is the methodology certified?"* — No; it's illustrative, demonstrating the platform
  pattern. Your methods plug in as governed models — the workbench is methodology-agnostic.
- *"Our data isn't this clean."* — The triangle is a view; point it at your ledger (or
  federate to it) and it reconciles to whatever's there. Messy data is a DQ-expectations
  conversation, separate from the reserving logic.
- *"Does this replace ResQ / our tool?"* — No. The selection step is a pluggable seam;
  keep your tool for the pick and let Databricks own the data, governance and downstream.
- *"How does this feed Solvency II / IFRS 17?"* — The reserve estimate + cashflow pattern
  is a single-producer contract those regimes consume — compute the best estimate once.

## About this demo
Bricksurance SE is fictional; all data synthetic; the methodology is illustrative, not a
certified model. Every panel reads a real Unity Catalog table, view or function.
