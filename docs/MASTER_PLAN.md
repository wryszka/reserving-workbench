# Reserving Workbench — Master Plan

*The single source of truth. Merges the actuary review (`ACTUARY_REVIEW.md`), the engine/positioning
plan and the SA review (agents/MCP/story). Supersedes `BUILD_PLAN_ENGINE_AND_POSITIONING.md` and
`SA_REVIEW_AGENTS_MCP_STORY.md` as the plan of record — keep those two as the reasoning behind it.*

---

## 0 · What this is (and is not) — read before building anything

**This is a demo and a vision, not a product.** That single fact drives every prioritisation call:

- **Lead with what actuaries find HARD; do not lead with what they've already solved.** Factor
  selection, chain-ladder maths, a tail number — they do these in their sleep. Leading with them is
  boring and invites "my spreadsheet already does that". The plumbing, reconciliation, governance,
  reproducibility, narrative and model-ops — the 90% that hurts — is what we open on.
- **It must feel at home.** An actuary should look at it and think *"this is my world, done properly,"*
  not *"a developer built a database app."* If it doesn't feel like their environment, they won't
  leave Excel for it. Workstream G exists entirely for this.
- **The "vs ResQ" answer is easy and must be said the same way every time** (see §1).

## 1 · The positioning — one answer, said identically everywhere

> **It's "both, or just this" — your choice.**
> **If you own ResQ / Reserve Pro:** keep it. We enrich where you're weak — the data in, the
> governance around, the reproducibility, the narrative out — and your engine plugs into the same
> governed record. *Pay for the package, get its depth; we make everything around it defensible.*
> **If you don't (Excel / R on a laptop):** you don't need one to close. Everything runs here
> natively and governed — so you get off the spreadsheet without buying a licensed product.

