# Reserving Workbench — Aug 5 quick demo flow

**Room:** Hiscox reserving team (Daniel Tully, Jay Bishop). **Slot:** the 10:00 "art of the possible" hour.
**App:** https://reserving-workbench-7474656169654171.aws.databricksapps.com
**One line:** *"Your whole quarterly close — triangle to sign-off — on one governed platform, with an AI second set of eyes. You keep the judgement; it does the grunt work."*

**Before you start (2 min):** open the app once so it's warm · sidebar → **Reset demo** · leave **AI: cached** on. ~8 minutes of clicks below.

---

### 0 · Today (30s)
Land on **Today**. "Monday of close week. The triangle's already built — no weekend in Excel." Point at **⚠ Needs your attention → Commercial Property AY2023** and the four doors. Click **1 · Prepare**.

### 1 · Ingestion (1 min)
"Everyone's real pain: dirty data landing late." Show feeds + DQ pass %. The **Large-loss bordereau is quarantined** — a critical check failed. Click **Accept** on it → **blocked**: "resolve the quarantine first." *"The platform won't let you reserve on bad data."*

### 2 · Triangle & selection — the hero (3 min)
Nav → **Triangle & selection**. Show the triangle, then the individual factors: **AY2023 = 3.63× vs 1.67×** everywhere else (red). "One late large loss — I recognise it instantly."
- In the **Decision module**: edit the first factor **1.899 → 1.667**. Ultimate recomputes **live £14.74M → £14.44M**.
- Type a one-line rationale → **🔍 AI peer review**. A real Databricks agent reviews *your* pick and gives a verdict. *"An AI second-checking a qualified actuary — and I stay in control."*
- **Elect & save** → new audited row appears. "My old script couldn't stop to let me do that."

### 3 · Diagnostics (45s)
Nav → **Diagnostics**. AY2023 flagged (residual −3.05). Scroll to the **movement waterfall** — "why did reserves move, answered as data, not detective work."

### 4 · Workbench AI (1 min)
Nav → **Workbench AI**. Ask *"why did Commercial Property reserves move?"* → routes to **Movement Explainer** (green **agent endpoint** pill — real registered agent). Then *"draft the committee note"* → Committee-Note Drafter. *"The AI does the tedious 80%; I edit."*

### 5 · Governance & sign-off (1.5 min)
Nav → **Governance & sign-off**. Point at:
- **Triangle ↔ ledger: ties to the penny** — "reconciliation dread, gone."
- **Audit trail** + **AI activity** ("every model call, governed") + **model registry** (versioned).
- Click **Sign off** on a pending line → green. "I put my name on it — and the data version makes it reproducible when the auditor asks why."

### Close (30s)
"Platform found the problem, I made the judgement, the AI wrote it up, it's all governed and reproducible. Time back — and bulletproof at sign-off. This is your in-house process, on the platform you're already adopting: Excel / macros / FDW pain gone, your R and Python models run natively and governed, and the capital handoff to Tyche sits downstream."

---

**Know the room (from the notes):** Hiscox reserving runs **in-house models (Python/R)**, Excel/macros, SQL, monthly FDW loads — and **Tyche for capital** (stays; can't trigger on-prem from Databricks). They are **adopting Databricks** (Daniel is the champion). So frame this as *their process on the platform they're already on* — NOT "wrap around a tool you keep." Do **not** mention ResQ — that's other accounts. If you land on the "External engines" page, reframe it verbally as "plug in your own R/Python models, or hand off to Tyche," not ResQ.

**If asked:** *methodology?* illustrative, platform-agnostic — your own models plug in. *our data?* triangle's a view over your ledger (replaces the Excel/macro/FDW grind). *does the AI decide?* no — it drafts/reviews; you decide, every call audited. *capital?* Tyche stays; this feeds it downstream.

*Bricksurance SE is fictional; synthetic data. Reset demo in the sidebar between runs.*
