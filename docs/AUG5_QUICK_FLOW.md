# Reserving Workbench — Aug 5 quick demo flow

**Room:** Hiscox reserving team (Daniel Tully, Jay Bishop). **Slot:** the 10:00 "art of the possible" hour.
**App:** https://reserving-workbench-7474656169654171.aws.databricksapps.com

**The one line:** *"Data you trust, judgement that's yours, a story that writes itself, an audit trail for free."*

**The framing that lands:** selecting factors is the bit you enjoy — and about a tenth of your quarter. The rest is what changed in the data, why the triangle won't tie to the GL, who re-mapped a class, and writing the movement commentary. **That's** what we take away. Judgement stays yours; it's the pivot of the story, not the climax.

**Before you start (2 min):** open the app once so it's warm · sidebar → **Reset demo** · leave **AI: cached** on. ~9 minutes of clicks below.

**SAY** = say it out loud. *KNOW* = presenter note, don't say the jargon.

---

### 0 · Today — the book (45s)
Land on **Today**.
**SAY:** "Monday of close week. The triangle is already built and reconciling. And the platform has read the *whole book* and ranked it by what needs a human — not one cohort, all five lines." Point at: Commercial Property **needs review**, two lines with **restated** data, Professional Indemnity with a **mapping change**.
*KNOW: this is the "we run 30+ classes" answer — the flags are queries over governed tables, so it's the same at 50 lines.*

### 1 · Trust the data (2.5 min) — **the first peak**
Click **1 · Trust the data**. Six tabs, in the order a real close asks them.

**Tab 1 · What changed** — **SAY:** "The first question of every close, and the one that's hardest from a spreadsheet: what moved since September? 642 claims moved. And **six of them restated a cell that was already reported and signed off last quarter**." Point at the top row: **Commercial Property AY2023 · backdated transaction · +£1.05m**. "Posted this quarter, dated into 2023. That single row is the whole story of what you'll see on the triangle in a minute — and we found it *before* any actuarial work."

**Tab 2 · Reconciliation** — **SAY:** "Claims paid movements tie to the general ledger. To the penny." *KNOW: real arithmetic against the same ledger the triangle is a view over — you could re-run it. The one break is the bordereau, explained and owned; an explained break is a control, an unexplained one is a risk.*
**SAY:** "No `_v7_FINAL.xlsx` anywhere in this picture."

**Tab 3 · Data sign-off** — **SAY:** "Who says this data is fit to reserve on? The data owner attests it, per domain, before I start." Click **Attest data** on **Large losses & bordereaux** → it's **refused** and names the failing control. **SAY:** "You can't declare bad data fit. Two different jobs that usually get conflated: the data owner says *the data is right*, then I say *the judgement is mine*."

**Tab 4 · Quality checks** (20s) — **SAY:** "Grouped as accuracy, completeness and appropriateness — the Solvency II dimensions. Reserving feeds the technical provisions, so your check suite *is* your Article 19 evidence."

**Tab 6 · Class mapping** (20s) — **SAY:** "Professional indemnity was re-mapped this quarter. Every control ties, the data's perfect — and two development patterns just broke for a reason no factor diagnostic will ever explain. That's normally a week of archaeology; here it's a row on a screen."

### 2 · Make the judgement (2 min) — **the pivot**
Nav → **Triangle & selection**. Cumulative **paid**.
**SAY:** "AY2023 develops at **3.63×** where every other year is **1.67×** — that's the backdated loss we just traced. Any of you would spot it. The 1.899 average is dragged up by that one outlier; 1.667 is roughly the average without it."
- Edit the first factor **1.899 → 1.667** → ultimate recomputes live **£14.74m → £14.44m**.
- Rationale → **AI peer review**. **SAY:** "A second pair of eyes that challenges my pick and drafts the documentation. It challenges; **I decide**." *(One click, don't dwell.)*
- **Select & save** → audited row. **SAY:** "My old script couldn't stop and let me do that."

### 3 · Explain the movement (1.5 min) — **the second peak**
Nav → **Diagnostics**, scroll to the **movement waterfall**.
**SAY:** "'Why did reserves move?' — the question your chief actuary opens every committee with. Here it's a decomposition: expected run-off, experience, assumptions, large losses, judgement. Not a weekend of detective work."
Nav → **Workbench AI**, ask *"why did Commercial Property reserves move?"* → **Movement Explainer** narrates it. Then *"draft the committee note"* → **Committee-Note Drafter**.
**SAY:** "The pack's first draft writes itself. You edit it and own it — you don't assemble it. Tuesday evenings back."

### 4 · Sign off & reproduce (1 min)
Nav → **Governance & sign-off**.
- **SAY:** "Triangle ties to the ledger to the penny. Every selection, judgement, sign-off and model call logged. Every method version-controlled."
- Click **Sign off** on a pending line → green. **SAY:** "I put my name on it."
- Point at the data version. **SAY:** "**And the regulator asks in March about the Q2 number — one click, not spreadsheet archaeology.**"

### 5 · Your own models (45s) — the differentiator for this room
Nav → **Engines & your models**.
**SAY:** "The triangle mechanics aren't the argument — everyone has those. This is your own frequency-severity model, in R or Python, registered as a **first-class method** right next to chain-ladder: same interface, versioned, aliased, reproducible. **Your methodology, our governance.** It comes off one analyst's laptop and gains an audit trail you didn't have to build."

### Close (20s)
**SAY:** "**Data you trust, judgement that's yours, a story that writes itself, an audit trail for free.** Your process, on the platform you're already adopting — the Excel and data-wrangling grind gone, your own models running natively and governed, and the capital handoff sitting downstream."

---

**Know the room (from the notes):** Hiscox reserving runs **in-house models (Python/R)**, Excel/macros, SQL, monthly FDW loads — and **Tyche for capital** (stays; can't trigger on-prem from Databricks). They are **adopting Databricks** (Daniel is the champion). Frame this as *their process on the platform they're already on* — NOT "wrap around a tool you keep". **Do not mention ResQ** — that's other accounts. On the Engines page, talk about *their* R/Python models and Tyche downstream.

**If asked:**
- *methodology?* Illustrative, method-agnostic — your own models register as first-class methods.
- *our data is a nightmare to extract?* Honest: that's the real project — connectors, a claim-movement model, control definitions. What you're seeing is the landed state; once movements are on the platform, those six controls are queries, not a team.
- *does the AI decide?* No — it challenges and drafts; you decide, every call audited.
- *30+ classes?* The Today cockpit ranks the whole book; a new class is a row, not a spreadsheet.
- *off-cycle what-ifs?* Scratch pad on Diagnostics — answers off the live triangle, writes nothing.
- *capital?* Tyche stays; this feeds it downstream.
- *tail factors?* Selected like any factor, plus a fitted curve beyond the triangle (demo-simplified).
- *gross or net?* Gross here; net = same engine + reinsurance recoveries downstream.
- *paid or incurred?* Cumulative paid; incurred is the same structure with case reserves added.

**If something wobbles:** AI slow on first ask = endpoint cold-starting (~30-60s); keep **AI: cached** on (default) and it's instant. A tile errors = reload once, or move on — the spine is *trust the data → judgement → movement → sign-off* and each beat stands alone. Attest doesn't refuse = you already attested it in a prior run; **Reset demo** and retry. Reset misbehaves = click it again (idempotent).

*Bricksurance SE is fictional; synthetic data; figures in GBP. Reset demo in the sidebar between runs.*
