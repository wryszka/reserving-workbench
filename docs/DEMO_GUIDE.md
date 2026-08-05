# Reserving Workbench — Demo Guide

**App:** https://reserving-workbench-7474656169654171.aws.databricksapps.com · **Entity:** Bricksurance SE (fictional; synthetic data; **reports in GBP**) · on Databricks (dev).

The reserving analogue of the pricing workbench: the full quarterly reserving process — **data → engines → agents → governance** — on one platform, with human-in-the-loop decisions and a real AI layer. Three timed runs (5 / 10 / 15 min) and a full feature list.

> **Language key.** Plain lines are what you can say to the room. *(Presenter note: …)* lines are for you — don't say the jargon (Genie / Conversation API / metric view / seam) out loud; say "ask in plain English", "one governed definition", "plug-in point".

> **Before any demo (2 min):** open the app once so it's warm · sidebar → **Reset demo** · leave **AI: cached** on (routed answers return instantly; the model endpoint cold-starts ~30-60s if you switch to live). Story: *Sarah, a senior reserving analyst, on the Monday of Q4 close.*

> **The four doors** (on the landing "Today" page) are the workflow: **1 · Prepare** (ingestion & data quality) → **2 · Select** (triangle & selection) → **3 · Analyse** (methods, ranges & diagnostics) → **4 · Sign off** (governance & sign-off).

---

## ⏱ 5-minute run — the hero loop

Find the problem → make the judgement → it's governed.

1. **Today** (30s) — the close cockpit. Point at **⚠ Needs your attention → Commercial Property AY2023** and the four doors (above). *"The triangle's already built and reconciling — no weekend in Excel; the platform tells me where to look."*
2. **Triangle & selection** (3 min) — the hero. The triangle shows **cumulative paid** losses by accident year and development month. In the individual factors, **AY2023 develops at 3.63× at 12→24 months vs ~1.67× every other year** (flagged red). *(Presenter note: the volume-weighted average factor of 1.899 is dragged up by that single 3.63 outlier; 1.667 is roughly the average with that year excluded.)* In the **decision module**: edit the first factor **1.899 → 1.667**; the ultimate recomputes **live £14.74m → £14.44m**. Click **AI peer review** — an assistant reviews *your* pick and gives a verdict. Type a rationale → **Select & save** → a new audited row appears.
3. **Governance & sign-off** (1.5 min) — **the triangle ties back to the claims ledger to the penny**; the **audit trail** shows your selection; click **Sign off** → the basis is reproducible for the auditor.

*Close:* "The platform found it, I judged it, it's governed and reproducible — time back, and defensible at sign-off."

---

## ⏱ 10-minute run — add ingestion + the AI

1. **Today** (30s) — as above.
2. **Ingestion & data quality** (1.5 min) — feeds + data-quality pass rate. The large-loss feed is **quarantined**: a critical check failed because the **corrected** bordereau hasn't tied out yet. Click **Accept** → **blocked**: "resolve the quarantine first." *"Won't let you reserve on data that hasn't passed its checks."* *(Presenter note: the raw large loss is already in the claims ledger — that's why AY2023 develops high; what's quarantined is the reconciled correction to it. Don't say the quarantine causes the distortion.)*
3. **Triangle & selection** (3 min) — the hero loop + AI peer review + **Select & save** (as 5-min step 2).
4. **Workbench AI** (2 min) — a supervisor and specialist tiles. Ask *"why did Commercial Property reserves move?"* → it routes to the **Movement Explainer**. Click the **Committee-Note Drafter** tile → it drafts the memo. *"The assistant does the tedious 80%; I edit and decide."*
5. **Governance & sign-off** (2 min) — reconciliation to the penny, audit trail, the AI-activity log (every model call recorded), the method register, **Sign off**.

---

## ⏱ 15-minute run — the full quarter

Everything, in workflow order — the "day in the life".

