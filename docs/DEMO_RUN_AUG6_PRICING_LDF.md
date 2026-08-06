# LDF Process on Databricks — Prototype Review

**For:** Hiscox US Pricing — John McGinn, Richard Derr (+ Scott Klepetka, Imogen Hirsh)
**Date:** 6 August 2026

---

## 0 · Where everything is (read this first)

| What | Click straight through |
|---|---|
| **The whole demo folder** — everything below lives here, numbered in running order | **[open LDF_demo](https://fevm-lr-dev-aws-us.cloud.databricks.com/browse/folders/1906953798015725)** |
| **1 · The monolith** (start here) | [1_the_monolith](https://fevm-lr-dev-aws-us.cloud.databricks.com/editor/notebooks/64021633005599) |
| **2 · The four stages** — run in order | [2_stage_0_source_sync](https://fevm-lr-dev-aws-us.cloud.databricks.com/editor/notebooks/64021633005600) |
| | [3_stage_1_prep](https://fevm-lr-dev-aws-us.cloud.databricks.com/editor/notebooks/64021633005601) |
| | [4_stage_2_selection](https://fevm-lr-dev-aws-us.cloud.databricks.com/editor/notebooks/64021633005602)  ← **this is where it stops for a human** |
| | [5_stage_3_output](https://fevm-lr-dev-aws-us.cloud.databricks.com/editor/notebooks/64021633005603)  ← guarded |
| **3 · The Job** | **[LDF pipeline — 4 tasks, successful runs](https://fevm-lr-dev-aws-us.cloud.databricks.com/jobs/128759624194016)** |
| | [stage-3-only job (what the app triggers)](https://fevm-lr-dev-aws-us.cloud.databricks.com/jobs/292936672808317) |
| **4 · The app** (the easy interface on top) | **[open the workbench](https://reserving-workbench-7474656169654171.aws.databricksapps.com)** → sidebar **Prepare** → **Triangle & selection** |
| **If they push on transparency** | [6_see_into_it](https://fevm-lr-dev-aws-us.cloud.databricks.com/editor/notebooks/64021633005604) — 19 cells, all verified |
| **The analyst's door** (power-user path) | [7_analyst_selection](https://fevm-lr-dev-aws-us.cloud.databricks.com/editor/notebooks/64021633005605) — all lines, all bases, ad-hoc exclusions; writes the same selection row the app does |
| **R indication** | [8_r_indication](https://fevm-lr-dev-aws-us.cloud.databricks.com/editor/notebooks/64021633005606) |
| | [9_r_indication_classic](https://fevm-lr-dev-aws-us.cloud.databricks.com/editor/notebooks/64021633005607) (classic compute — the variant that actually ran) |
| **SQL Editor** (for the ad-hoc queries in §3 and §7) | [open SQL Editor](https://fevm-lr-dev-aws-us.cloud.databricks.com/sql/editor) — warehouse **Serverless Starter** |
| **Catalog / schema for every query below** | `lr_dev_aws_us_catalog.reserving_workbench` |

**The Job is real and has run.** Workflows shows *[reserving-workbench] LDF pipeline* with a
successful 4-task run, and *LDF stage 3* with its own. The app links to both from the **pipeline
panel** on Triangle & selection — you never have to leave the app to prove the pipeline exists.

> ⚠️ **Provenance — say this early, do not let them assume otherwise.** The monolith in step 1 is
> **our reconstruction**, not your script: yours hasn't been shared with us yet. We built it from
> the shape you described on 23 July so there was something concrete to decompose. Your real one is
> longer, messier, and has rules in it we've guessed at — which is exactly why we're still asking
> for it. Everything downstream of it is real and runs; the starting point is a stand-in.

**Two-minute pre-flight:** open the app once so it wakes up → sidebar **Reset demo** → open the
**LDF_demo folder** (link above) and leave **1_the_monolith** on screen, ready to run.

---

## 1 · What we understood you needed

From our conversation on 23 July, the picture we took away:

**Where you are today.** The LDF process runs on-premises in Discovery (SQL Server) as a single
large SQL script. Three things about that hurt:

- **You can't see into it.** It's one script, so identifying where a particular transformation
  happens is hard. *(This is the one that matters most — answered in §7.)*
- **You can't restart part of it.** If it fails, the whole thing reruns.
- **You can't stop it to intervene.** There's no point at which someone can override an
  empirical pick — for example holding a prior LDF pattern because a data anomaly distorted
  this period's factor — before it flows into the final tables.

**The up-front data build matters too.** Coverage remapping, named claim exclusions and
large-loss adjustment — described as required for every part of the quarterly loss ratio process.

**And a data constraint.** Premium has moved to Databricks, but loss data from One Shield is
still being validated, so Discovery stays the source for losses until those feeds are verified.
Nothing here depends on that validation finishing.

**What you asked to see.** Three specific capabilities:

| # | Your ask | Section |
|---|---|---|
| 1 | **Triangle visualisation** — the losses and the empirically calculated LDFs *before* anything is selected | §4 (stage 2), §6 (in the app) |
| 2 | **Comparison** — the empirical factors against a previously selected set | §5 (materiality gate), §6 |
| 3 | **A decision module** — take the empirical pick, or hold the prior one, as a deliberate step | §6 |

Plus two things to explore: **R integration**, since indications are built in R; and reading
Discovery **without an ingestion project**.

**What we said we'd do.** Build a prototype showing a staged workflow, the manual intervention
point, and the R options — and review it today. That's what §3 to §6 walk through, in that order.

> **One framing note.** This uses loss-development machinery that reserving teams also use.
> That's deliberate: same technique, and here it serves a **rate indication**, not a booked
> reserve. Build it once, both teams consume it.

---

## 2 · The running order

Deliberately **not** starting with the app. The app is the last thing, because it is the easiest
thing — and leading with it invites "so it's a dashboard". The argument runs the other way:

| | What | Why this order |
|---|---|---|
| **1** | **The monolith** — one script, works fine, produces a number | Establish the problem on their own terms, in SQL they recognise |
| **2** | **Broken into four notebooks** | Each stage named, runnable alone, writing an inspectable table |
| **3** | **The same four as a Job** | Now it's a process: dependencies, run history, repair a single task |
| **4** | **The app on top** | The easy interface over stage 2's stopping point — not the product, the front door |

The single most useful thing to show is the **diff between step 1 and step 3**: same claims, same
day, and the monolith is **£369,370 higher** on Commercial Property alone — because nobody ever
looked at the factors. See §3.

---

## 3 · Step 1 — the monolith, and what it costs

**Where:** [**1_the_monolith**](https://fevm-lr-dev-aws-us.cloud.databricks.com/editor/notebooks/64021633005599) (or the folder link in §0). Run it; it works.

It reads claims, remaps coverages, holds out large losses, applies exclusions, builds the triangle,
computes the factors and writes ultimates — in one pass. Point at what that means:

- The coverage remap is a `LEFT JOIN` inside a CTE. The large-loss hold-out is a `WHERE` clause
  three CTEs down. **Nothing records that a claim left the base.**
- The factors are computed and consumed **in the same breath**. No row anywhere says what was
  selected, by whom, or why.
- The tail (`* 1.01`) is hardcoded mid-script.
- There is **no point at which it stops.**
- The final column reads `applied_selection_id = 'no selection recorded'`.

**Then the number.** Run the comparison against the governed pipeline's output:

```sql
SELECT m.accident_year,
       round(m.ultimate_loss,0)              AS monolith,
       round(s.ultimate_loss,0)              AS governed,
       round(m.ultimate_loss - s.ultimate_loss,0) AS difference
FROM demo_monolith_ultimate m
JOIN demo_stage3_ultimate s
  ON s.accident_year = m.accident_year
 AND s.line_of_business_code = m.line_of_business_code
WHERE m.line_of_business_code = 'COMMERCIAL_PROPERTY'
ORDER BY 1;
```

Commercial Property, same claims, same day: the monolith is **£369,370 higher in total** — AY2021
+£45,966, AY2022 +£54,416, AY2023 +£38,823, and so on. Not because it's broken, but because the
anomalous factor was never reviewed. **The output looks perfectly respectable, and that is the trap.**

> **The line:** *"This isn't a quality problem — it runs, and the number looks fine. It's a
> reviewability problem. You can't see it, you can't stop it, and it already wrote the answer."*

---

## 4 · Step 2 — the same logic, in four named stages

**Where:** `2_stage_0_source_sync` → `3_stage_1_prep` → `4_stage_2_selection` → `5_stage_3_output`
(links in §0). They are numbered in running order, so the folder reads top to bottom. Each is a
notebook you can run cell by cell, and each writes a table you can look at.

Nothing about the actuarial content changed. What changed is that **every step has a name and a
checkpoint** — the three seams you asked for, plus a source-binding stage in front so the move off
Discovery touches one file.

---

## 5 · Step 3 — the Job: now it is a process

Same four stages, wired together with dependencies, run history, and the ability to rerun one task.
This is the moment it stops being "some SQL files" and becomes an operable process.

**Where:** Workspace → **Workflows** → *[reserving-workbench] LDF pipeline*. Open the successful
run and walk the four green tasks.

| Stage | File | What it does | Writes |
|---|---|---|---|
| 1 | `3_stage_1_prep` | The up-front build: **coverage remapping**, **named claim exclusions**, **large-loss adjustment**. Excluded and large rows are **flagged out, never silently deleted**. | `demo_stage1_prepared_loss` |
| 2 | `4_stage_2_selection` | Triangle → empirical factors (individual *and* volume-weighted) → **comparison vs the prior selection with a materiality gate**. **Then it stops.** | `demo_stage2_triangle`, `demo_stage2_empirical_ldf`, `demo_stage2_comparison` |
| 3 | `5_stage_3_output` | **Guard: refuses to produce output unless an approved election exists.** Then develops to ultimate on the elected pattern. | `demo_stage3_ultimate` |

**Stage 1 checkpoint:** 366 claims, **1 large loss held out**, **53 coverage-remapped**, 0 excluded
by rule. The flags are columns, so you can see exactly what was removed and why.

**Stage 2 is the beat worth pausing on.** The materiality gate flagged something nobody went
looking for — query it live:

```sql
SELECT line_of_business_code, step_idx, prior_factor, empirical_factor,
       round(variance_pct,1) AS pct_change, review_status
FROM lr_dev_aws_us_catalog.reserving_workbench.demo_stage2_comparison
WHERE review_status = 'REVIEW_REQUIRED';
```

→ **General Liability, step 0: empirical 2.4003 vs prior 1.90 = +26.3% → REVIEW_REQUIRED.**

Commercial Property came back within tolerance on every step. So the process itself surfaced the
one line that needs a human, without anyone knowing in advance to look at it.

**Stage 3 is the answer to "we can't stop it".** The guard means an unelected empirical pick
**cannot** reach the output table. Every output row carries `applied_selection_id` and
`applied_selection_source` — currently `SEL-2026Q4-PROP-ELECTED` — so the number traces to the
election and the person who approved it. Commercial Property ultimates:

| AY | cum paid | CDF | ultimate |
|---|---|---|---|
| 2019 | 1,250,057 | 1.0100 | 1,262,557 |
| 2022 | 1,926,759 | 1.0405 | 2,004,796 |
| 2025 | 1,460,097 | 1.4159 | 2,067,373 |
| 2026 | 909,946 | 2.3603 | 2,147,773 |

**Rerun one stage, not the lot.** In the run page, click the failed or stale task -> **Repair run**
-> it reruns *that task alone*. That is the direct answer to "if it fails, the whole thing reruns".

**And the decision resumes it.** Stage 2 stops on purpose. In the app, after **Select & save**, an
**Approve & run stage 3** button appears with a live status chip: approving flips the selection to
approved and triggers the stage-3 job, and you watch it go green without leaving the page. If you
approve nothing and run stage 3 anyway, it **fails with a readable message** -
*"STAGE 3 BLOCKED: no approved selection for COMMERCIAL_PROPERTY..."*. **That failure is the control
working, not a bug** - worth saying out loud before you trigger it.

**Three points to make with this:** named stages you can run and re-run individually · it stops
where a human is needed, by design · the decision is data, not a code edit — so it's auditable
and reversible.

---

## 6 · Step 4 — the app, the easy interface on top

Now the app earns its place: it is the front door onto **stage 2's stopping point**, not a separate
product. Everything it shows is the same governed table the notebooks and the Job read.

### Ask #1 — the triangle and empirical LDFs, before selection

**Where:** app sidebar → **Prepare** → **Triangle & selection**, line of business **Commercial
Property** (it's the default).

- **Cumulative paid triangle** — accident year down, development month across; shaded = observed.
- Below it, **individual age-to-age factors by accident year**, then the **volume-weighted
  empirical factors**. Nothing selected yet — this is what the data says.

**The triangle is a view, not an output.** Derived from the loss ledger on read, so it reconciles
to source by construction, with no stored copy to drift and no script to rerun.

**The factor is a callable function, not a line buried in a script.** In your SQL Editor tab:

```sql
SELECT lr_dev_aws_us_catalog.reserving_workbench.fn_empirical_ldf('COMMERCIAL_PROPERTY', 0);
-- 1.897191    (the 12 to 24 month factor)
```

Callable from SQL, the app, or a notebook — one definition, one answer, version-controlled. The
direct contrast with "somewhere in 5,000 lines".

**On Discovery:** this reads synthetic loss data today. Pointing it at Discovery is a connection,
not a migration — see §10.

---

### Asks #2 and #3 — compare against the prior set, then decide

**Where:** same page, scroll to **Individual age-to-age factors**, then **Decision module —
select development factors**.

**What the comparison shows.** In the individual factors:

| Accident year | 12 to 24 month factor |
|---|---|
| 2019 | 1.667 |
| 2020 | 1.676 |
| 2021 | 1.667 |
| 2022 | 1.667 |
| **2023** | **3.627** — flagged red |
| 2024 | 1.667 |
| 2025 | 1.667 |

One accident year develops at more than twice the rate of every other — a single late-reported
large loss. The volume-weighted average across all years is **1.897**, dragged up by that one
year; hold it out and you're back to roughly **1.667**.

Exactly the case you described: an empirical pick you would not want flowing through untouched.

**The decision module.** Directly below:

- **Averaging basis** dropdown (volume-weighted / simple / last-N / median / geometric) — factors
  recompute live. *(Median gives **1.6667** — a useful answer if asked how you'd defend 1.667.)*
- Or **type over any single factor**: change the first from **1.897 to 1.667**. The ultimate
  recomputes immediately, **£15.25m to £14.94m**, and **Δ vs prior selection** shows the
  difference against the previously approved pattern. You see the consequence before committing.
- Type a reason, then **Select & save**.

**What that writes.** A new row — who, when, basis, factors, whether anything was overridden, and
why. The previous selection is not overwritten. The **Selection audit trail** table at the bottom
of the page shows it:

| Selection | Source | Status | First factor |
|---|---|---|---|
| SEL-2026Q3-PROP-PRIOR | prior selection | approved | 1.667 |
| SEL-2026Q4-PROP-EMPIRICAL | calculated | draft | 1.897 |
| SEL-2026Q4-PROP-ELECTED | held prior | approved | 1.667 *(reason recorded)* |

The stop-and-override point the current process can't offer — a recorded decision, not an edit
someone remembers making.

---

## 7 · "Can I see into my methodology?" — the five queries

**Where:** [**6_see_into_it**](https://fevm-lr-dev-aws-us.cloud.databricks.com/editor/notebooks/64021633005604). Run the cells in order — all 19 verified.

This is the sharpest version of the objection, and worth separating from §4 and §5.
"We split the script into three files" does not answer it — you would still be reading files.
The actual answer is that **the methodology stopped being text in a file** and became a governed
object the catalog can answer questions about.

**Query 1 — what does the factor actually do?**

```sql
SELECT routine_definition
FROM system.information_schema.routines
WHERE routine_schema = 'reserving_workbench' AND routine_name = 'fn_empirical_ldf';
```

Returns the whole methodology, out of the catalog — no repo, no file, no author to ask:

```
SUM(nxt.cumulative_paid) / NULLIF(SUM(cur.cumulative_paid), 0)
  ...joined on accident_year, line_of_business, currency, development_lag + 1
```

**Read that out loud.** That *is* the volume-weighted age-to-age factor: sum of the next column
over sum of this one. An actuary can audit it in ten seconds and say "yes, that's what I meant".
Compare with locating the same logic inside 5,000 lines.

**Query 2 — where do the triangle numbers come from?** The triangle is a view, so its definition
*is* its documentation: you can read that paid = indemnity + expense − recovery, and that
development lag = transaction year − accident year. Nothing hidden in a load step.

**Query 3 — why is this number what it is?** Drill from the 3.627 factor to the claim, in two
hops: the two cells it divides (1,942,643 / 535,586), then every claim inside that movement —
**CLM-2023-ANOMALY at £900,000 + £150,000**, on a base of ~40k claims. The anomaly names itself.
In the current process this is the week-three discovery.

**Query 4 — what else would I break if I changed it?** Lineage, recorded automatically as queries
run rather than drawn by hand. Also in the UI: Catalog Explorer → table → **Lineage** tab, which
shows the notebooks and jobs that touched it too.

**Query 5 — what changed, and who changed it?** `DESCRIBE HISTORY` on the selection table gives
every version with timestamp and author (32 versions today), and the selection table itself carries
who chose what, on what basis, and why.

> **The line to land.** *Five things you can ask about your methodology here — what it does, where
> its inputs come from, why a number is what it is, what depends on it, and what changed. A script
> can only answer the first, and only by reading it. That isn't a tidiness difference.*

---

## 8 · Policy, premium and the loss ratio

**Where:** app sidebar → **Prepare** → **Ingestion & data controls** → tab **5 · Feeds &
timeliness**. Two of the six feeds are **policy and claim experience read live from the pricing
team's own schema** — 50,000 policies and 47,521 claims, not copied.

That matters for two reasons:

**It is the cross-team point, made concrete.** Pricing already owns policy and premium on the
platform. Reserving reads them *in place* as a view — no second copy to reconcile, no extract to go
stale. One book of business, two teams consuming it.

**It gives you the denominator.** Ultimates alone are a numerator. With premium present, the loss
ratio becomes a governed measure rather than something each analyst recomputes — GBP 2.24bn earned
premium and GBP 260.5bn sum insured across 15 SIC codes, so the triangle can be cut at a segment
grain rather than five broad lines.

*(One check is deliberately amber: a minority of claims have no matching policy row. It is a
warning, not a gate — it narrows segment analysis without invalidating the triangle, and it is
reported rather than silently dropped.)*

---

## 9 · R integration

**Where:** [**8_r_indication**](https://fevm-lr-dev-aws-us.cloud.databricks.com/editor/notebooks/64021633005606).

Your indications are built in R and nothing here asks you to change that. R runs natively on
Databricks — as a notebook or a task in the same job as the stages above. The script reads
`demo_stage3_ultimate`, **prints the assumption it is standing on** (selection id, approver,
rationale), computes loss ratios, trends them, credibility-weights, and writes the result carrying
the `applied_selection_id`.

**It ran** — 6 August, R 4.4.0, reading 8 accident years and naming the selection it stood on:

| AY | ultimate | earned premium | LR | trended LR |
|---|---|---|---|---|
| 2022 | 2,004,796 | 3,040,000 | 0.659 | 0.842 |
| 2023 | 1,281,740 | 2,140,000 | 0.599 | 0.728 |
| 2024 | 1,024,863 | 1,610,000 | 0.637 | 0.737 |
| 2025 | 2,067,373 | 3,160,000 | 0.654 | 0.721 |

Weighted trended LR **0.7446** against a permissible **0.62** → **indicated rate change +20.1%**
(5% annual trend, prospective 2027, AY2026 excluded as too immature).

> **Be straight about one nuance if asked.** The SQL pipeline runs on serverless; R needs classic
> compute, so the R ran on a classic cluster with the stage-3 output carried across
> (`indication_e2.R` is that variant). Real execution and real numbers — the cross-workspace hop
> is an artefact of where R runs, not of the design. **Do not claim it ran on serverless.**

**The point:** their logic stays in R and stays theirs. What changes is that the assumption
feeding it is governed upstream, so the indicated rate traces to an approved election instead of a
line in a 5,000-line script.

---

## 10 · Reading Discovery without an ingestion project

Federation connects Databricks to the Discovery SQL Server and queries its tables in place. No
copy, no pipeline, no waiting on One Shield validation.

The honest trade-off: queries execute against Discovery, so its load and performance apply. For
triangle-sized aggregation that's usually fine, and it means you start on real loss data now and
revisit ingestion when the Databricks feeds are verified — rather than the other way round.

**Not connected yet.** It needs connection details, a read account, and network sign-off.

---

## 11 · What we'd need from you

- **The LDF script split on the three seams in §4** — ingestion/prep, the selection and
  intervention point, output. It doesn't need to be tidy or complete. Without it, my intervention
  point sits where I guessed rather than where your decisions actually are, and the exclusion and
  remap rules in stage 1 are plausible stand-ins rather than yours.
- **One sample R indication** (synthetic is fine) — enough to wire stage 4 to your real calculation.
- **Federation details for Discovery** — connection, read account, network approval.

Then the sequence is: wire Federation → run your real rules through the three stages →
**reconcile against one of your actual quarters**. That last step is the one that earns trust, and
it hasn't been done.

---

## 12 · Anticipated questions

**"This looks like reserving."** Same loss-development mathematics, different consumer — you
develop losses to ultimate to reach a loss cost and an indicated rate; a reserving team books a
liability. Building once and letting both consume is a feature.

**"Our loss data can't move yet."** It doesn't need to. Federation reads Discovery in place; the
triangle is a view over whatever it reads.

**"Can we keep R?"** Yes — natively, as a stage in the flow rather than a separate system.

**"Can the selection happen in a tool we already use?"** Yes, and there's a concrete demonstration
rather than an assurance. Open **7_analyst_selection** (link in §0): it reads stage 2, shows every line of
business at once, five averaging bases side by side, an ad-hoc "what if we drop AY2023" exclusion
and a tail-factor range — then **writes to the same `selected_development_pattern` table the app
writes to**, as `PENDING_APPROVAL`. Both rows appear in the same audit trail and stage 3's guard
treats them identically.

**The line:** *the app is for the sign-off moment, the notebook is for the analyst who wants to dig
— and the governed record doesn't care which door the decision came through.* If a notebook can
write a first-class selection, so can R, and so can an external actuarial tool. There's a source
field on the row for exactly that, so you're not locked in either direction.

**"What if it fails halfway?"** Each stage is a separate task — only the failed stage reruns.

**"Who can override, and is that controlled?"** Every selection records author and reason, and an
override can be routed for a second person's approval before use. The prototype shows the
recording; the routing is the same mechanism used elsewhere in the app.

**"Can you do closed-with-pay or reported count bases?"** Not built. Identical shape — the same
window functions over a count instead of an amount. A small addition to stage 2. *(Don't imply
they exist.)*

---

*Bricksurance SE is a fictional carrier and all data is synthetic. The methodology is illustrative
rather than certified — the intent is to show the shape of the workflow, not to propose a factor
selection. Every screen reads a real governed table, view or function.*
