# LDF Process on Databricks — Prototype Review

**For:** Hiscox US Pricing — John McGinn, Richard Derr (+ Scott Klepetka, Imogen Hirsh)
**Date:** 6 August 2026 · **Prototype:** https://reserving-workbench-7474656169654171.aws.databricksapps.com

---

## 1 · What we understood you needed

From our conversation on 23 July, the picture we took away:

**Where you are today.** The LDF process runs on-premises in Discovery (SQL Server) as a single
large SQL script. Three things about that hurt:

- **You can't see into it.** It's one script, so identifying where a particular transformation
  happens is hard.
- **You can't restart part of it.** If it fails, the whole thing reruns.
- **You can't stop it to intervene.** There's no point at which someone can override an
  empirical pick — for example holding a prior LDF pattern because a data anomaly distorted
  this period's factor — before it flows into the final tables.

**And a data constraint.** Premium has moved to Databricks, but loss data from One Shield is
still being validated, so Discovery stays the source for losses until those feeds are verified.
Nothing here should depend on that validation finishing.

**What you asked to see.** Three specific capabilities:

| # | Your ask | Where it is below |
|---|---|---|
| 1 | **Triangle visualisation** — see the losses and the empirically calculated LDFs *before* anything is selected | §3 |
| 2 | **Comparison** — the empirical factors against a previously selected set | §4 |
| 3 | **A decision module** — take the empirical pick, or hold the prior one, as a deliberate step | §4 |

Plus two things to explore: **R integration**, since indications are built in R; and reading
Discovery **without an ingestion project**.

**What we said we'd do.** Build a prototype showing a staged workflow, the manual intervention
point, and the R options — and review it today.

> **One framing note.** What follows uses loss-development machinery that reserving teams also
> use. That's deliberate and it's the point: it's the same technique, and here it's serving a
> **rate indication**, not a booked reserve. Build it once, and both teams consume it.

---

## 2 · The shape of the answer

One flow, four stages, each stoppable and inspectable:

**Read Discovery in place → build the triangle and empirical LDFs → compare and decide (recorded)
→ hand the selected pattern to your R indication.**

That's the whole architecture. The alternatives we walked through on the 23rd — a visual
flow-builder, notebooks with parameter widgets, a custom app — aren't competing options; they're
just different front doors to the same staged flow, chosen per audience. What matters is that the
stages exist as separate steps, and that stage three is a decision a person makes.

---

## 3 · Ask #1 — the triangle and the empirical LDFs, before selection

Open **Triangle & selection** (Commercial Property).

- The **cumulative paid triangle** — accident year down, development month across; shaded cells
  are observed.
- Below it, the **empirical age-to-age factors**, volume-weighted, calculated from that triangle.
  Nothing has been selected yet: this is what the data says.

Two things worth pointing out:

**The triangle is a view, not an output.** It's derived from the loss ledger on read, so it
reconciles to source by construction and there's no separately-stored copy to drift. No script
produced it, so there's nothing to rerun.

**The factor is a callable function, not a line buried in a script.** In a query tab:

```sql
SELECT lr_dev_aws_us_catalog.reserving_workbench.fn_empirical_ldf('COMMERCIAL_PROPERTY', 0);
-- 1.897191    (the 12 to 24 month factor)
```

Callable from SQL, from the app, from a notebook — one definition, one answer, version-controlled.
That's the direct contrast with "somewhere in 5,000 lines".

**On Discovery:** today this reads synthetic loss data. Pointing it at Discovery is a connection,
not a migration — the triangle view sits on top of whatever it reads, so nothing here waits on the
One Shield validation.

---

## 4 · Asks #2 and #3 — compare against the prior set, then decide

Still on **Triangle & selection**, this is the beat that matters most.

**First, what the comparison shows you.** In the individual factors by accident year:

| Accident year | 12 to 24 month factor |
|---|---|
| 2019 | 1.667 |
| 2020 | 1.676 |
| 2021 | 1.667 |
| 2022 | 1.667 |
| **2023** | **3.627** — flagged |
| 2024 | 1.667 |
| 2025 | 1.667 |