1. **Today — close cockpit** (1 min) — attention hooks, sign-off status, the four doors, KPIs.
2. **Ingestion & data quality** (2 min) — feeds, data-quality checks, quarantine **blocks** acceptance; accept a clean feed (the actuary's decision is recorded).
3. **Triangle & selection** (3.5 min) — the **cumulative-paid** triangle, the AY2023 anomaly, the **decision module**: averaging-basis toggle (volume-weighted / simple / last-N / median) recomputes factors live, per-factor override, live ultimate/IBNR + change vs the prior selection, **AI peer review**, **Select & save** (audited).
4. **Methods & estimates** (1.5 min) — the method library (chain-ladder, Bornhuetter-Ferguson, Mack, GLM, benchmark), each **version-controlled and registered**; estimates reconciling to the penny; and **reserve ranges** (coefficient of variation + percentiles) — uncertainty that **informs** the Solvency II risk margin and the IFRS 17 risk adjustment.
5. **Diagnostics** (1.5 min) — actual-vs-expected on the first development step (AY2023 flagged, a large **positive** residual — it developed above the norm), the **movement roll-forward** waterfall ("why did it move"), and **large-loss review**.
6. **Expert judgement** (1.5 min) — raise a judgement; the size **routes the approval**: **under £1m → senior actuary; £1m–£10m → chief actuary; over £10m → board**. Approve it — maker/checker, audited.
7. **Workbench AI** (2 min) — supervisor + 5 specialists (a registered model endpoint) + a plain-English data question that writes and runs governed SQL for you. *(Presenter note: this is Genie via the Conversation API — say "ask the data a question in plain English".)*
8. **Governance & sign-off** (1.5 min) — reconciliation to the penny, full audit trail, AI-activity log, method register, **Sign off** with the as-at data version for reproduction.
9. **External engines** (30s, optional) — the plug-in point: run the selection here, or hand the triangle to an external tool and read the pick back into the same governed record.

*Also:* the **Learn** tile (green, sidebar) — a plain-language walkthrough + Q&A.

---

## Full feature list

| Area | Feature | Interactive? |
|---|---|---|
| **Today** | Close cockpit: attention hooks, sign-off status, four workflow doors, KPIs | navigation |
| **Ingestion** | Feeds, data-quality checks, **quarantine blocks acceptance**, accept (records the decision) | ✅ act |
| **Triangle** | Cumulative-**paid** loss-development triangle — a live view over the claims ledger; reconciles to the penny | view |
| **Selection** | Averaging-basis toggle · per-factor override · live ultimate/IBNR + change vs prior · **Select & save** (audited) | ✅ act |
| **AI peer review** | An assistant independently reviews the actuary's own factor selection, with a verdict | ✅ act |
| **Methods** | Method library (chain-ladder, BF, Mack, GLM, benchmark), each version-controlled & registered | view |
| **Estimates** | Ultimate/IBNR/outstanding per accident year × method, reconciling to the penny | view |
| **Ranges** | Coefficient of variation + percentiles — informs the SII risk margin / IFRS 17 risk adjustment | view |
| **Diagnostics** | Actual-vs-expected validation · movement roll-forward · large-loss review | view |
| **Expert judgement** | Raise → size-routed approval → approve; maker/checker, audited | ✅ act |
| **Committee** | Reserves by line of business + a Senior Reserving Actuary brief | ✅ agent |
| **Workbench AI** | Supervisor + 5 specialists on a registered model endpoint; each grounded on live tables | ✅ act |
| **Plain-English data Q&A** | Ask a question, get governed SQL + the answer *(presenter: Genie / Conversation API)* | ✅ act |
| **Governance** | Reconciliation to the penny · full audit trail · AI-activity log · method register · **Sign-off** + reproduce-as-at | ✅ act |
| **External engines** | Pluggable selection point (Databricks or external tool → same governed record) | view |
| **Platform** | AI cache (cached/live toggle) · demo reset · Learn tile · asset labelling | ✅ act |

---

## If something goes wrong (fallback)

- **AI answer is slow / spins on first ask** — the model endpoint is scale-to-zero and cold-starting (~30-60s). With **AI: cached** on (sidebar, default), the pre-run questions answer instantly; if you switched to **live**, either wait ~1 min or toggle back to **cached** and re-ask. Each answer shows how it was served (agent endpoint / cached / fallback) — a "fallback" tag is fine, it's still a real model answer.
- **A page shows an error or a number looks empty** — the app SP occasionally drops off the SQL warehouse. Reload once; if it persists, move on to another beat and come back (or note it and continue — the story doesn't depend on any single tile).
- **Reset didn't fully restore** — click **Reset demo** again; it's idempotent. If a live selection/judgement you created is still showing, that's harmless — it just means the audit trail has your demo action in it.
- **Genie question returns no rows** — the text answer still carries the figures; read those. Re-ask a simpler phrasing if needed.

---

## Two audiences, one asset
- **Reserving actuaries** (e.g. Hiscox reserving) — book the reserve: select, validate, judge, sign off. Frame as *their in-house process on the platform they're adopting* — the Excel/data-wrangling grind gone; their own R/Python models plug in; capital (e.g. Tyche) sits downstream. **Do not pitch an external reserving tool to this room.**
- **Pricing analysts** (e.g. Hiscox US) — develop losses to ultimate for the rate **indication**: the same triangle machinery, feeding the indicated rate, not the balance sheet.

## Q&A armour
- *Methodology certified?* No — illustrative, method-agnostic; your own models plug in.
- *Our data isn't this clean?* The triangle is a live view over your ledger — it reconciles to whatever's there.
- *Does the AI decide?* No — it drafts and reviews; the actuary decides, and every call is recorded.
- *Replace our tool?* No — the selection step is a plug-in point; we own the data and governance around it.
- *Paid or incurred triangle?* This one is **cumulative paid**; incurred is the same structure with case reserves added — both are just views over the ledger.
- *How do you pick tail factors?* Selected the same way as any age-to-age factor (with a fitted curve beyond the observed triangle where needed) and recorded on the pattern; a demo simplification here, your tail methodology plugs in.
- *Gross or net of reinsurance?* This shows **gross** reserves; net is the same engine with reinsurance recoveries applied downstream (a modelled extension, not shown today).
- *Where do the Bornhuetter-Ferguson priors (expected loss ratios) come from?* From planning / pricing loss ratios in the real world; here they're a synthetic a-priori — the point is the method blends that prior with emerging experience, weighted toward the prior for immature years.

*All data synthetic; Bricksurance SE fictional; figures in GBP. Reset demo in the sidebar between runs.*
