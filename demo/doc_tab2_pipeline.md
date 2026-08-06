# The three-part pipeline

The monolith decomposed on the three seams requested: **data prep**, **the selection /
intervention point**, and **output**. Three separate files, each independently runnable
and each writing an inspectable table. All three have been run on Databricks; the
figures below are the actual output.

## Stage 1 · Data prep

*The up-front process — required for every part of the quarterly loss-ratio cycle.*

Three things happen here, each as a named, visible step rather than a clause buried in
a longer query:

- **Coverage remapping** — source class codes are mapped to the reporting line of
  business, and any claim whose mapping moved since the prior quarter is flagged. This
  is the thing that quietly breaks a triangle year on year if it goes unnoticed.
- **Claim exclusions** — one named rule per exclusion, with the reason carried on the
  row. Excluded claims are **flagged out, not deleted**, so you can always see what
  left the base and why.
- **Large-loss adjustment** — losses over the threshold are identified and, where the
  treatment says so, held out of the developable base and reserved individually
  instead, so a single claim cannot distort the factor.

**Verified checkpoint output:**

| Check | Value |
|---|---|
| Claims in developable base | 365 |
| Claims excluded by named rule | 0 |
| Large losses held out | 1 |
| Claims coverage-remapped | 53 |

## Stage 2 · Development factors and the intervention point

This is the stage the current process cannot offer: **it computes, compares, and then
stops.**

- **The triangle** is cumulated from the prepared base — for paid and incurred. (The
  count bases, closed-with-pay and reported, follow the identical shape; swap the
  measure.)
- **Empirical age-to-age factors** are produced both as *individual* factors per
  accident year and as the *volume-weighted* average. Keeping the individual factors
  visible is deliberate: an outlier should be seen, not averaged away.
- **The comparison** puts the empirical pattern side by side with the previously
  selected one, step by step, with the variance and a materiality gate.

**Verified comparison output — one step flagged:**

| Line of business | Step | Prior | Empirical | Variance | Status |
|---|---|---|---|---|---|
| General Liability | 0 (12–24m) | 1.90 | 2.40 | +26.3% | **REVIEW REQUIRED** |

Commercial Property came through within tolerance. Its individual factors sit at
approximately **1.667×** across accident years, which is the baseline against which an
anomalous year stands out.

**Then the pipeline stops.** The actuary elects: accept the empirical pattern, or hold
the prior for the affected step. That election is recorded as a governed row — who
elected it, when, from which source, the old and new factors, and the stated reason.
Nothing is overwritten; a new row is written, so the history stands.

## Stage 3 · Output

Applies the **elected** pattern and produces the table the indication consumes.

Note the guard at the top: the stage looks for an **approved election** and produces
nothing without one. An unreviewed empirical pick cannot flow through to the output —
which is the structural difference from the present process.

**Verified ultimates (Commercial Property):**

| Accident year | Cumulative paid | CDF to ultimate | Ultimate loss |
|---|---|---|---|
| 2019 | 1,250,057 | 1.0100 | 1,262,557 |
| 2020 | 1,668,030 | 1.0100 | 1,684,711 |
| 2021 | 1,662,067 | 1.0201 | 1,695,475 |
| 2022 | 1,926,759 | 1.0405 | 2,004,796 |
| 2023 | 1,173,188 | 1.0925 | 1,281,740 |
| 2024 | 868,580 | 1.1799 | 1,024,863 |
| 2025 | 1,460,097 | 1.4159 | 2,067,373 |
| 2026 | 909,946 | 2.3603 | 2,147,773 |

The development factor rises as the accident year gets greener, as it should. Every row
carries the id and source of the selection applied, so any ultimate can be traced back
to the election that produced it and the person who approved it.

## The three points worth taking away

1. **Named stages, not one script.** Each stage runs, is inspected, and re-runs on its
   own. A failure in output does not mean re-running prep.
2. **It stops where a human is needed.** The intervention point is structural, enforced
   by the guard in stage 3 — not a convention someone has to remember.
3. **The decision is data, not a code edit.** Elections are governed rows, so the
   assumption behind any number is auditable and reversible without touching code.