That is the pricing-workbench-to-Radar stance, inverted to be **standalone-first**. Never pitch this
as a ResQ *replacement* (an actuary punctures it in one screen); never pitch it as *needing* ResQ
(it doesn't). Two honest doors, same governed house.

**The three-sentence story (true on today's data):**
> *"Your claim ledger becomes a governed triangle that reconciles to the penny — no more
> `_v7_FINAL.xlsx`. The one late large loss that would have quietly over-reserved you by £369k is
> caught in the data, flagged for a human, overridden with a recorded reason, and reproducible six
> months later for the auditor. And every method — chain-ladder, your own R model, or a package you
> plug in — runs the same governed pipeline, so the number is defensible however it was produced."*

---

## 2 · Guardrails (apply to every item)

- **Spec-first.** New table/view/function → `model/**.yaml` (gen2 format) → `tools/generate.py` →
  `tools/deploy_databricks.py`. No hand-DDL.
- **No business-level duplication.** New triangles (incurred, net, counts) are **views** over the
  claim ledger, never stored copies.
- **Runs for real.** Every method an MLflow model in UC; every batch step a real Job task; app reads
  live tables; agents are real FMAPI calls traced to the audit log. Nothing faked.
- **Dev language on every page:** unfoldable "what am I seeing" + **per-datapoint "why decided"** +
  demo disclaimer + asset labelling (`[reserving-workbench]`, `bxc_*`), smoke-test enforced.
- **Two personas, one asset.** Reserving books the number; pricing develops to ultimate for the
  indication. No screen tells a pricing actuary it's a reserving tool.
- **Sizes:** ◔ hours · ◑ 1–2 days · ● 3–5 days.

---

## 3 · Workstreams

Seven, lettered. A–D from the engine/positioning plan; E–G are new from the SA review + the
"feel at home" mandate.

### A · The engine — close the actuarial gaps (so a standalone team can book a cohort)
Ordered ★★★ (every-quarter pain) first. Goal is **enough real method to defend a booked number**,
not ResQ parity.

- **A1 · Prior-pattern factor row + "Hold prior" button** ◔ — third read-only row (prior factors)
  in the decision grid; one-click hold-prior that pre-fills a rationale; fix `prior_reserve()` to
  pick the genuine prior; pass real `prior_factors` to the AI reviewer. *(actuary review's #1 miss)*
- **A2 · Fitted, smoothed tail** ◑ — fit exp / inverse-power / Weibull to the last N factors, show
  the curve beyond the triangle, accept or override; store `tail_method_code`/`tail_params`. New
  `fn_fit_tail` UC function + `tail_method` code set.
- **A3 · Method blending per cohort** ● — weight CL↔BF by maturity + a maturity rule; add **Cape
  Cod** and **Benktander** as methods; blended ultimate → `reserve_estimate` with `blend_spec` JSON.
- **A4 · Editable BF/ELR a-priori per cohort** ◑ — user-set a-priori (= planning LR × earned
  premium, premium already ingested); `reserve_apriori` entity.
- **A5 · Gross-to-net (reinsurance)** ● — minimal RI programme (QS % + one XoL layer), ceded triangle
  as a **view**, net columns on estimates + committee. The loudest silence for a reserving actuary.
- **A6 · Bootstrap / full predictive distribution** ● — ODP bootstrap as a registered model run in a
  **Job** (thousands of sims); `reserve_distribution` entity; histogram + percentiles.
- **A7 · Incurred triangle + paid/incurred consistency** ◑ — basis-aware selection (paid|incurred) +
  convergence diagnostic. Incurred already a column.
- **A8 · Count & average-cost triangles (frequency-severity)** ◑ — count/closure/avg-cost views;
  the pricing-actuary need, a reserving cross-check.
- **A9 · Discounting + cohort basis** ◑ — PV on a yield curve (SII/IFRS 17); underwriting/report-year
  triangles, not only accident year.
- **A10 · Cell-level actual-vs-expected heatmap** ◔ — residual heatmap across the whole triangle.

### B · Positioning & framing (make the §1 stance explicit and honest)
- **B1 · Fix misleading language** ◔ — "ultimates" not "reserves" on the pricing path; honest
  "GBP (illustrative)"; wire the AI review to the prior (via A1) so it can keep its button.
- **B2 · Rebuild "Engines & your models" as the positioning centrepiece** ◑ — three tracks:
  **Standalone (default, headline)** / **Bring your own R-Python** / **Plug in a package (optional)**,
  mirroring pricing's `RatingEngineIntegration` page but standalone-first. Carries the §1 line verbatim.
- **B3 · In-app honesty panel** ◔ — capability matrix: native (green) / bring-your-model (blue) /
  a package still does better (grey). Being explicit is what keeps an actuary's trust.
- **B4 · Update demo docs** ◔ — standalone-first stance into `DEMO_GUIDE.md` + Aug docs.

### C · MLflow model-management & automation (the real differentiator — "MLOps for reserving")
This is where a package-less team gets something a spreadsheet team *and most incumbents* don't have.
- **C1 · Whole engine MLflow-governed** ◑ — extend notebook 04 to register Cape Cod / Benktander /
  bootstrap / tail-fit; every method versioned, aliased, signed, lineaged → model risk management for
  free (the SR11-7 / TS 20-1 story).
- **C2 · Scheduled quarterly close as a Job** ● — parameterised Job: source → prep → all triangles →
  every registered method → bootstrap → AvE → estimates, one MLflow run per method per cohort, the
  guard intact. Reproducible close; bootstrap *must* live here.
- **C3 · Champion/challenger + back-testing** ◑ — scheduled job re-runs prior selections against
  emergence, logs error per method to MLflow → `method_backtest`. "Which method has been most
  accurate on GL over 8 quarters" becomes a tracked metric. **Depends on F1 (historical data).**
- **C4 · Approval = MLflow alias transition** ◔ — promoting to `production` is the governed, logged,
  reversible act; app shows alias history.

### D · Designer / Excel on-ramps (meet actuaries where they live)
- **D1 · Lakeflow Designer as no-code prep** ◑ — Designer builds the stage-1 prep flow visually,
  same governed output table. The "different front door" for the non-SQL analyst.
- **D2 · Excel as a first-class surface** ◑ — read: `reserving_metrics` metric view live from Excel
  (one governed definition); write-back (scoped): an Excel template lands a `PENDING_APPROVAL` row —
  same governed record as app/notebook/SQL/MCP.
- **D3 · One-click Excel committee pack** ◔ — `.xlsx` of ultimates + selections + audit carrying
  `applied_selection_id`/approver/rationale ("your Excel now carries its provenance").

### E · Clarity — the dev-language "why decided" half (mostly hours, high trust-per-hour)
Every page has the "what am I seeing" intro; the gap is **per-datapoint "why"**.
- **E1 · Per-datapoint "why" unfolds** ◑ — Today: why each flag fired (residual/restated £/mapping
  id). Triangle: "why this factor" per column (n years, outlier dropped, prior held). Diagnostics:
  per-row "why flagged". Methods: which basis is booked and why.
- **E2 · Per-tab sub-headers on Ingestion** ◔ — each of the six tabs gets its own one-liner (the page
  explainer currently covers all six).
- **E3 · "You are here in the close" breadcrumb** ◔ — Trust → Select → Analyse → Decide → Sign off,
  on every page, so a big-screen viewer never loses the thread.

### F · Story data (prerequisite for the differentiator + the complete narrative)
The synthetic world is one valuation date; the big story needs depth.
- **F1 · Historical quarters (≥6)** ● — triangles, selections and emergence across time. Unlocks
  back-testing (C3), the accuracy agents, and time-depth in every diagnostic. **Highest story value;
  gates Phase 3.**
- **F2 · One worked downstream landing** ◑ — signed ultimate → a Solvency II TP cell / IFRS 17 LIC
  line, closing the arc from ledger to regulatory number (lifecycle stages 7–8 are stubbed today).
- **F3 · Deeper segmentation (20+ classes)** ◑ — so the book cockpit *shows* the "30+ classes" scale
  it currently only asserts.

### G · Feel at home — the UI that makes an actuary stay (the "why leave Excel" answer)
The reason to come here instead of Excel isn't features — it's that it **feels like their world,
better.** Lead with their hard problems; make the familiar things instantly recognisable.
- **G1 · The triangle looks like an actuary's triangle** ◑ — proper development-triangle styling
  (diagonal shading for the latest diagonal, the staircase of observed vs future, factor row beneath
  in the conventional place), heatmap option on residuals. It should be *more* readable than their
  Excel triangle, not less. This is the "at home" anchor.
- **G2 · Excel-grade interactions** ◔ — keyboard-navigable factor grid (arrow keys, tab, type-over),
  copy-paste a column out to Excel, number formatting an actuary expects (thousands, no scientific
  notation, £ aligned). Small touches that say "built by someone who uses spreadsheets".
- **G3 · Lead-with-the-hard-thing landing** ◔ — the Today page and each section open on the painful
  90% (what changed, what won't reconcile, what needs judgement), not on the triangle mechanics.
  Reorder so the first thing seen is the thing they can't do today.
- **G4 · "This would take you a week" callouts** ◑ — quiet, tasteful markers on the beats that
  replace days of manual work (reconciliation, movement explanation, reproduce-as-at, back-testing),
  so the value lands without being told. Not "WOW Factor" branding — the work speaks.

### H · Agents & MCP (extends C; the explain/draft/challenge triad + chat operability)
- **H1 · New specialists, inside the triad** ◑ — **Data-Diff Narrator**, **Selection-Rationale
  Drafter** (fills the blank rationale box), **Method-Recommender** (CL-vs-BF-by-maturity),
  **Back-test Commentator** (needs F1/C3), **Reproduce-as-at Explainer**. Never an agent that *decides*.
- **H2 · MCP server — operate the workbench by chat** ◑ — mirror pricing's `routes/mcp.py`. Read
  tools (triangle, compare, estimates, diagnostics, whatif) + governed write tools (`propose_selection`
  → PENDING_APPROVAL, `approve_selection`, `run_pipeline_stage3`). **Write tools reuse the app's
  endpoint logic** (rationale required, magnitude-routed approval, no self-approve) — never a
  governance bypass. The beat: propose a selection from an assistant, watch it appear in the app's
  audit trail — proves the governance is in the platform, not the UI.

---

## 4 · Phasing

**Phase 1 — "stop an actuary dismissing it, and make it feel at home" (mostly hours).**
A1 · B1 · B2 · B3 · E1 · E2 · E3 · G3. *Outcome: nothing overclaims, the core screen answers all
three asks, the "why" is visible per datapoint, and it opens on the hard problems. Highest
trust-per-hour, and it's the "review each page" + "feel at home" ask delivered.*

**Phase 2 — "a standalone team could book a cohort" (the ★★★ engine gaps + at-home triangle).**
A2 · A5 · A3 · C1 · G1 · G2. *Outcome: the honest claim becomes "you can close in this without a
package," on a triangle that feels like theirs.*

**Phase 3 — "MLOps for reserving" (the differentiator).**
F1 (data prerequisite) → C2 · A6 · C3 · C4 · H1 (back-test/accuracy agents). *Outcome: versioned,
back-tested, scheduled reproducible reserving — a category incumbents mostly don't offer.*

**Phase 3.5 — "operate it from anywhere, same governance".**
H2 (MCP) · G4 (value callouts). *Outcome: the "any door, same governed row" thesis, provable from chat.*

**Phase 4 — depth + on-ramps.**
A4 · A7 · A8 · A9 · A10 · D1 · D2 · D3 · F2 · F3. *Outcome: engine depth, Designer/Excel, and the
complete ledger-to-capital arc at real scale.*

---

## 5 · Deliberately NOT doing
- Not replacing ResQ / building a reserving package (no exotic curve libraries, no decades of edge
  cases). The seam stays; "plug yours in if you own one" is track 3 of B2.
- Not faking the engine deeper than it is — the honesty panel (B3) states the boundary out loud.
- Not duplicating business data — every new triangle is a view.
- Not "WOW Factor" branding (G4 is tasteful, the work speaks).

## 6 · The "done" test
> *A reserving actuary with no package builds paid and incurred triangles by segment, fits a tail,
> blends CL and BF by maturity, runs a bootstrap for the range, takes it gross and net, discounts it,
> overlays a judgement, signs it off, reproduces it six months later, and drives any of it from chat —
> all governed, versioned, reproducible — and never opens Excel except to read the pack. And it felt
> like home the whole way.*

---

## 7 · Status log
- **2026-08-11 — plan merged; starting Phase 1.**
- **2026-08-11 — Phase 1 shipped & verified live:** A1 (prior row + Hold-prior + fixed
  prior_reserve + AI review gets real priors), B1 (language), B2 (three-track standalone-first
  positioning), B3 (honesty matrix), E1 (why-factor), E2 (per-tab sub-headers), E3 (breadcrumb).
- **2026-08-11 — Phase 2 in progress:** A2 (fitted tail — exponential/inverse-power, R² surfaced)
  DONE & live. A5 (gross-to-net — RI programme entity, net columns, grain-correct QS+expected-XoL)
  DONE & live; retention 70–90%/line, 76% book. A3 (method blending + Cape Cod &
  Benktander) DONE & live — blend control (flat weight + maturity rule), verified: maturity rule
  correctly puts CL on mature cohorts, BF on green; Benktander sits between BF and CL. C1 DONE — all
  9 methods registered as real MLflow/UC models (smoke 26/26). **Phase 2 complete.** Next: Phase 3
  (MLOps differentiator — F1 historical data, then C2 scheduled close Job, A6 bootstrap, C3 back-test).
- **2026-08-11 — Phase 3 in progress:** F1 (historical depth — no fake snapshots; valuation-as-of is the
  ledger truncated to transaction_year<=Y) + C3 (champion/challenger back-testing, method_backtest, the
  Method-accuracy page, Back-test Commentator agent) DONE & live, smoke 28/28. Accuracy tracks tail length,
  measured not asserted (Marine 1.8% → PI 16%).
  **DECISION NEEDED before C2 (scheduled close Job):** two engines have diverged —
  `notebooks/01_reserving_engine.py` (older) vs `tools/run_reserving.py` (canonical, has Cape Cod/Benktander/
  net/backtest). C2 must chain ONE. Options: (a) wrap the verified tools/ scripts as job-task notebooks
  [lower risk, keeps the tested engine]; (b) bring notebook 01 to parity [cleaner long-term, more work].
  Recommend (a). A6 (bootstrap) then slots in as another task on whichever wins.
