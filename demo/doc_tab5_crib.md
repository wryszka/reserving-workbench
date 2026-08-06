# Crib sheet — what they asked, how I answered

> **Internal note to self — not for sharing.** The other tabs are written customer-safe;
> this one is candid, including what is *not* built. Delete or move it before sending
> the document to anyone at Hiscox.

Every row: their words (or close to them) from the 23 July discovery and Rich's 10 July
email, then the specific thing I point at.

---

## The three complaints about the current process

**You asked about — "it's one giant script, we can't tell where any particular transformation happens."**
*How I responded:* Three named files, split on the seams you asked for — prep, selection,
output. Each one runs on its own and writes a table you can look at. Where large losses
get adjusted is a labelled block in stage 1, not line 3,000-something.
→ *Point at:* tab 2, the stage-1 checkpoint table (365 in base / 1 large loss held out / 53 remapped).

**You asked about — "if it fails, the whole thing has to rerun."**
*How I responded:* Each stage is independent and writes a checkpoint. A failure in output
means re-running output, not re-deriving the loss base. Cheap to re-run, and you can
inspect between stages.
→ *Point at:* the three separate files; each is a `CREATE OR REPLACE TABLE`.

**You asked about — "there's no way to stop the process and override an empirical pick before it flows into the final tables."**
*How I responded:* This is the one I built most deliberately. Stage 2 computes the
factors, compares them to the prior selection, flags what breaches tolerance — **and
stops**. Stage 3 has a hard guard: it looks for an approved election and produces nothing
without one. So an unreviewed empirical pick physically cannot reach the output.
→ *Point at:* the guard at the top of stage 3, and the flagged GL row (2.40 vs 1.90, +26.3%).

---

## John's three explicit asks

**You asked about — triangle visualisation: seeing losses and the empirically-calculated factors before anything is selected.**
*How I responded:* The app's Triangle & LDF page shows the cumulative triangle with the
volume-weighted factor row; stage 2 produces the same thing as a table. Individual factors
per accident year are kept *alongside* the weighted average on purpose — so an outlier is
visible rather than averaged away.

**You asked about — comparison capability: empirical against the previously-selected set.**
*How I responded:* `demo_stage2_comparison` — step by step, prior vs empirical, variance
in absolute and percentage terms, plus a materiality gate that marks anything beyond
tolerance as REVIEW REQUIRED.

**You asked about — a decision module: elect the empirical factors or hold the prior.**
*How I responded:* The election is a governed row, not a code change — who, when, from
which source, old vs new factors, and the stated reason. Nothing is overwritten, a new row
is written, so the history stands. The app shows the chain: prior → empirical (draft) →
elected.

---

## Rich's framing from the 10 July email

**You asked about — starting with development factors on four bases: paid, incurred, closed-with-pay counts, reported counts.**
*How I responded:* Paid and incurred are built and running. **The two count bases are
not built** — I say they follow the identical shape and you swap the measure, which is
true, but do not imply they exist. If pushed: it is a small addition to stage 2, same
window functions over a count rather than an amount.

**You asked about — the up-front data build: large-loss adjustment, claim exclusions, remapping claims to coverages. "Required for every part of our quarterly loss ratio process."**
*How I responded:* All three are in stage 1, each as a named step. The design decision
worth mentioning: excluded claims and held-out large losses are **flagged out, not
deleted** — so you can always see what left the base and why. The remap step flags claims
whose mapping moved since the prior quarter, which is the thing that silently breaks a
triangle year on year.

**You asked about — "we still have data quality issues on the loss side within Databricks. This is a OneShield problem, not a Databricks problem. We'll need to start with Discovery."**
*How I responded:* Agreed, and it does not block us. Lakehouse Federation reads Discovery
in place — no ingestion project, no waiting for the OneShield feed to be validated. The
triangle is a view; it sits on top of whatever it reads. Premium is already in Databricks,
so that half needs nothing.

**You asked about — "build it in a manner that minimises future rework when we transition."**
*How I responded:* The stages talk to each other through a contract (ultimates by accident
year plus the id of the assumption applied). When the loss source moves from Discovery to
Databricks, you change the source binding in stage 1 — stages 2 and 3 and the indication
are untouched.

---

## R

**You asked about — R integration, since the indications are written in R.**
*How I responded:* R runs natively on Databricks, as a notebook or a task in a job, so
your indication code runs unchanged. What changes is that it reads the *elected* pattern
from a governed table, so the indicated rate can name the assumption behind it and who
approved it.

✅ **This now runs.** Executed 6 Aug on a classic Single User cluster, R 4.4.0:
`INDICATED=+20.10%`, reading 8 accident years from Unity Catalog and naming the selection
it stood on. You can say it ran, because it did.

One nuance to be straight about if asked: the SQL pipeline is on **serverless** and R needs
**classic**, so the R ran in a separate classic workspace with the stage-3 output carried
across. Real numbers, real execution, but the cross-workspace hop is an artefact of where R
can run — not the target design. In their environment it is one job with R as a task.

---

## Things I chose to collapse or push back on

**You asked about — the five architecture options I sketched at discovery (Federation, Lakeflow Designer, parameterised jobs, notebook widgets, Apps).**
*How I responded:* Deliberately collapsed to **one** recommended flow rather than leaving
five open. Federation → triangle and factors in Databricks → elect/override, audited →
your R indication. The others are framed as persona choices, not undecided options:
Lakeflow Designer if you want visual-first authoring, notebook widgets for analyst-driven
parameters. Leaving five options open would have handed the design decision back to them.

**You asked about — whether this replaces an external selection tool.**
*How I responded:* No. The selection step is a pluggable seam — Databricks preps the
triangle, the external tool makes the pick, we read it back with the same governance and
record the source. There is an enum on the selection row for exactly this, so you are not
locked in either direction.

---

## What is NOT built — do not overstate

| Gap | If it comes up |
|---|---|
| Closed-with-pay and reported **count** bases | Not built. Same shape, swap the measure. Small addition. |
| ~~R script execution~~ | **Done** — ran 6 Aug, R 4.4.0, +20.10%. Serverless/classic split noted above. |
| **Federation to Discovery** | Demonstrated on synthetic data. The connection is not made — needs their connection details, a read account, and network sign-off. |
| Reconciliation against **their actual quarter** | Not done, and it is the thing that would earn trust. It is step 3 in the sequence on tab 4. |
| Their **real exclusion and remap rules** | Mine are plausible stand-ins. Their real rules are why I want the split script. |

---

## The one thing to keep saying

The demo is not "here is a reserving tool." It is: **the assumption feeding your indicated
rate becomes a governed, audited, reversible decision instead of a line buried in a script
nobody can safely change.** Everything else — the staging, the guard, the audit trail — is
in service of that.

## And the ask to close on

The split script and one sample R indication. Without the first, my intervention point is
placed where I guessed rather than where their decisions actually are.
