# The two open asks — answered on synthetic data

Neither the split LDF script nor the R indication code ever arrived from Hiscox.
Rather than wait, both are answered here with synthetic stand-ins built on the
live `reserving_workbench` schema. **Everything below has been run for real on DEV
except the R script** (see the caveat in §2).

---

## 1 · "The giant SQL script" → three staged, checkpointed files

`demo/ldf_pipeline/` — the monolith decomposed exactly the way Rich asked for it
(ingest/prep · selection · output). All three run on warehouse `a3b61648ea4809e3`.

| Stage | File | What it does | Writes |
|---|---|---|---|
| 1 | `stage_1_prep.sql` | The up-front process: **coverage remapping**, **named claim exclusions**, **large-loss adjustment**. Excluded/large rows are *flagged out*, never silently deleted. | `demo_stage1_prepared_loss` |
| 2 | `stage_2_selection.sql` | Cumulative triangle → **empirical age-to-age factors** (individual *and* volume-weighted) → **comparison vs the prior selection** with a materiality gate. **Then it stops.** | `demo_stage2_triangle`, `demo_stage2_empirical_ldf`, `demo_stage2_comparison` |
| 3 | `stage_3_output.sql` | **Guard**: refuses to produce output unless an APPROVED election exists. Then develops to ultimate on the **elected** pattern. | `demo_stage3_ultimate` |

**Verified output (run on DEV):**

- Stage 1 checkpoint: **365 claims** in the developable base, **1 large loss held out**, **53 coverage-remapped**, 0 excluded by rule.
- Stage 2 comparison: Commercial Property **within tolerance**; **General Liability step 0 = REVIEW_REQUIRED** — empirical **2.40** vs prior **1.90** (**+26.3%**). That is the stop-and-decide moment, surfaced automatically.
- Stage 2 individual factors confirm the anomaly story: every CP accident year develops ≈**1.667×** at 12–24m.
- Stage 3 ultimates (CP), CDF rising as years get greener:

| AY | cum paid | CDF | ultimate |
|---|---|---|---|
| 2019 | 1,250,057 | 1.0100 | 1,262,557 |
| 2022 | 1,926,759 | 1.0405 | 2,004,796 |
| 2025 | 1,460,097 | 1.4159 | 2,067,373 |
| 2026 | 909,946 | 2.3603 | 2,147,773 |

Every output row carries `applied_selection_id` + `applied_selection_source`, so the
number traces back to the election and the person who approved it.

### The three points to make with this
1. **Named stages, not one script** — you can run, inspect and re-run any stage alone.
2. **It stops where a human is needed** — stage 3 has a hard guard; an unelected empirical pick cannot flow through.
3. **The decision is data, not a code edit** — the election is a governed row (who/when/why/source), so it is auditable and reversible.

---

## 2 · "R for indications" → `demo/r_indication/indication.R`

An indication written in R that **consumes the governed elected pattern**:
reads `demo_stage3_ultimate`, prints the assumption it is standing on (selection id,
approver, rationale), computes loss ratios → trends them → credibility-weights → an
indicated rate change, then writes `demo_r_indication` carrying the `applied_selection_id`.

**Validated numbers** (the arithmetic was run and checked; annual trend 5%, prospective 2027, permissible LR 0.62; AY2026 excluded as too immature):

| AY | ultimate | earned prem | LR | trended LR |
|---|---|---|---|---|
| 2022 | 2,004,796 | 3,040,000 | 0.659 | 0.842 |
| 2023 | 1,281,740 | 2,140,000 | 0.599 | 0.728 |
| 2024 | 1,024,863 | 1,610,000 | 0.637 | 0.737 |
| 2025 | 2,067,373 | 3,160,000 | 0.654 | 0.721 |

Weighted trended LR **0.7446** vs target **0.62** → **indicated rate change ≈ +20.1%**.

> ⚠️ **CAVEAT — the R script has NOT been executed.** R requires a cluster and there
> is **no running cluster on DEV** right now (only the SQL warehouse). The *arithmetic*
> above was independently verified, but the script itself is unrun. Either start a
> small cluster before the call and run it, or present it as **code review + the
> validated numbers** and say the seam is ready — do **not** claim it ran.

### The point to make
Their indication logic stays in R and stays theirs. What changes is that the
**assumption feeding it is governed upstream** — so the indicated rate is traceable
to an approved LDF election instead of to a line buried in a 5,000-line script.

---

## Sequencing in the demo

Show the app first (the visual, the override moment), *then* these files as the
"and here's what that looks like as your pipeline" follow-up. The app is the story;
these are the proof it is real and the answer to the two things they owe us.

## Closing ask (unchanged)
Send the real script split on these three seams and one sample R indication, and we
wire this to Discovery over Federation.

*Synthetic data, illustrative method — not a certified model.*
