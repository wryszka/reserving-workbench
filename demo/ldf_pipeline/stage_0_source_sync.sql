-- ============================================================================
-- STAGE 0 of 3 — SOURCE SYNC  ("getting the loss data in")
--
-- What this is in YOUR environment:
--   Loss data lives in Discovery (SQL Server) and One Shield is still being
--   validated. Two ways in, and they are complementary rather than either/or:
--
--     * Lakehouse Federation — a connection, not a migration. Query Discovery
--       tables in place. Best for access today: nothing to schedule, nothing to
--       wait for, and no copy to drift. Queries execute on Discovery, so its
--       load and performance apply.
--
--     * A scheduled copy-in — for the big fact tables (claim transactions),
--       where you do not want every quarterly rebuild hammering Discovery. This
--       task is where that copy lands, on whatever cadence suits.
--
--   The pattern: federate for access and for the small/reference tables, copy in
--   the large facts on a schedule. Either way stages 1-3 do not change, because
--   only THIS task knows where the data came from.
--
-- What it is HERE: the synthetic ledger is already in the schema, so this task
-- materialises the source-shaped views the pipeline reads and records what it
-- did. That keeps the stage boundary real — when the source moves from Discovery
-- to Databricks-native, this is the only file that changes.
--
-- Writes: demo_stage0_source_manifest   <- what was pulled, from where, when
-- ============================================================================

USE CATALOG lr_dev_aws_us_catalog;
USE SCHEMA reserving_workbench;

-- ── the source contract stages 1-3 depend on ────────────────────────────────
-- Named views, so the binding to a source is declared in exactly one place.
-- Repoint these at a Federation catalog (e.g. discovery.dbo.claim) and nothing
-- downstream is touched.
CREATE OR REPLACE VIEW demo_src_claim
COMMENT '[reserving-workbench] Stage 0 - the claim header as the pipeline sees it. Repoint at a Federation catalog to read Discovery in place; stages 1-3 are unaffected.'
AS SELECT claim_id, policy_id, accident_year, loss_date, line_of_business_code, report_date
   FROM `1_raw_claim`;

CREATE OR REPLACE VIEW demo_src_claim_transaction
COMMENT '[reserving-workbench] Stage 0 - the claim movement ledger as the pipeline sees it. In production this is the large fact table worth a scheduled copy-in rather than federating every rebuild.'
AS SELECT claim_transaction_id, claim_id, transaction_year, transaction_date,
          claim_transaction_type_code, amount, currency_code
   FROM `1_raw_claim_transaction`;

-- ── the manifest: what this run pulled, and from where ──────────────────────
-- A quarterly process needs to be able to answer "which data was this built on?"
-- months later. This is that record.
CREATE OR REPLACE TABLE demo_stage0_source_manifest
COMMENT '[reserving-workbench] Stage 0/3 - provenance of the loss data this pipeline run used: source, access mode, row counts, and when it landed.'
AS
SELECT 'claim'             AS source_object,
       'DISCOVERY (synthetic stand-in)' AS source_system,
       'federation'        AS access_mode,
       COUNT(*)            AS rows_pulled,
       current_timestamp() AS synced_at
FROM demo_src_claim
UNION ALL
SELECT 'claim_transaction',
       'DISCOVERY (synthetic stand-in)',
       'scheduled_copy_in',
       COUNT(*),
       current_timestamp()
FROM demo_src_claim_transaction;

SELECT * FROM demo_stage0_source_manifest;
