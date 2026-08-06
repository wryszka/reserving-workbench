# Reserving Workbench — Demo Guide

**App:** https://reserving-workbench-7474656169654171.aws.databricksapps.com · **Entity:** Bricksurance SE (fictional; synthetic data; **reports in GBP**) · on Databricks (dev).

The reserving analogue of the pricing workbench: the full quarterly reserving process — **data → engines → agents → governance** — on one platform, with human-in-the-loop decisions and a real AI layer. Three timed runs (5 / 10 / 15 min) and a full feature list.

> **The one-line thesis.** *"Data you trust, judgement that's yours, a story that writes itself, an audit trail for free."*
>
> Selecting factors is the part actuaries enjoy — and about a tenth of a close. The rest is plumbing: what changed in the data, why the triangle won't tie to the GL, who re-mapped a product code, and writing the movement commentary. **That** is what we remove. Judgement is the pivot of the story, not its peak; the peaks are reconciliation and narrative.

> **Language key.** **SAY** lines are audience-facing script. *KNOW* lines are presenter notes — never say the jargon out loud.
>
> **Banned out loud:** Unity Catalog / UC, Genie, serving endpoint, HITL, seam, Agent Framework, writeback. **Say instead:** "registered and version-controlled", "ask the data in plain English", "you approve it and it's recorded", "swap in your own engine, same governed result".

> **Before any demo (2 min):** open the app once so it's warm · sidebar → **Reset demo** · leave **AI: cached** on (routed answers return instantly; the model endpoint cold-starts ~30-60s if you switch to live). Story: *Sarah, a senior reserving analyst, on the Monday of Q4 close.*

> **The four doors** (on the landing "Today" page) are the workflow, in story order: **1 · Trust the data** → **2 · Make the judgement** → **3 · Explain the movement** → **4 · Sign off & reproduce.**

---

## ⏱ 5-minute run — the hero loop

Trust the data → make the judgement → explain the movement → sign off & reproduce.

**1 · Today (30s)**
**SAY:** "Monday of close week. The triangle is already built and reconciling — no weekend in Excel, no `_v7_FINAL.xlsx`. And the platform has read the *whole book* and ranked it by what needs me." Point at the book table: Commercial Property flagged (validation), two lines showing **restated** data, Professional Indemnity showing a **mapping change**.
*KNOW: this is the answer to "we run 30+ classes, does this scale?" — every flag is a query over a governed table, so it works the same at 5 or 50 lines.*

**2 · Trust the data (1.5 min)** — *the first peak*
Open **1 · Trust the data**. Six tabs, in the order a real close asks them.
- Tab **1 · What changed** — **SAY:** "First question of every close: what moved since last quarter? 642 claims. And these six restated a cell that was already reported *and signed off*." Point at the top row: **Commercial Property AY2023, backdated transaction, +£1.05m**. "Any analyst spots the problem — the platform traced it to the source record."
- Tab **2 · Reconciliation** — **SAY:** "Claims paid ties to the general ledger to the penny. I never fight the GL again." *KNOW: this is real arithmetic against the same ledger the triangle is a view over — re-runnable, not a label. One break exists and is explained and owned.*
- Tab **3 · Data sign-off** — **SAY:** "The data owner attests each domain before I do any actuarial work." Click **Attest data** on **Large losses & bordereaux** → **refused**, naming the failing control. "It won't let anyone declare bad data fit."
- *(If time: tab 4 shows the checks grouped as accuracy / completeness / appropriateness — the Solvency II dimensions, because reserving feeds the technical provisions.)*

**3 · Make the judgement (1.5 min)** — *the pivot, not the peak*
Open **Triangle & selection**. **SAY:** "Cumulative paid. AY2023 develops at **3.63×** where every other year is **1.67×** — that's the backdated loss we just traced. The 1.897 average is dragged up by that one outlier; 1.667 is roughly the average without it."
- Edit the first factor **1.897 → 1.667** — ultimate recomputes live **£15.25m → £14.94m**.
- Type a rationale → click **AI peer review**. **SAY:** "A second pair of eyes that challenges my pick and drafts the documentation. It challenges; **I decide**."
- **Select & save** → new audited row.

**4 · Explain the movement (1 min)** — *the second peak*
Open **Diagnostics**. Scroll to the **movement roll-forward**. **SAY:** "'Why did reserves move?' — the question the chief actuary always opens with. Answered as a decomposition, not a weekend of detective work." Then in **Workbench AI**, ask *"why did Commercial Property reserves move?"* → the **Movement Explainer** narrates it in committee language.

**5 · Sign off & reproduce (30s)**
Open **Governance & sign-off**. **SAY:** "Reconciled, audited, every method version-controlled. I sign off." Click **Sign off**. Then point at the data version: **"The regulator asks in March about the Q2 number — one click, not spreadsheet archaeology."**

*Close on the thesis:* **"Data you trust, judgement that's yours, a story that writes itself, an audit trail for free."**

---

## ⏱ 10-minute run — the full data front door + the drafter

