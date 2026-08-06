# The R indication

## The point being made

Your indications are written in R, and they should stay in R. Databricks runs R
natively — as a notebook or as a task inside a job — so the indication code itself does
not need to change.

What *does* change is where the assumption comes from. The script reads the **elected
development pattern** out of a governed table, so the indicated rate can name the exact
selection it stands on, who approved it, and why. Today that assumption is a line
somewhere inside a long script; here it is a referenceable, audited row.

## What the script does

1. Reads the developed losses produced by stage 3 — the ultimates computed on the
   **elected** pattern.
2. Prints the assumption it is standing on: selection id, source, approver, and the
   stated rationale. (This is the governance beat — the indication can always answer
   "which LDF pick produced this?")
3. Computes the indication: loss ratio on ultimate losses, trended to the prospective
   period, credibility-weighted across the relevant accident years, compared against
   the permissible loss ratio.
4. Writes the result back, carrying the selection id — so the indicated rate stays
   traceable to the LDF election.

## Assumptions used (illustrative)

| Parameter | Value |
|---|---|
| Annual trend | 5.0% |
| Prospective year | 2027 |
| Permissible (target) loss ratio | 0.62 |
| Credibility weights | 2022: 0.15 · 2023: 0.20 · 2024: 0.25 · 2025: 0.40 |
| AY2026 | **Excluded** — at one development period it is too immature to carry weight |

## Result

| Accident year | Ultimate | Earned premium | Loss ratio | Trended LR |
|---|---|---|---|---|
| 2022 | 2,004,796 | 3,040,000 | 0.659 | 0.842 |
| 2023 | 1,281,740 | 2,140,000 | 0.599 | 0.728 |
| 2024 | 1,024,863 | 1,610,000 | 0.637 | 0.737 |
| 2025 | 2,067,373 | 3,160,000 | 0.654 | 0.721 |

Weighted trended loss ratio **0.7446** against a permissible **0.62** gives an
**indicated rate change of approximately +20.1%**.

Earned premium here is synthetic. In the real build it comes from the premium tables
already landed in Databricks — which is the half of the picture that is not blocked on
the OneShield loss feed.

## Status — executed

**The R script has been run for real.** Executed on a Databricks classic cluster
(Single User, DBR 16.4 LTS), **R version 4.4.0**, on 6 August 2026.

Console result:

> `R version 4.4.0 (2024-04-24) | rows=8 | selection=SEL-2026Q4-PROP-ELECTED (PRIOR_SELECTION) | weighted_trended_LR=0.7446 | target=0.62 | INDICATED=+20.10%`
>
> per-year: 2022 LR=0.659 trended=0.842 · 2023 LR=0.599 trended=0.728 · 2024 LR=0.637 trended=0.737 · 2025 LR=0.654 trended=0.721

The script read its input from a Unity Catalog table (8 accident years), reported the
selection id and source it was standing on, computed the indication, and wrote the
result back to a governed table carrying that selection id.

One point of transparency on the plumbing: the SQL pipeline runs in a **serverless**
workspace, and R requires **classic** compute — so the R execution ran in a separate
classic workspace, with the stage-3 output carried across and written to a table there
before being read back. The numbers are the genuine stage-3 output and the R execution
is genuine; the cross-workspace hop is an artefact of where R can run today, not part
of the target design. In your environment prep, selection, output and the R indication
would sit in one workspace as tasks in a single job.

## What we would do with your real code

Drop it in place of the illustrative calculation. The contract it reads — ultimate loss
by accident year, plus the id of the assumption applied — does not change, so your
existing indication logic runs unmodified against a governed input. Running it as a task
in the same job puts prep, selection, output and indication in one orchestrated flow
with a single lineage.
