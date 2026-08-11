-- ============================================================================
-- REVIEW AND APPROVE A SELECTION — without the app
--
-- Answers a question the demo order raises: at step 3 (the Job) the pipeline
-- stops for a human. Where does that human do their review? The app is one door,
-- not the only one — and it matters that it is not the only one, because a
-- reviewer who lives in SQL should not have to adopt a web app to sign something.
--
-- The guard on stage 3 keys on APPROVAL (status_code = 'APPROVED' and
-- approved_by set), NOT on which tool wrote it. So all three of these are
-- equivalent as far as the pipeline is concerned:
--
--   * the app          — Triangle & selection -> Select & save -> Approve
--   * a notebook       — 7_analyst_selection writes the row, an approver updates it
--   * this SQL         — read the evidence, then approve in one statement
--
-- Same governed row, same audit trail, same stage-3 behaviour, either way.
-- ============================================================================

USE CATALOG lr_dev_aws_us_catalog;
USE SCHEMA reserving_workbench;


-- ── 1 · WHAT AM I BEING ASKED TO APPROVE? ───────────────────────────────────
-- Everything a reviewer needs on one screen: what is proposed, what it replaces,
-- who proposed it, and the reason they gave.
SELECT
  selection_id,
  source_code                       AS proposed_by_tool,
  selected_by                       AS proposed_by,
  status_code,
  development_factors,
  tail_factor,
  rationale
FROM selected_development_pattern
WHERE line_of_business_code = 'COMMERCIAL_PROPERTY'
  AND status_code = 'PENDING_APPROVAL'
ORDER BY selected_at DESC;


-- ── 2 · IS IT DEFENSIBLE? proposed vs empirical vs prior, factor by factor ───
-- The comparison an actuary actually wants: three patterns side by side. Nothing
-- here trusts the proposer's own summary — the empirical column is recomputed
-- from the triangle.
WITH proposed AS (
  SELECT selection_id, posexplode(from_json(development_factors, 'array<double>')) AS (step_idx, factor)
  FROM selected_development_pattern
  WHERE line_of_business_code = 'COMMERCIAL_PROPERTY' AND status_code = 'PENDING_APPROVAL'
),
prior AS (
  SELECT posexplode(from_json(development_factors, 'array<double>')) AS (step_idx, factor)
  FROM selected_development_pattern
  WHERE line_of_business_code = 'COMMERCIAL_PROPERTY'
    AND selection_id = 'SEL-2026Q3-PROP-PRIOR'
),
empirical AS (
  SELECT step_idx, empirical_factor AS factor
  FROM demo_stage2_comparison
  WHERE line_of_business_code = 'COMMERCIAL_PROPERTY'
)
SELECT
  p.step_idx                                              AS step,
  ROUND(e.factor, 4)                                      AS empirical,
  ROUND(pr.factor, 4)                                     AS prior_selection,
  ROUND(p.factor, 4)                                      AS proposed,
  CASE WHEN ABS(p.factor - pr.factor) < 0.0005 THEN 'held prior'
       WHEN ABS(p.factor - e.factor)  < 0.0005 THEN 'took empirical'
       ELSE 'neither — judgement' END                     AS what_they_did,
  ROUND(p.factor - e.factor, 4)                           AS vs_empirical
FROM proposed p
LEFT JOIN prior pr     ON pr.step_idx = p.step_idx
LEFT JOIN empirical e  ON e.step_idx  = p.step_idx
ORDER BY p.step_idx;


-- ── 3 · WHAT DOES IT DO TO THE ANSWER? ──────────────────────────────────────
-- A reviewer should see the consequence before signing, not after. This is the
-- same arithmetic stage 3 will do, run against the proposed factors.
WITH proposed AS (
  SELECT from_json(development_factors, 'array<double>') AS factors, tail_factor
  FROM selected_development_pattern
  WHERE line_of_business_code = 'COMMERCIAL_PROPERTY' AND status_code = 'PENDING_APPROVAL'
  ORDER BY selected_at DESC LIMIT 1
),
latest AS (
  SELECT accident_year, MAX(development_lag) AS latest_lag,
         MAX_BY(cum_paid, development_lag) AS cum_paid_latest
  FROM demo_stage2_triangle
  WHERE line_of_business_code = 'COMMERCIAL_PROPERTY'
  GROUP BY accident_year
)
SELECT
  l.accident_year,
  l.cum_paid_latest,
  ROUND(l.cum_paid_latest * AGGREGATE(
    SLICE(p.factors, l.latest_lag + 1, GREATEST(SIZE(p.factors) - l.latest_lag, 0)),
    CAST(1.0 AS DOUBLE), (acc, x) -> acc * x) * p.tail_factor, 2) AS ultimate_if_approved
FROM latest l CROSS JOIN proposed p
ORDER BY l.accident_year;


-- ── 4 · APPROVE IT ──────────────────────────────────────────────────────────
-- One statement. Set your own name — the point of the audit trail is that it
-- records a person, not a service account. Stage 3's guard opens the moment this
-- commits, because the guard keys on approval rather than on the app.
--
-- Uncomment, set the reviewer, run.
--
-- UPDATE selected_development_pattern
--    SET status_code = 'APPROVED',
--        approved_by = 'john.mcginn@hiscox.com',      -- <- a named human
--        approved_at = current_timestamp()
--  WHERE line_of_business_code = 'COMMERCIAL_PROPERTY'
--    AND status_code = 'PENDING_APPROVAL';


-- ── 5 · ...OR REJECT IT, WHICH IS ALSO A DECISION WORTH RECORDING ────────────
-- Rejection is not "do nothing". The proposal happened and the fact it was
-- turned down is part of the story of how the number was set.
--
-- UPDATE selected_development_pattern
--    SET status_code = 'REJECTED',
--        approved_by = 'john.mcginn@hiscox.com',
--        approved_at = current_timestamp(),
--        rationale   = rationale || ' | REJECTED on review: empirical spike is '
--                   || 'genuine deterioration, not a one-off — do not hold the prior.'
--  WHERE line_of_business_code = 'COMMERCIAL_PROPERTY'
--    AND status_code = 'PENDING_APPROVAL';


-- ── 6 · CONFIRM: the guard now sees an approved pattern ──────────────────────
SELECT selection_id, status_code, selected_by, approved_by, approved_at
FROM selected_development_pattern
WHERE line_of_business_code = 'COMMERCIAL_PROPERTY'
  AND status_code = 'APPROVED'
  AND approved_by IS NOT NULL;
-- Zero rows here => stage 3 will fail with its guard message.
-- One or more    => re-run stage 3 (or the stage-3 job) and it produces the loss cost.


-- ============================================================================
-- THE POINT TO MAKE
--
-- The review is a governed row transition, not a screen. Whoever does it — in the
-- app, in a notebook, in SQL, or in an external tool that writes the same row —
-- the pipeline behaves identically and the audit trail records the same facts:
-- who proposed, who approved, on what basis, and why.
--
-- That is what makes the app "an easy interface on top" rather than the product.
-- ============================================================================