1. **Today** (1 min) — as above, plus the KPI strip and sign-off status.
2. **Trust the data** (3 min) — all six tabs. Add: tab **4 · Quality checks** grouped by Solvency II dimension; tab **5 · Feeds & timeliness** (click **Accept** on the quarantined bordereau → **blocked**); tab **6 · Class mapping** — **SAY:** "Professional indemnity was re-mapped this quarter. Every control ties, the data is perfect — and two development patterns just broke for a reason no factor diagnostic will ever explain. That's usually a week of archaeology."
3. **Make the judgement** (2 min) — the hero loop + AI peer review + **Select & save**.
4. **Explain the movement** (2.5 min) — roll-forward waterfall, then give the **Committee-Note Drafter** a full moment: **SAY:** *"The committee pack's first draft writes itself. Tuesday evenings back."* Edit a line to make the point that you own it.
5. **Sign off & reproduce** (1 min) — reconciliation, audit trail, AI-activity log, **Sign off**, reproduce-as-at.
6. **Plain-English question** (30s) — one-liner: ask *"total IBNR by line of business"* and read the answer. *KNOW: Genie via the Conversation API.*

*Workbench AI tiles: 60-second sweep only.* The two shown live are **Movement Explainer** and **Committee-Note Drafter**.

---

## ⏱ 15-minute run — the full quarter

Everything above, in the same story order, plus:

7. **Methods & estimates** (1.5 min) — the method library, each **version-controlled and registered**; estimates reconciling to the penny; **reserve ranges** (CoV + percentiles) — uncertainty that **informs** the Solvency II risk margin and the IFRS 17 risk adjustment.
8. **Diagnostics — the rest** (1 min) — actual-vs-expected (AY2023 flagged, a large **positive** residual — it developed above the norm), large-loss review, and the **scratch pad**: **SAY:** "The CFO asks what two extra points of claims inflation would do. Seconds, off the live triangle — and it writes *nothing*. Exploration and decisions stay clearly apart."
9. **Expert judgement** (1.5 min) — raise a judgement; the size **routes the approval**: **under £1m → senior actuary; £1m–£10m → chief actuary; over £10m → board**. Approve it — maker/checker, audited.
10. **Engines & your models** (2 min) — ***the deliberate differentiation beat, not an afterthought.***
    **SAY:** "The triangle mechanics aren't the argument — everyone has those. Here's your own frequency-severity model, in R or Python, registered as a **first-class method** right next to chain-ladder: same interface, versioned, aliased, reproducible. **Your methodology, our governance.** It comes off one analyst's laptop and gains an audit trail you didn't have to build." Then the plug-in point: "or keep the tool your team already uses — we do the data in, the governance around, and the narrative out. The engine is a step."
11. **Learn** tile (green, sidebar) — plain-language walkthrough + Q&A.

---

## Persona pain → what to point at

| Their pain | Feature |
|---|---|
| "What changed in the data?" at close open | **Data-diff since last quarter** (Trust the data, tab 1) |
| Triangle never ties to the GL; days lost | **Ingestion reconciliation** + ledger-view triangle, penny reconciliation |
| Reserving on data nobody's approved | **Data sign-off gate** (tab 3) — refuses while a control is red |
| "Why did it move?" panic | **Movement waterfall + Movement Explainer** |
| Committee pack eats evenings | **Committee-Note Drafter** |
| Audit archaeology months later | **Reproduce-as-at** + full audit trail |
| `_v7_FINAL.xlsx` version chaos | Single governed table, audited selections |
| Key-person risk in macros / one analyst's script | **Registered versioned methods** (incl. their own model) + Learn tile |
| Bad data found too late | **DQ quarantine + mapping change alerts** upstream |
| Off-cycle "what if?" asks | **Scratch pad** (Diagnostics) — answers in seconds, writes nothing |
| "We run 30+ classes" | **Book cockpit** on Today — every line ranked by what needs a human |

---

## Full feature list

