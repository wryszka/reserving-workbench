-- ============================================================================
-- STAGE 1 of 3 — DATA PREP  ("the up-front process")
--
-- The part Rich described as required for *every* part of the quarterly
-- loss-ratio process: adjust for large losses, apply claim exclusions, remap
-- claims to coverages. In the monolith this is buried thousands of lines in.
-- Here it is one named, runnable, checkpointed stage that writes a table you
-- can inspect BEFORE anything develops.
--
-- Reads (Lakehouse Federation over Discovery in the real thing; synthetic here):
--   1_raw_claim, 1_raw_claim_transaction, large_loss, 1_raw_class_mapping
-- Writes:
--   demo_stage1_prepared_loss   <- inspectable checkpoint
-- ============================================================================

USE CATALOG lr_dev_aws_us_catalog;
USE SCHEMA reserving_workbench;

CREATE OR REPLACE TABLE demo_stage1_prepared_loss
COMMENT '[reserving-workbench] Stage 1/3 - prepared loss: large-loss adjusted, exclusions applied, coverage remapped. Inspectable checkpoint before development.'
AS
WITH
-- 1a · claim-to-coverage remapping -----------------------------------------
--      source class codes remap to the reporting line of business.
--      changed_since_prior flags a remap that moved claims between lines -
--      exactly the thing that silently breaks a triangle year on year.
remap AS (
  SELECT
    line_of_business_code,
    MAX(CASE WHEN changed_since_prior = 'true' THEN 1 ELSE 0 END) AS lob_remapped
  FROM 1_raw_class_mapping
  GROUP BY line_of_business_code
),

-- 1b · claim exclusions ----------------------------------------------------
--      one NAMED rule per exclusion, reason kept on the row, so the actuary
--      sees WHAT was dropped and WHY - not a silent WHERE clause.
claims AS (
  SELECT
    c.claim_id,
    c.accident_year,
    c.line_of_business_code,
    c.loss_date,
    c.report_date,
    COALESCE(r.lob_remapped, 0) = 1 AS coverage_remapped,
    CASE
      WHEN c.accident_year < 2019 THEN 'excluded_outside_experience_period'
      WHEN DATEDIFF(c.report_date, c.loss_date) > 1095 THEN 'excluded_late_reported_over_3y'
      ELSE NULL
    END AS exclusion_reason
  FROM 1_raw_claim c
  LEFT JOIN remap r ON r.line_of_business_code = c.line_of_business_code
),

-- 1c · transactions rolled to incremental paid / incurred by development lag -
--      development_lag = transaction_year - accident_year (same convention as
--      the governed loss_development view, so this ties out).
txn AS (
  SELECT
    t.claim_id,
    (t.transaction_year - c.accident_year) AS development_lag,
    SUM(CASE WHEN t.claim_transaction_type_code IN ('INDEMNITY_PAYMENT','EXPENSE_PAYMENT')
             THEN t.amount ELSE 0 END) AS paid,
    SUM(t.amount)                       AS incurred   -- payments + case reserve movement
  FROM 1_raw_claim_transaction t
  JOIN 1_raw_claim c ON c.claim_id = t.claim_id
  GROUP BY t.claim_id, (t.transaction_year - c.accident_year)
),

-- 1d · large-loss adjustment ----------------------------------------------
--      losses over threshold are flagged and (per treatment) held OUT of the
--      developable base so they cannot distort the factor; they are reserved
--      individually instead. THIS is the step behind the AY2023 anomaly.
large AS (
  SELECT claim_id, threshold, treatment, distorts_factor
  FROM large_loss
)

SELECT
  cl.claim_id,
  cl.accident_year,
  cl.line_of_business_code,
  x.development_lag,
  x.paid,
  x.incurred,
  cl.coverage_remapped,
  cl.exclusion_reason,
  l.claim_id IS NOT NULL             AS is_large_loss,
  COALESCE(l.treatment, 'in_base')   AS large_loss_treatment,
  -- The developable base. Excluded rows and individually-reserved large losses
  -- are CARRIED but flagged out - never silently deleted.
  CASE
    WHEN cl.exclusion_reason IS NOT NULL           THEN FALSE
    WHEN l.treatment = 'reserved_individually'     THEN FALSE
    ELSE TRUE
  END                                AS in_developable_base,
  current_timestamp()                AS prepared_at
FROM claims cl
JOIN txn x       ON x.claim_id = cl.claim_id
LEFT JOIN large l ON l.claim_id = cl.claim_id
WHERE x.development_lag >= 0;

-- ── CHECKPOINT · inspect before you develop ────────────────────────────────
SELECT 'claims in developable base' AS check_name, COUNT(DISTINCT claim_id) AS value
FROM demo_stage1_prepared_loss WHERE in_developable_base
UNION ALL SELECT 'claims excluded (named rule)', COUNT(DISTINCT claim_id) FROM demo_stage1_prepared_loss WHERE exclusion_reason IS NOT NULL
UNION ALL SELECT 'large losses held out',         COUNT(DISTINCT claim_id) FROM demo_stage1_prepared_loss WHERE large_loss_treatment = 'reserved_individually'
UNION ALL SELECT 'claims coverage-remapped',      COUNT(DISTINCT claim_id) FROM demo_stage1_prepared_loss WHERE coverage_remapped
ORDER BY check_name;
