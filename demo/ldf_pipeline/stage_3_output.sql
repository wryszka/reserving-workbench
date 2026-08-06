-- ============================================================================
-- STAGE 3 of 3 — OUTPUT / FORMATTING  (feeds the indication)
--
-- Applies the ELECTED pattern to develop losses to ultimate and produces the
-- loss-cost table the R indication consumes. Note the guard: this stage will
-- not produce output unless a human has elected an APPROVED pattern in Stage 2.
-- That is the difference from the monolith, where the empirical pick flowed
-- straight through whether anyone looked at it or not.
--
-- Reads:  demo_stage2_triangle, selected_development_pattern (ELECTED)
-- Writes: demo_stage3_ultimate  <- the contract the R indication reads
-- ============================================================================

USE CATALOG lr_dev_aws_us_catalog;
USE SCHEMA reserving_workbench;

-- ── GUARD · refuse to run on an unelected pattern ──────────────────────────
-- Returns the elected row; if this is empty, STOP — Stage 2 is unresolved.
SELECT
  selection_id, source_code, status_code, selected_by, approved_by, rationale
FROM selected_development_pattern
WHERE status_code = 'APPROVED'
  AND selection_id LIKE '%ELECTED%'
  AND line_of_business_code = 'COMMERCIAL_PROPERTY';
-- ^ zero rows  => do not proceed. one row => that is your governed assumption.

-- 3a · develop to ultimate using the ELECTED factors -------------------------
CREATE OR REPLACE TABLE demo_stage3_ultimate
COMMENT '[reserving-workbench] Stage 3/3 - losses developed to ultimate on the ELECTED pattern. The loss-cost contract the R indication reads.'
AS
WITH elected AS (
  SELECT
    line_of_business_code,
    selection_id,
    source_code,
    tail_factor,
    from_json(development_factors, 'array<double>') AS factors
  FROM selected_development_pattern
  WHERE status_code = 'APPROVED'
    AND selection_id LIKE '%ELECTED%'
),
latest AS (   -- latest observed diagonal per accident year
  SELECT
    t.line_of_business_code,
    t.accident_year,
    MAX(t.development_lag) AS latest_lag,
    MAX_BY(t.cum_paid, t.development_lag) AS cum_paid_latest
  FROM demo_stage2_triangle t
  GROUP BY t.line_of_business_code, t.accident_year
)
SELECT
  l.line_of_business_code,
  l.accident_year,
  l.latest_lag,
  l.cum_paid_latest,
  e.selection_id                                   AS applied_selection_id,
  e.source_code                                    AS applied_selection_source,
  -- cumulative development factor = product of remaining steps x tail
  ROUND(
    AGGREGATE(
      SLICE(e.factors, l.latest_lag + 1, GREATEST(SIZE(e.factors) - l.latest_lag, 0)),
      CAST(1.0 AS DOUBLE), (acc, x) -> acc * x
    ) * e.tail_factor
  , 4)                                             AS cdf_to_ultimate,
  ROUND(
    l.cum_paid_latest *
    AGGREGATE(
      SLICE(e.factors, l.latest_lag + 1, GREATEST(SIZE(e.factors) - l.latest_lag, 0)),
      CAST(1.0 AS DOUBLE), (acc, x) -> acc * x
    ) * e.tail_factor
  , 2)                                             AS ultimate_loss,
  current_timestamp()                              AS produced_at
FROM latest l
JOIN elected e ON e.line_of_business_code = l.line_of_business_code;

-- ── OUTPUT · what the indication consumes ──────────────────────────────────
SELECT
  accident_year,
  cum_paid_latest,
  cdf_to_ultimate,
  ultimate_loss,
  applied_selection_source AS assumption_source,
  applied_selection_id     AS assumption_id     -- full audit trail back to the election
FROM demo_stage3_ultimate
ORDER BY accident_year;