| Area | Feature | Interactive? |
|---|---|---|
| **Today** | Book cockpit: every line ranked by validation / restated / mapping / large-loss flags, data-gate status, four doors, KPIs | ✅ navigate |
| **Trust the data · 1** | Data movement since prior close by type; the six movements that **restate** an already-reported cell | view |
| **Trust the data · 2** | Reconciliation to the source of record (real arithmetic vs the claim ledger), explained breaks | view |
| **Trust the data · 3** | **Data sign-off gate** — data owner attests per domain; refused while a critical control fails | ✅ act |
| **Trust the data · 4** | DQ checks grouped by Solvency II dimension (accuracy / completeness / appropriateness) | view |
| **Trust the data · 5** | Feeds: rows, months present vs expected, arrival vs SLA, quarantine **blocks acceptance** | ✅ act |
| **Trust the data · 6** | Source-class → reserving-class mapping with the prior close alongside; changes flagged | view |
| **Triangle** | Cumulative-**paid** triangle — a live view over the claim ledger; reconciles to the penny | view |
| **Selection** | Averaging-basis toggle · per-factor override · live ultimate/IBNR + change vs prior · **Select & save** (audited) | ✅ act |
| **AI peer review** | An assistant independently challenges the actuary's factor selection and drafts the rationale | ✅ act |
| **Methods** | Method library incl. **the customer's own model as a first-class method**, each version-controlled & registered | view |
| **Estimates / Ranges** | Ultimate/IBNR/outstanding per AY × method; CoV + percentiles informing SII risk margin / IFRS 17 risk adjustment | view |
| **Diagnostics** | Actual-vs-expected · movement roll-forward · large-loss review | view |
| **Scratch pad** | Off-cycle what-if (inflation / tail / extra large loss) — **writes nothing** | ✅ act |
| **Expert judgement** | Raise → size-routed approval → approve; maker/checker, audited | ✅ act |
| **Committee** | Reserves by line of business + a Senior Reserving Actuary brief | ✅ agent |
| **Workbench AI** | Supervisor + 5 specialists on a registered model endpoint; each grounded on live tables | ✅ act |
| **Plain-English data Q&A** | Ask a question, get governed SQL + the answer *(presenter: Genie / Conversation API)* | ✅ act |
| **Governance** | Reconciliation to the penny · full audit trail · AI-activity log · method register · **Sign-off** + reproduce-as-at | ✅ act |
| **Engines & your models** | Own R/Python model registered as a method; external-tool plug-in point → same governed record | view |
| **Platform** | AI cache (cached/live toggle) · demo reset · Learn tile · asset labelling | ✅ act |

---

## If something goes wrong (fallback)

- **AI answer is slow / spins on first ask** — the model endpoint is scale-to-zero and cold-starting (~30-60s). With **AI: cached** on (sidebar, default), the pre-run questions answer instantly; if you switched to **live**, either wait ~1 min or toggle back to **cached** and re-ask. Each answer shows how it was served (agent endpoint / cached / fallback) — a "fallback" tag is fine, it's still a real model answer.
- **A page shows an error or a number looks empty** — the app SP occasionally drops off the SQL warehouse. Reload once; if it persists, move on and come back. **The run still works without any single tile:** the story's spine is Trust-the-data → selection → movement → sign-off, and each of those four is independently demonstrable.
- **Reset didn't fully restore** — click **Reset demo** again; it's idempotent. If a live selection or attestation you created is still showing, that's harmless — it just means the audit trail has your demo action in it. (Worst case, narrate it: "that's my action from the last run, still audited.")
- **The attest button doesn't refuse** — you may already have attested that domain in a prior run; click **Reset demo** and retry on **Large losses & bordereaux**.
- **Genie question returns no rows** — the text answer still carries the figures; read those. Re-ask a simpler phrasing if needed.

---

## Two audiences, one asset
- **Reserving actuaries** (e.g. Hiscox reserving) — book the reserve: trust the data, select, judge, explain, sign off. Frame as *their in-house process on the platform they're adopting* — the Excel/data-wrangling grind gone; their own R/Python models registered as first-class methods; capital (e.g. Tyche) sits downstream. **Do not pitch an external reserving tool to this room.**
- **Pricing analysts** (e.g. Hiscox US) — develop losses to ultimate for the rate **indication**: the same triangle machinery, feeding the indicated rate, not the balance sheet.

## Q&A armour
- *Methodology certified?* No — illustrative, method-agnostic; your own models plug in as first-class methods.
- *Our data isn't this clean?* The triangle is a live view over your ledger — it reconciles to whatever's there. And the six data controls are exactly the machinery for *finding* the mess rather than being surprised by it.
- ***"Our data is a nightmare to even extract."*** Honest answer: that's the real work, and it's an implementation project — connectors, a claim-movement model, and the control definitions. What you're seeing is the **landed state**: once the movements are on the platform, the six controls are queries, not a team. We'd scope the extraction properly rather than pretend it's free.
- ***We run 30+ classes — does this scale?*** The Today cockpit ranks the whole book by what needs a human; adding a class adds a row, not a spreadsheet. The flags are queries over governed tables.
- ***What about off-cycle and what-if asks?*** There's a scratch pad on Diagnostics that answers them off the live triangle and writes nothing — so exploration never contaminates the booked number.
- *Does the AI decide?* No — it challenges, drafts and reviews; the actuary decides, and every call is recorded.
- *Replace our tool / our models?* No. Your model gets registered as a first-class method — same interface, versioned and governed. The engine is a pluggable step; we own the data and governance around it.
- *Paid or incurred triangle?* This one is **cumulative paid**; incurred is the same structure with case reserves added — both are just views over the ledger.
- *How do you pick tail factors?* Selected the same way as any age-to-age factor (with a fitted curve beyond the observed triangle where needed) and recorded on the pattern; a demo simplification here — your tail methodology plugs in.
- *Gross or net of reinsurance?* This shows **gross** reserves; net is the same engine with reinsurance recoveries applied downstream (a modelled extension, not shown today).
- *Where do the Bornhuetter-Ferguson priors (expected loss ratios) come from?* From planning / pricing loss ratios in the real world; here they're a synthetic a-priori — the point is the method blends that prior with emerging experience, weighted toward the prior for immature years.

*All data synthetic; Bricksurance SE fictional; figures in GBP. Reset demo in the sidebar between runs.*
