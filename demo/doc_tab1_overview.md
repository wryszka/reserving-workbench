# LDF on Databricks — the two open asks, answered

## Why this document

At the discovery session we agreed two things would come back to us: a **simplified
version of the LDF script, split into three parts**, and **sample R code** for the
indications. Neither has arrived yet — so rather than wait, both have been built out
on **synthetic data** so the mechanics can be reviewed and agreed now. When the real
script and R code land, they drop into the same seams.

Everything described here **runs for real** on Databricks (Unity Catalog, SQL
warehouse) — with one clearly-flagged exception noted on the R tab.

## The problem being solved

The LDF process today lives in one large SQL script on the on-prem Discovery database.
Three consequences, all of which came up in the session:

- **Opacity** — it is hard to find where any particular transformation happens.
- **All-or-nothing** — if it fails, the whole thing reruns.
- **No intervention point** — there is no way to stop the process and override an
  empirical pick (for example, holding a prior LDF pattern where a data anomaly has
  distorted the empirical factor) before it flows into the final tables.

Plus two constraints we are designing around: loss data must come from **Discovery**
for now (the OneShield feed is still being validated — that is a source-system matter,
not a Databricks one), and the indications themselves are written in **R** and should
stay that way.

## The shape of the answer

One opinionated flow, rather than the five options sketched at discovery:

> **Federation reads Discovery → triangle and empirical LDFs computed in Databricks →
> selection (in Databricks, or in an external tool) → elect / override, audited →
> feeds the R indication.**

The runners-up are persona choices, not open questions: Lakeflow Designer if a
visual-first build is preferred, notebook widgets for analyst-driven parameters.

## What is on the other tabs

| Tab | Contents |
|---|---|
| **2 · The three-part pipeline** | The script decomposed into prep / selection / output, with the verified output of each stage |
| **3 · R indication** | The indication in R, consuming the governed pattern — plus an honest note on what has and has not been executed |
| **4 · What we need from you** | The two items still owed, and the Federation wire-up |

## A note on the data

Everything shown uses a **synthetic** claim ledger for a fictional insurer, and the
methodology is **illustrative rather than certified**. The point is the mechanics —
the staging, the intervention point, the audit trail and the contract the indication
reads — not the numbers themselves. Every table and view referenced is a real,
governed Unity Catalog object.
