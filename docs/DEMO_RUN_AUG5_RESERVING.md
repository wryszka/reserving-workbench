# Demo Run — Aug 5, 2026 · Hiscox Reserving Team Workshop

**Audience:** ~10–12 Hiscox reserving analysts (Daniel Tully, Jay Bishop). **Slot:**
10:00–11:00 "Databricks 101 & Reserving on Databricks (visionary)". **Frame:** a day in
the life — reserving proper. **App:** https://reserving-workbench-7474656169654171.aws.databricksapps.com

> Tell a story, not a feature tour. One character, one close, one hero moment. Every
> beat below maps to a real screen. Pre-warm the AI cache (sidebar → the demo opens
> instantly) and hit Reset demo before you start.

## The story: "The Monday of close week — Sarah, senior reserving analyst"

### Beat 0 — Today (landing / close cockpit)
Open on **Today — Q4 close cockpit**. "It's the first Monday of Q4 close. Sarah opens
the workbench." Point at:
- **The triangle's already built and reconciling** — she didn't spend the weekend in Excel.
- **⚠ Needs your attention:** the platform has flagged ONE cohort — **Commercial Property
  AY2023, residual −3.05**. "She didn't eyeball 40 triangles. It told her where to look."
- Pending sign-offs, KPI tiles, and the "two ways in" (reserving vs pricing). Click **Review →**.

### Beat 1 — the judgment moment (Triangle & LDF selection)
The triangle + individual-factor grid. The AY2023 12→24m factor is **3.63× vs ~1.67×**
everywhere else, in red. "Sarah recognises it instantly — one late-reported large loss.
*This* is the actuarial work, not the janitorial work." (Cross-ref **Large-loss review** —
CLM-2023-ANOMALY, £1.05m, reserved individually — if asked "how do you know?")

### Beat 2 — the hero beat (the decision module, live)
In the **Decision module**: "Watch." Edit the first factor 1.899 → **1.667**. The **Selected
ultimate recomputes live £14.74M → £14.44M**, Δ-vs-prior updates. Type the rationale
("held prior 12–24m factor; AY2023 is one large loss, reserved individually"). Click
**Elect & save**. A new **MANUAL / PENDING_APPROVAL** row appears in the audit trail.
"Her old process couldn't stop to let her do that. This one records who, when, and why."

### Beat 3 — the AI does the grunt work (Workbench AI)
Go to **Workbench AI**. Type *"why did Commercial Property reserves move this quarter?"* →
the supervisor routes to the **Movement Explainer**, which narrates the roll-forward. Then
*"draft the committee note"* → the **Committee-Note Drafter**. "Sarah edits; she doesn't
author from a blank page. The AI does the tedious 80% so she does the 20% she trained for.
A second set of eyes — she stays in control." (Note the routing reason + cached/live badge.)

### Beat 4 — best estimate AND uncertainty (Reserve ranges)
**Reserve ranges**: CoV and percentiles per line. "When the board asks 'how confident are
you?', she has the range — and it's the same number that becomes the Solvency II risk margin
and IFRS 17 risk adjustment. One producer, many consumers."

### Beat 5 — sign-off without fear (Governance & sign-off)
**Governance & sign-off**. Point at:
- **Triangle ↔ ledger: ties to the penny** — the reconciliation dread, gone.
- The **audit trail** — every selection, judgement, agent call, logged.
- The **model registry** — every method a versioned UC model.
- Click **Sign off** on a pending line → green confirmation. "She puts her name to the
  number. The data version makes it reproducible — when the auditor asks 'why did you
  override AY2023 property?', she clicks, and shows them. Two years ago that was a frantic
  email search."

### Close
"That's a close week: the platform found the problem, Sarah made the judgment, the AI wrote
it up, and it's all governed and reproducible. Time back, and bulletproof at sign-off."

## Daniel's stated needs → where they land
- **Practitioner workflows, not toy notebooks** → the whole Sarah flow is her actual quarter.
- **Excel migration** → "this is what your workbook did — triangle, selection, overlays — governed and reproducible."
- **Entry-level AI + Genie for semi-technical actuaries** → Workbench AI (routed specialists) + Ask the Triangle (Genie) + the Learn page.

## Logistics
- Pre-warm cache + Reset demo before the room. Cache toggle in the sidebar (show "live" once for authenticity, then back to "cached").
- If the app is cold, the first call wakes it (~20s) — open Today a minute early.
- Afternoon deep-dive: External engines (ResQ) for the "keep your tool, we govern it" conversation, and the Learn page.

## About this demo
Bricksurance SE is fictional; synthetic data; methodology illustrative, not certified. Every panel reads a real Unity Catalog table, view or function.
