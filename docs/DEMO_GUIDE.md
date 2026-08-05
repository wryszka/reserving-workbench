# Reserving Workbench — Demo Guide

**App:** https://reserving-workbench-7474656169654171.aws.databricksapps.com · **Entity:** Bricksurance SE (fictional, synthetic data) · on Databricks (dev).

The reserving analogue of the pricing workbench: the full quarterly reserving process — **data → engines → agents → governance** — on one platform, with human-in-the-loop decisions and a real AI layer. This guide gives three timed runs (5 / 10 / 15 min) and a full feature list.

> **Before any demo (2 min):** open the app once so it's warm · sidebar → **Reset demo** · leave **AI: cached** on (routed AI answers return instantly; the serving endpoint cold-starts ~30-60s if you go live). Story character: *Sarah, a senior reserving analyst, on the Monday of Q4 close.*

---

## ⏱ 5-minute run — the hero loop

The single strongest thread: find the problem → make the judgement → it's governed.

1. **Today** (30s) — land on the close cockpit. Point at **⚠ Needs your attention → Commercial Property AY2023** (a validation breach) and the four "doors". *"The triangle's already built and reconciling — no weekend in Excel; the platform tells me where to look."*
2. **Triangle & selection** (3 min) — the hero. Show the triangle; in the individual factors, **AY2023 = 3.63× vs 1.67×** everywhere else (red). In the **Decision module**: edit the first factor **1.899 → 1.667**; the ultimate recomputes **live £14.74M → £14.44M**. Click **🔍 AI peer review** — a real agent reviews *your* pick and gives a verdict. Type a rationale → **Elect & save** → a new audited row appears.
3. **Governance & sign-off** (1.5 min) — **triangle ties to the ledger to the penny**; the **audit trail** shows your election; click **Sign off** on a pending line → reproducible for the auditor.

*Close:* "Platform found it, I judged it, it's governed and reproducible — time back, bulletproof at sign-off."

---

## ⏱ 10-minute run — add ingestion + the AI

The 5-min loop, plus the front door and the AI layer.

1. **Today** (30s) — as above.
2. **Ingestion & data quality** (1.5 min) — feeds + DQ pass %. The **large-loss bordereau is quarantined** (a critical check failed). Click **Accept** → **blocked**: "resolve the quarantine first." *"Won't let you reserve on bad data — and that quarantined loss is the very one distorting AY2023."*
3. **Triangle & selection** (3 min) — the hero loop + AI peer review + elect (as 5-min step 2).
4. **Workbench AI** (2 min) — supervisor + specialist tiles. Ask *"why did Commercial Property reserves move?"* → routes to **Movement Explainer** (real agent endpoint). Click the **Committee-Note Drafter** tile → drafts the memo. *"The AI does the tedious 80%; I edit and decide."*
5. **Governance & sign-off** (2 min) — reconciliation, audit trail, **AI activity** (every model call, governed), model registry, **sign off**.

---

## ⏱ 15-minute run — the full quarter

Everything, in workflow order — the "day in the life".

1. **Today — close cockpit** (1 min) — attention hooks, sign-off status, the four doors, KPIs.
2. **Ingestion & data quality** (2 min) — feeds, DQ expectations, quarantine **blocks** acceptance; accept a clean feed (HITL writeback).
3. **Triangle & selection** (3.5 min) — triangle, the AY2023 anomaly, the **decision module**: basis toggle (volume-weighted / simple / last-N / median) recomputes factors live, per-factor override, live ultimate/IBNR + Δ-vs-prior, **AI peer review**, **Elect & save** (audited).
4. **Methods & estimates** (1.5 min) — the methodology library (CL/BF/Mack/GLM/peer, each a versioned UC model), estimates reconciling to the penny, and **reserve ranges** (Mack CoV/percentiles → the input SII risk margin & IFRS 17 risk adjustment need).
5. **Diagnostics** (1.5 min) — actual-vs-expected (AY2023 flagged, residual −3.05), the **movement roll-forward** waterfall ("why did it move"), and **large-loss review**.
6. **Expert judgement** (1.5 min) — raise a judgement; magnitude **routes the approval** (senior actuary < £1m < chief actuary < £10m < board); approve it — maker/checker, audited.
7. **Workbench AI** (2 min) — supervisor + 5 specialist tiles (real registered agent endpoint) + server-side **Genie** ("total IBNR by line of business" → answer + SQL).
8. **Governance & sign-off** (1.5 min) — reconciliation to the penny, full **audit trail**, **AI activity** log, model registry, **sign off** with reproduce-as-at data version.
9. **External engines** (30s, optional) — the pluggable seam: run selection in Databricks or hand the triangle to an external tool and read the pick back into the same governed table.

