-- ============================================================================
-- "CAN I SEE INTO MY METHODOLOGY?" — the answer, in five queries
--
-- The real objection is not "the script is in one file". It is: *I cannot see
-- what my own methodology does.* Splitting a monolith into three files does not
-- answer that on its own — you would still be reading files.
--
-- What answers it: the methodology is not in a file at all. It is a governed
-- object in the catalog, and you can ask the catalog what it does, where its
-- numbers come from, what depends on it, and what changed. That is the thing a
-- 5,000-line SQL script fundamentally cannot offer.
--
-- Run these in order on warehouse a3b61648ea4809e3. Every one has been run.
-- ============================================================================


-- ── 1 · WHAT DOES THE FACTOR ACTUALLY DO? ───────────────────────────────────
-- The whole methodology, read out of the catalog. No repo, no file, no author
-- to ask. Ten readable lines instead of "somewhere in 5,000".
SELECT routine_definition
FROM system.information_schema.routines
WHERE routine_schema = 'reserving_workbench'
  AND routine_name   = 'fn_empirical_ldf';

-- Returns:
--   SUM(nxt.cumulative_paid) / NULLIF(SUM(cur.cumulative_paid), 0)
--   ...joined on accident_year, line_of_business, currency, development_lag+1
--
-- Read it out loud to the room. That IS the volume-weighted age-to-age factor:
-- sum of next column over sum of this column. An actuary can audit that in
-- ten seconds and say "yes, that's what I meant".
--
-- Also available, with parameter docs, owner and creation time:
--   DESCRIBE FUNCTION EXTENDED lr_dev_aws_us_catalog.reserving_workbench.fn_empirical_ldf;


-- ── 2 · WHERE DO THE TRIANGLE NUMBERS COME FROM? ────────────────────────────
-- The triangle is a view, so its definition IS its documentation. You can see
-- that paid = indemnity + expense - recovery, and that development_lag is
-- transaction_year - accident_year. Nothing is hidden in a load step.
SELECT view_definition
FROM system.information_schema.views
WHERE table_schema = 'reserving_workbench'
  AND table_name   = 'loss_development';


-- ── 3 · DRILL FROM A FACTOR TO THE CLAIMS BEHIND IT ─────────────────────────
-- The 3.627 factor on AY2023 Commercial Property. Three steps, no detective
-- work: the cell, then what is inside the movement.

-- 3a · the two cells the factor divides (1,942,643.18 / 535,585.92 = 3.627)
SELECT development_lag, cumulative_paid
FROM lr_dev_aws_us_catalog.reserving_workbench.loss_development
WHERE line_of_business_code = 'COMMERCIAL_PROPERTY'
  AND accident_year = 2023
  AND development_lag <= 1
ORDER BY development_lag;

-- 3b · every claim inside that movement, biggest first — the anomaly names itself
SELECT ct.claim_id,
       ct.claim_transaction_type_code,
       round(ct.amount, 0) AS amount
FROM lr_dev_aws_us_catalog.reserving_workbench.`1_raw_claim_transaction` ct
JOIN lr_dev_aws_us_catalog.reserving_workbench.`1_raw_claim` c
  ON c.claim_id = ct.claim_id
WHERE c.accident_year          = 2023
  AND c.line_of_business_code  = 'COMMERCIAL_PROPERTY'
  AND ct.transaction_year      = 2024
  AND ct.claim_transaction_type_code IN ('INDEMNITY_PAYMENT','EXPENSE_PAYMENT')
ORDER BY ct.amount DESC
LIMIT 5;

-- Returns CLM-2023-ANOMALY at 900,000 + 150,000 — one claim, £1.05m, sitting
-- on top of a base of ~40k claims. Factor to cell to claim to transaction, in
-- two queries. In the current process this is the week-three discovery.


-- ── 4 · WHAT ELSE WOULD I BREAK IF I CHANGED IT? ────────────────────────────
-- The question you cannot answer about a monolith. Databricks records lineage
-- automatically as queries run — this is observed, not a diagram someone drew.
SELECT source_table_name, target_table_name, target_type
FROM system.access.table_lineage
WHERE source_table_schema = 'reserving_workbench'
  AND source_table_name   = 'loss_development'
  AND target_table_name IS NOT NULL
GROUP BY 1, 2, 3;

-- (Also available in the UI: Catalog Explorer -> the table -> Lineage tab, which
-- draws the same thing as a graph, including which notebooks and jobs touched it.)

-- And every object in the workbench with its plain-English purpose — the
-- inventory a new joiner would otherwise have to reverse-engineer:
SELECT table_name, comment
FROM system.information_schema.tables
WHERE table_schema = 'reserving_workbench'
  AND comment IS NOT NULL
ORDER BY table_name;


-- ── 5 · WHAT CHANGED, AND WHO CHANGED IT? ───────────────────────────────────
-- The methodology is versioned, so "did someone change the factor logic?" is a
-- query rather than an archaeology project.
DESCRIBE HISTORY lr_dev_aws_us_catalog.reserving_workbench.selected_development_pattern;

-- ...and the decision trail itself: every selection, who made it, on what
-- basis, and why. The assumption behind the indication, in one table.
SELECT selection_id, source_code, status_code, averaging_method_code,
       development_factors, selected_by, approved_by, rationale
FROM lr_dev_aws_us_catalog.reserving_workbench.selected_development_pattern
WHERE line_of_business_code = 'COMMERCIAL_PROPERTY'
ORDER BY valuation_date, selection_id;


-- ============================================================================
-- THE POINT TO MAKE
--
-- "Can I see into my methodology?" — yes, and not because we wrote better
-- documentation. Because the methodology stopped being text in a file and
-- became a governed object the catalog can answer questions about:
--
--   what it does        -> query 1  (its definition, from the catalog)
--   where its inputs    -> query 2  (the view's own definition)
--     come from
--   why a number is     -> query 3  (drill to the claim in two hops)
--     what it is
--   what depends on it  -> query 4  (lineage recorded automatically, not grep)
--   what changed        -> query 5  (version history + decision trail)
--
-- A 5,000-line script can only ever answer the first of those, and only by
-- reading it. That is the difference, and it is not a matter of tidiness.
-- ============================================================================