One accident year develops at more than twice the rate of every other. It's a single
late-reported large loss. The volume-weighted average across all years is **1.897** — dragged up
by that one year; hold it out and you're back to roughly **1.667**.

This is exactly the case you described: an empirical pick you would not want flowing through
untouched.

**Then, the decision module.** Below the factors:

- Change the **averaging basis** (volume-weighted / simple / last-N / median / geometric) and the
  factors recompute live.
- Or **type over any single factor**. Change the first from **1.897 to 1.667**. The ultimate
  recomputes immediately: **£15.25m to £14.94m**. You see the consequence of the decision before
  committing it.
- The **prior selected pattern** sits alongside for comparison, with the difference against it shown.
- Add a one-line reason, then **Select & save**.

**What that writes.** A new row — who, when, which basis, the factors, whether anything was
overridden, and why. The previous selection isn't overwritten; it's still there as the prior. So
the audit trail reads *prior, then empirical (proposed), then selected with reason*:

| Selection | Source | Status | First factor |
|---|---|---|---|
| SEL-2026Q3-PROP-PRIOR | prior selection | approved | 1.667 |
| SEL-2026Q4-PROP-EMPIRICAL | calculated | draft | 1.897 |
| SEL-2026Q4-PROP-ELECTED | held prior | approved | 1.667 *(with reason recorded)* |

That's the stop-and-override point the current process can't offer — and it's a recorded decision
rather than an edit someone remembers making.

---

## 5 · R integration

Your indications are built in R, and nothing here asks you to change that.

R runs natively on Databricks — as a notebook or as a task inside the same job as the stages
above. Your indication code reads the **selected** pattern from the same governed table the
decision module wrote to, so the factor feeding the indication is provably the one that was
chosen and approved.

Practically, the R step becomes stage four of the flow: it runs when the selection is approved,
and if it fails, it's the only stage that reruns.

*We haven't wired your actual code yet — that needs the sample you were going to send. The
connection point is ready for it.*

---

## 6 · Reading Discovery without an ingestion project

Federation connects Databricks to the Discovery SQL Server and queries its tables in place. No
copy, no pipeline, no waiting on One Shield.

It's worth being straight about the trade-off: queries execute against Discovery, so its load and
its performance apply. For triangle-sized aggregation that's usually fine, and it means you can
start on the real loss data now and revisit ingestion when the Databricks feeds are verified —
rather than the other way round.

---

## 7 · What we'd need from you to take this further

Two things from the 23rd that would let us move from prototype to your actual process:

- **The LDF script, split into three parts** — (1) ingestion and pre-processing, (2) the selection
  and intervention point, (3) final output and formatting. That split is what turns the stages
  above into *your* stages.
- **A sample of the R indication code** (synthetic is fine) — enough to wire stage four to your real
  calculation.

And from our side: a Federation connection to Discovery, once access is confirmed.

---

## 8 · Anticipated questions

**"This looks like reserving."** Same loss-development mathematics, different consumer — you're
developing losses to ultimate to get to a loss cost and an indicated rate; a reserving team uses
it to book a liability. Building it once and letting both consume it is a feature.

**"Our loss data can't move yet."** It doesn't need to. Federation reads Discovery in place, and
the triangle is a view over whatever it reads.

**"Can we keep R?"** Yes — it runs natively, and it's a stage in the flow rather than a separate
system.

**"Can the selection happen in a tool we already use?"** Yes. The selection stage is a defined
hand-off point: prepare the triangle here, make the pick wherever you prefer, read the chosen
pattern back into the same recorded table. The stages either side don't change.

**"What if the process fails halfway?"** Each stage is a separate task, so only the failed stage
reruns — that was one of the specific problems with the single script.

**"Who can override, and is that controlled?"** Every selection records its author and reason, and
an override can be routed for a second person's approval before it's used. Today's prototype shows
the recording; the routing is the same mechanism used elsewhere in the app.

---

*Bricksurance SE is a fictional carrier and all data here is synthetic. The methodology is
illustrative rather than certified — the intent is to show the shape of the workflow, not to
propose a factor selection. Every screen reads a real governed table, view or function.*
