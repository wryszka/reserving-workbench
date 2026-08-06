-- ============================================================================
-- THE MONOLITH — one script, start to finish
--
-- ⚠️ PROVENANCE, AND SAY THIS OUT LOUD: this is OUR RECONSTRUCTION, not your
--    script. Yours has not been shared with us yet. We built this from the shape
--    you described on 23 July — one script, no checkpoints, no stopping point,
--    exclusions and remapping buried inside it — so that there is something
--    concrete to decompose. The real one is almost certainly longer, messier and
--    has rules in it we have guessed at. That is precisely why we are asking for it.
--
-- What it does: everything, in one pass. Reads claims, applies the up-front data
-- build, forms the triangle, computes empirical factors, and writes ultimates
-- straight into a final table.
--
-- What it CANNOT do — and this is the whole point of the next three files:
--   * you cannot see where any single transformation happens
--   * you cannot rerun one part of it
--   * there is NO POINT AT WHICH IT STOPS for a human to override an empirical pick
--   * the ultimate is written before anyone has looked at the factors
--
-- Run it if you like — it works. That is what makes the argument: the problem is
-- not that it is broken, it is that it is unreviewable and unstoppable.
--
-- Writes: demo_monolith_ultimate
-- ============================================================================

USE CATALOG lr_dev_aws_us_catalog;
USE SCHEMA reserving_workbench;

CREATE OR REPLACE TABLE demo_monolith_ultimate
COMMENT '[reserving-workbench] The one-script version: claims to ultimates in a single pass, with no checkpoint and no human stopping point. Exists to be decomposed - do not use it for anything.'
AS
WITH
-- ── somewhere in here is the coverage remap ─────────────────────────────────
remapped AS (
  SELECT c.claim_id, c.accident_year, c.line_of_business_code AS orig_lob,
         COALESCE(m.line_of_business_code, c.line_of_business_code) AS line_of_business_code,
         c.policy_id
  FROM `1_raw_claim` c
  LEFT JOIN `1_raw_class_mapping` m
    ON m.source_class_code = CASE c.line_of_business_code
         WHEN 'COMMERCIAL_PROPERTY'    THEN 'PROP-COM-01'
         WHEN 'COMMERCIAL_MOTOR'       THEN 'MOT-FLT-01'
         WHEN 'GENERAL_LIABILITY'      THEN 'LIAB-PL-01'
         WHEN 'PROFESSIONAL_INDEMNITY' THEN 'PI-STD-01'
         WHEN 'MARINE'                 THEN 'MAR-HULL-01' END
),
-- ── ...and here is the large-loss hold-out, and the exclusions ──────────────
-- (note how you would have to read the whole CTE chain to find out that a claim
--  left the base, and there is nothing that records that it did)
filtered AS (
  SELECT r.*
  FROM remapped r
  LEFT JOIN large_loss l ON l.claim_id = r.claim_id
  WHERE l.claim_id IS NULL                    -- large losses dropped, silently
    AND r.claim_id NOT LIKE '%-EXCL-%'        -- exclusion rule, inline
),
movements AS (
  SELECT f.line_of_business_code, f.accident_year,
         t.transaction_year - f.accident_year AS development_lag,
         SUM(CASE WHEN t.claim_transaction_type_code IN ('INDEMNITY_PAYMENT','EXPENSE_PAYMENT')
                  THEN t.amount
                  WHEN t.claim_transaction_type_code = 'RECOVERY' THEN -t.amount
                  ELSE 0 END) AS incr_paid
  FROM filtered f
  JOIN `1_raw_claim_transaction` t ON t.claim_id = f.claim_id
  WHERE t.transaction_year >= f.accident_year
  GROUP BY 1, 2, 3
),
triangle AS (
  SELECT line_of_business_code, accident_year, development_lag,
         SUM(incr_paid) OVER (
           PARTITION BY line_of_business_code, accident_year
           ORDER BY development_lag ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
         ) AS cum_paid
  FROM movements
),
-- ── the factors get computed AND APPLIED in the same breath ─────────────────
-- Nobody sees them. There is no row anywhere recording what was selected, by
-- whom, or why. The next line consumes them.
factors AS (
  SELECT a.line_of_business_code, a.development_lag AS from_lag,
         SUM(b.cum_paid) / NULLIF(SUM(a.cum_paid), 0) AS factor
  FROM triangle a
  JOIN triangle b
    ON  b.line_of_business_code = a.line_of_business_code
    AND b.accident_year         = a.accident_year
    AND b.development_lag       = a.development_lag + 1
  GROUP BY 1, 2
),
latest AS (
  SELECT line_of_business_code, accident_year,
         MAX(development_lag) AS latest_lag,
         MAX_BY(cum_paid, development_lag) AS cum_paid_latest
  FROM triangle GROUP BY 1, 2
),
cdf AS (
  SELECT l.line_of_business_code, l.accident_year, l.cum_paid_latest,
         EXP(SUM(LN(f.factor))) * 1.01 AS cdf_to_ultimate   -- tail hardcoded, mid-script
  FROM latest l
  JOIN factors f
    ON  f.line_of_business_code = l.line_of_business_code
    AND f.from_lag >= l.latest_lag
  GROUP BY 1, 2, 3
)
SELECT line_of_business_code, accident_year, cum_paid_latest,
       ROUND(cdf_to_ultimate, 4) AS cdf_to_ultimate,
       ROUND(cum_paid_latest * cdf_to_ultimate, 2) AS ultimate_loss,
       'no selection recorded' AS applied_selection_id   -- <- the whole problem
FROM cdf
ORDER BY line_of_business_code, accident_year;

-- The output looks perfectly respectable. That is the trap: it is a number with
-- no provenance, produced by factors nobody reviewed, and there was no moment at
-- which anyone could have intervened.
SELECT * FROM demo_monolith_ultimate
WHERE line_of_business_code = 'COMMERCIAL_PROPERTY'
ORDER BY accident_year;
