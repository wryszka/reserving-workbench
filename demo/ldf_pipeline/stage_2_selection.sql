-- ============================================================================
-- STAGE 2 of 3 — DEVELOPMENT FACTORS + THE SELECTION / INTERVENTION POINT
--
-- This is the stage the monolith cannot give you: it STOPS here.
-- It computes the empirical factors, puts them side by side with the previously
-- selected pattern, and then WAITS. Nothing flows downstream until a human
-- elects a pattern — and the election is a governed row, not a code edit.
--
-- Rich asked for factors on four bases: Paid, Incurred, Closed-with-Pay counts,
-- Reported counts. Paid and Incurred are computed here off Stage 1; the count
-- bases follow the identical shape (swap the measure).
--
-- Reads:  demo_stage1_prepared_loss, selected_development_pattern
-- Writes: demo_stage2_triangle, demo_stage2_empirical_ldf, demo_stage2_comparison
-- ============================================================================

USE CATALOG lr_dev_aws_us_catalog;
USE SCHEMA reserving_workbench;

-- 2a · cumulative triangle, per basis ---------------------------------------
CREATE OR REPLACE TABLE demo_stage2_triangle
COMMENT '[reserving-workbench] Stage 2/3 — cumulative development triangle (paid & incurred) off the prepared base.'
AS
WITH incremental AS (
  SELECT
    line_of_business_code,
    accident_year,
    development_lag,
    SUM(paid)     AS inc_paid,
    SUM(incurred) AS inc_incurred
  FROM demo_stage1_prepared_loss
  WHERE in_developable_base          -- large losses / exclusions already out
  GROUP BY line_of_business_code, accident_year, development_lag
)
-- cumulate along the development axis: a triangle is cumulative by definition,
-- so the age-to-age factors below are >= 1.
SELECT
  line_of_business_code,
  accident_year,
  development_lag,
  SUM(inc_paid)     OVER (PARTITION BY line_of_business_code, accident_year
                          ORDER BY development_lag
                          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_paid,
  SUM(inc_incurred) OVER (PARTITION BY line_of_business_code, accident_year
                          ORDER BY development_lag
                          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_incurred
FROM incremental;

-- 2b · empirical age-to-age factors, both bases ------------------------------
--      individual factors kept alongside the volume-weighted average so the
--      analyst can SEE the outlier rather than having it averaged away.
CREATE OR REPLACE TABLE demo_stage2_empirical_ldf
COMMENT '[reserving-workbench] Stage 2/3 — empirical age-to-age factors (individual + volume-weighted) per basis. The outlier is visible, not hidden.'
AS
WITH stepped AS (
  SELECT
    line_of_business_code,
    accident_year,
    development_lag                                                                       AS from_lag,
    development_lag + 1                                                                   AS to_lag,
    cum_paid                                                                                 AS paid_from,
    LEAD(cum_paid)     OVER (PARTITION BY line_of_business_code, accident_year ORDER BY development_lag) AS paid_to,
    cum_incurred                                                                             AS inc_from,
    LEAD(cum_incurred) OVER (PARTITION BY line_of_business_code, accident_year ORDER BY development_lag) AS inc_to
  FROM demo_stage2_triangle
)
SELECT
  line_of_business_code,
  accident_year,
  from_lag,
  to_lag,
  ROUND(paid_to / NULLIF(paid_from, 0), 4) AS individual_factor_paid,
  ROUND(inc_to  / NULLIF(inc_from , 0), 4) AS individual_factor_incurred,
  -- volume-weighted average across accident years for this step
  ROUND(SUM(paid_to) OVER (PARTITION BY line_of_business_code, from_lag)
        / NULLIF(SUM(paid_from) OVER (PARTITION BY line_of_business_code, from_lag), 0), 4) AS vol_wtd_factor_paid,
  ROUND(SUM(inc_to) OVER (PARTITION BY line_of_business_code, from_lag)
        / NULLIF(SUM(inc_from) OVER (PARTITION BY line_of_business_code, from_lag), 0), 4) AS vol_wtd_factor_incurred
FROM stepped
WHERE paid_to IS NOT NULL;

-- 2c · THE COMPARISON — empirical vs previously selected --------------------
--      ask #2: "compare the empirical pattern against the prior selection".
CREATE OR REPLACE TABLE demo_stage2_comparison
COMMENT '[reserving-workbench] Stage 2/3 — empirical vs prior-selected pattern, step by step, with the variance that triggers review.'
AS
WITH prior_pick AS (
  -- the single most recent APPROVED prior selection per line of business
  SELECT line_of_business_code, development_factors
  FROM (
    SELECT
      line_of_business_code,
      development_factors,
      ROW_NUMBER() OVER (PARTITION BY line_of_business_code ORDER BY selected_at DESC) AS rn
    FROM selected_development_pattern
    WHERE source_code = 'PRIOR_SELECTION' AND status_code = 'APPROVED'
  ) WHERE rn = 1
),
prior AS (
  SELECT
    line_of_business_code,
    posexplode(from_json(development_factors, 'array<double>')) AS (step_idx, prior_factor)
  FROM prior_pick
),
empirical AS (
  -- step_idx is 0-based on the SAME axis as the prior factor array:
  -- step 0 = lag 0 -> 1, step 1 = lag 1 -> 2, ...
  SELECT DISTINCT
    line_of_business_code,
    from_lag            AS step_idx,
    vol_wtd_factor_paid AS empirical_factor
  FROM demo_stage2_empirical_ldf
)
SELECT
  COALESCE(e.line_of_business_code, p.line_of_business_code) AS line_of_business_code,
  COALESCE(e.step_idx, p.step_idx)                           AS step_idx,
  p.prior_factor,
  e.empirical_factor,
  ROUND(e.empirical_factor - p.prior_factor, 4)              AS variance,
  ROUND((e.empirical_factor / NULLIF(p.prior_factor,0) - 1) * 100, 1) AS variance_pct,
  -- a materiality gate: anything beyond tolerance is FLAGGED FOR REVIEW and
  -- must be consciously elected. This is the stop-and-look trigger.
  CASE
    WHEN e.empirical_factor IS NULL OR p.prior_factor IS NULL THEN 'no_comparison'
    WHEN ABS(e.empirical_factor / NULLIF(p.prior_factor,0) - 1) > 0.10 THEN 'REVIEW_REQUIRED'
    ELSE 'within_tolerance'
  END                                                        AS review_status
FROM empirical e
FULL OUTER JOIN prior p
  ON p.line_of_business_code = e.line_of_business_code AND p.step_idx = e.step_idx;

-- ══ INTERVENTION POINT ══════════════════════════════════════════════════════
-- The pipeline STOPS here. Stage 3 refuses to run until an APPROVED election
-- exists (see the guard at the top of stage_3_output.sql).
--
-- 1) Look at what needs a decision:
SELECT * FROM demo_stage2_comparison
WHERE review_status = 'REVIEW_REQUIRED'
ORDER BY line_of_business_code, step_idx;

-- 2) The actuary elects. Either ACCEPT the empirical pattern, or HOLD the prior
--    for the anomalous step. This is a governed INSERT — who, when, why, and
--    where the numbers came from. Nothing is overwritten; it's a new row.
--
--    (Run ONE of these. The second is the AY2023 large-loss case.)
--
-- -- (a) accept empirical wholesale:
-- INSERT INTO selected_development_pattern VALUES (
--   'SEL-2026Q4-PROP-ELECTED', '2026-12-31', NULL, 'COMMERCIAL_PROPERTY', 'GBP',
--   'DATABRICKS_EMPIRICAL', 'VOLUME_WEIGHTED', 5,
--   '[1.8972, 1.2062, 1.078, 1.0532, 1.02, 1.0374, 1.0]', 1.01,
--   'SEL-2026Q4-PROP-EMPIRICAL', 'APPROVED',
--   'Empirical pattern accepted; no distorting events identified this quarter.',
--   'j.mcginn', current_timestamp(), 'chief.actuary', current_timestamp());
--
-- -- (b) HOLD PRIOR for the distorted step (the real decision this quarter):
-- INSERT INTO selected_development_pattern VALUES (
--   'SEL-2026Q4-PROP-ELECTED', '2026-12-31', NULL, 'COMMERCIAL_PROPERTY', 'GBP',
--   'PRIOR_SELECTION', 'VOLUME_WEIGHTED', 5,
--   '[1.667, 1.2062, 1.078, 1.0532, 1.02, 1.0374, 1.0]', 1.01,
--   'SEL-2026Q4-PROP-EMPIRICAL', 'APPROVED',
--   'Held prior 12-24 factor: AY2023 empirical 3.63x distorted by a single late-reported large loss (LL-2023-001, GBP 1.05m) now reserved individually. Remaining steps taken from empirical.',
--   'j.mcginn', current_timestamp(), 'chief.actuary', current_timestamp());
--
-- 3) Then, and only then, run stage 3.
-- ════════════════════════════════════════════════════════════════════════════