*Also on the platform:* the **Learn** tile (green, sidebar) — a plain-language walkthrough of the process + Q&A armour.

---

## Full feature list (what to point at)

| Area | Feature | Interactive? |
|---|---|---|
| **Today** | Close cockpit: attention hooks, sign-off status, workflow doors, KPIs | navigation |
| **Ingestion** | Source feeds, DQ expectations, **quarantine blocks acceptance**, HITL accept (writeback) | ✅ act |
| **Triangle** | Loss-development triangle (a view over the ledger; reconciles to the penny) | view |
| **LDF selection** | Averaging basis toggle · per-factor override · live ultimate/IBNR + Δ-vs-prior · **elect & save** (audited) | ✅ act |
| **AI peer review** | An agent independently reviews the actuary's own factor selection, with a verdict | ✅ act |
| **Methods** | Methodology library (CL/BF/Mack/GLM/peer), each a versioned UC model | view |
| **Estimates** | Ultimate/IBNR/outstanding per AY × method, reconciling to the penny | view |
| **Ranges** | Mack CoV + percentiles → SII risk margin / IFRS 17 risk adjustment | view |
| **Diagnostics** | Actual-vs-expected validation · movement roll-forward · large-loss review | view |
| **Expert judgement** | Raise → magnitude-routed approval → approve; maker/checker, audited | ✅ act |
| **Committee** | Reserves by LOB + Senior Reserving Actuary brief | ✅ agent |
| **Workbench AI** | Supervisor + 5 specialists on a real **Agent-Framework serving endpoint**; each grounded on live tables | ✅ act |
| **Genie** | Natural-language over the tables via the **Conversation API** (server-side, governed SQL) | ✅ act |
| **Governance** | Reconciliation to the penny · full audit trail · **AI activity** (every model call) · model registry · **sign-off** + reproduce-as-at | ✅ act |
| **External engines** | Pluggable selection seam (Databricks or external tool → same governed table) | view |
| **Platform** | AI cache (live/cached toggle) · demo reset · Learn tile · asset labelling (every object tagged to the workbench) | ✅ act |

---

## Two audiences, one asset
- **Reserving actuaries** (e.g. Hiscox reserving) — book the reserve: select, validate, judge, sign off. Frame as *their in-house process on the platform they're adopting* — the Excel/macro/data-wrangling grind gone; own R/Python models plug in; capital (e.g. Tyche) is downstream. **Do not pitch ResQ to this room.**
- **Pricing analysts** (e.g. Hiscox US) — develop losses to ultimate for the rate **indication**: the same triangle machinery, feeding the indicated rate not the balance sheet.

## Q&A armour
*Methodology certified?* No — illustrative, platform-agnostic; your own models plug in. *Our data isn't this clean?* The triangle is a view over your ledger — reconciles to whatever's there. *Does the AI decide?* No — it drafts and reviews; the actuary decides, every call audited. *Replace our tool?* No — the selection step is a pluggable seam; we own the data + governance around it.

*All data synthetic; Bricksurance SE fictional. Reset demo in the sidebar between runs.*
