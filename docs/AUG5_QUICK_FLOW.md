# Aug 5 — Hiscox reserving: 9-minute run

**Room:** Daniel Tully, Jay Bishop + reserving team. **Slot:** the 10:00 hour.
**App:** https://reserving-workbench-7474656169654171.aws.databricksapps.com

**One line:** *"Data you trust, judgement that's yours, a story that writes itself, an audit trail for free."*

**The framing:** selecting factors is the bit you enjoy — and a tenth of your quarter. The rest is what changed in the data, why the triangle won't tie to the GL, who re-mapped a class, and writing the commentary. **That's** what we take away.

**Setup (2 min):** open the app once so it's warm · **Reset demo** · leave **AI: cached** on.

**SAY** = out loud. *KNOW* = presenter note only.

---

### 0 · Today (45s)
**SAY:** "Monday of close week. Triangle's already built and reconciling. The platform read the *whole book* and ranked it — not one cohort, all five lines." Point at CP **needs review**, two lines **restated**, PI **mapping change**.
*KNOW: this is the "we run 30+ classes" answer.*

### 1 · Trust the data (2.5 min) — **first peak**
**Tab 1 · What changed** — "First question of every close: what moved since September? 642 claims. **Six restated a cell already reported and signed off.**" Point at top row: **CP AY2023 · backdated · +£1.05m**. "Posted this quarter, dated into 2023. That row is the whole story you'll see on the triangle in a minute — found *before* any actuarial work."

**Tab 2 · Reconciliation** — "Claims paid ties to the general ledger. To the penny. No `_v7_FINAL.xlsx` anywhere."
*KNOW: real arithmetic against the ledger the triangle views. The one break is the bordereau, explained and owned.*

**Tab 3 · Data sign-off** — "Who says this data is fit to reserve on?" Click **Attest data** on **Large losses & bordereaux** → **refused**, names the failing control. "You can't declare bad data fit. Two jobs usually conflated: the data owner says *the data's right*, then I say *the judgement's mine*."

**Tab 4** (15s) — "Accuracy, completeness, appropriateness — the Solvency II dimensions. Reserving feeds the technical provisions, so your check suite *is* your evidence."

**Tab 6** (20s) — "PI was re-mapped this quarter. Every control ties, data's perfect — and two development patterns just broke for a reason no factor diagnostic explains. Normally a week of archaeology."

### 2 · Make the judgement (2 min) — **the pivot, not the climax**
**Triangle & selection.** Cumulative **paid**.
**SAY:** "AY2023 develops at **3.63×** where every other year is **1.67×** — the backdated loss we just traced. Any of you spots it. The 1.897 average is dragged up by that one outlier; 1.667 is roughly the average without it."
- Edit first factor **1.897 → 1.667** → ultimate recomputes live **£15.25m → £14.94m**
- Rationale → **AI peer review** (one click, don't dwell): "Second pair of eyes that challenges my pick and drafts the documentation. It challenges; **I decide**."
- **Select & save** → audited row. "My old script couldn't stop and let me do that."

### 3 · Explain the movement (1.5 min) — **second peak**
**Diagnostics** → **movement waterfall**: "'Why did reserves move?' — what your chief actuary opens every committee with. A decomposition: run-off, experience, assumptions, large losses, judgement. Not a weekend of detective work."
**Workbench AI** → ask *"why did Commercial Property reserves move?"* → then *"draft the committee note"*.
**SAY:** "The pack's first draft writes itself. You edit and own it — you don't assemble it. Tuesday evenings back."

### 4 · Sign off & reproduce (1 min)
**Governance & sign-off.** "Ties to the ledger to the penny. Every selection, judgement and model call logged. Every method version-controlled." Click **Sign off** → green. "I put my name on it."
Point at the data version: **"And the regulator asks in March about the Q2 number — one click, not spreadsheet archaeology."**

### 5 · Your own models (45s) — the differentiator for this room
**Engines & your models.** "Triangle mechanics aren't the argument — everyone has those. This is your own frequency-severity model, in R or Python, registered as a **first-class method** next to chain-ladder: same interface, versioned, reproducible. **Your methodology, our governance.** Off one analyst's laptop, with an audit trail you didn't build."

### Close (20s)
"**Data you trust, judgement that's yours, a story that writes itself, an audit trail for free.** Your process, on the platform you're already adopting."

---

**Know the room:** in-house **Python/R** models, Excel/macros, SQL, monthly FDW loads, **Tyche for capital** (stays). They're **adopting Databricks**; Daniel is the champion. Frame as *their process on the platform they're already on*. **Do not mention ResQ** — different accounts. On Engines, talk about *their* R/Python and Tyche downstream.

**If asked:**
- *methodology?* Illustrative, method-agnostic — your models register as first-class methods.
- *our data's a nightmare to extract?* Honest: that's the real project — connectors, a claim-movement model, control definitions. This is the **landed state**; once movements are on the platform those six controls are queries, not a team.
- *does the AI decide?* No — challenges and drafts; you decide, every call audited.
- *30+ classes?* Today's cockpit ranks the whole book; a new class is a row.
- *off-cycle what-ifs?* Scratch pad on Diagnostics — off the live triangle, writes nothing.
- *capital?* Tyche stays; this feeds it downstream.
- *tail factors?* Selected like any factor + a fitted curve beyond the triangle (demo-simplified).
- *gross or net?* Gross; net = same engine + recoveries downstream.
- *paid or incurred?* Cumulative paid; incurred adds case reserves.

**If it wobbles:** AI slow on first ask = endpoint cold-starting; keep **AI: cached** on (default). Tile errors = reload once or move on — each of the four beats stands alone. Attest doesn't refuse = already attested in a prior run; **Reset demo**. Reset odd = click again (idempotent).

*Bricksurance SE fictional; synthetic data; GBP. Reset demo between runs.*
