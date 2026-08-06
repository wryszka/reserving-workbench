# Do we have policy/claims tables and a visible ingestion process? — honest answer

**Internal note.** Written in response to: *"we need policy and claims tables to show this, no?
do we have explicitly visible ingestion process here? what else is needed?"*

---

## 1 · What exists, verified just now

| Thing | Status |
|---|---|
| **Claims** — `1_raw_claim` (366 claims: id, policy_id, accident year, loss date, LOB, report date) | ✅ real |
| **Claim movements** — `1_raw_claim_transaction` (~4,700 rows: indemnity, expense, recovery, case movement) | ✅ real |
| **Policy table** | ❌ **does not exist** |
| **Premium / exposure** | ❌ **does not exist anywhere in the schema** |
| **Ingestion process, visible** | ⚠️ **two half-answers, neither is a pipeline** — see §3 |

`1_raw_claim` carries a `policy_id`, but it's a dangling reference: there is no policy table for it
to join to. So the claim side is genuinely there and the **policy side is a foreign key pointing at
nothing.**

---

## 2 · Why the missing policy/premium side matters more for pricing than reserving

For reserving you can get a long way on claims alone — the triangle, the factors, IBNR. That's why
the gap hasn't hurt us until now.

For **pricing** it's structural:

- **Loss ratio needs earned premium.** It's the denominator. No premium, no loss ratio — and their
  process is literally called the quarterly loss ratio process.
- **Rate indication needs exposure.** Loss cost per unit of exposure is the thing being indicated.
- **They price by segment** (state / class / programme), and segment comes off the **policy**, not
  the claim.

So the pipeline we're showing produces **ultimates** — the numerator only. The R indication papers
over this by hardcoding premium as a data frame. That's fine as an illustration of R consuming a
governed assumption; it is not a loss ratio.

**The saving grace, and it's a good one:** Rich told us in July that **premium has already migrated
to Databricks** — it's the loss side stuck in Discovery. So the half we're missing is the half
they've already done. That makes it their obvious next step rather than our hole.

---

## 3 · Is the ingestion process visible? Not really — and this is the weaker half

Two things exist and neither is what a pricing team means by "ingestion":

**a · `1_raw_data_feed` + the six data controls (in the app).** Feed arrival, SLA, DQ checks by
Solvency II dimension, reconciliation to the ledger, a data-owner sign-off gate, class-mapping
change detection. This is genuinely strong — but it's **control and monitoring over data that is
already there**. It describes a landed state; it doesn't show anything landing.

**b · `stage_0_source_sync` (new, in the job).** Declares the source binding as views
(`demo_src_claim`, `demo_src_claim_transaction`) and writes a provenance manifest — what was
pulled, from where, how (federation vs scheduled copy-in), when. It makes the "repoint one file
when the source moves" argument concrete and it runs as task 0 of the job.

**What's missing:** an actual *movement of data from somewhere into here*. No Federation connection
to a real external source, no ingest job reading files or a database, nothing to watch land. If
John asks *"show me the data arriving"*, we show a manifest row that says it arrived — which is a
record, not a demonstration.

---

## 4 · What's needed, in order of value per hour

**1 · Premium/exposure table (highest value, small).** A `1_raw_policy` and
`1_raw_premium_earned` by accident year × segment, joined to `demo_stage3_ultimate` → **loss ratio
as a governed measure** instead of an R-local calculation. This converts the demo from "we develop
losses" to "we produce your loss ratio", which is the process they named. It also gives the metric
view something a pricing analyst actually wants to pull into Excel.

**2 · A real Federation connection (highest credibility, needs them).** Even to a throwaway
external database, so "federate, don't migrate" is a thing they watch work rather than a claim.
Needs their connection details for the real version; a stand-in could be stood up on our side.

**3 · Segment grain on the policy table.** State / class / programme, so the triangle can be cut
the way they actually price. Our five broad lines are a toy at their granularity, and this is the
first thing that will look wrong to them.

**4 · One visible landing step.** Even a small scheduled copy-in from a file or an external table
into `1_raw_*`, so there is a task in the job that demonstrably brings data in.

---

## 5 · How to handle it on the call

Don't volunteer the gap unprompted, but don't defend it either. If policy, premium or loss ratio
comes up:

> *"Claims and claim movements are real here — that's what the triangle is built from. Policy and
> premium aren't in this prototype, which is why the indication carries premium as an input rather
> than reading it. Your premium is already on Databricks, so that's the half that's ready to wire —
> and once it is, the loss ratio becomes a governed measure everyone reads the same way instead of
> something each analyst recomputes."*

And if asked to see ingestion:

> *"What you're seeing is the controls over the data once it's landed — reconciliation, completeness,
> the data-owner gate. The landing itself is stage 0 of the job, and today it's a synthetic
> stand-in: it declares the source binding and records the provenance. Wiring it to Discovery over
> Federation is a connection, not a build — that's the next step and it needs your read account."*

Both keep it accurate and both end in something they own.
