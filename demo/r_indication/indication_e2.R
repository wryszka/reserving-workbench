# =============================================================================
# RATE INDICATION IN R — portable version (runs on a classic workspace)
#
# Why this file exists: R needs classic compute. The main build lives in a
# serverless workspace, so this variant carries the stage-3 output with it,
# writes it to a governed table in THIS workspace, and then reads it back —
# so the "the indication consumes a governed assumption" point is still made
# for real rather than hardcoded in the script.
#
# Stage 3 output reproduced here is the ACTUAL output of stage_3_output.sql
# (Commercial Property, developed on the ELECTED pattern).
#
# Writes: <catalog>.<schema>.demo_stage3_ultimate   (seeded)
#         <catalog>.<schema>.demo_r_indication      (the result)
# =============================================================================

library(SparkR)
sparkR.session()

# ── configure for this workspace ─────────────────────────────────────────────
CATALOG <- "hive_metastore"   # set after checking write access on this workspace
SCHEMA  <- "lr_reserving_demo"
fq <- function(t) paste0(CATALOG, ".", SCHEMA, ".", t)

sql(paste0("CREATE SCHEMA IF NOT EXISTS ", CATALOG, ".", SCHEMA))

# ── 1 · seed the stage-3 output (real values from the SQL pipeline) ──────────
stage3 <- data.frame(
  line_of_business_code    = rep("COMMERCIAL_PROPERTY", 8),
  accident_year            = as.character(2019:2026),
  cum_paid_latest          = c(1250056.55, 1668030.28, 1662067.36, 1926758.61,
                               1173188.21,  868580.25, 1460096.70,  909945.92),
  cdf_to_ultimate          = c(1.0100, 1.0100, 1.0201, 1.0405,
                               1.0925, 1.1799, 1.4159, 2.3603),
  ultimate_loss            = c(1262557.12, 1684710.58, 1695474.91, 2004796.19,
                               1281739.91, 1024863.26, 2067373.00, 2147773.12),
  applied_selection_id     = rep("SEL-2026Q4-PROP-ELECTED", 8),
  applied_selection_source = rep("PRIOR_SELECTION", 8),
  stringsAsFactors         = FALSE
)
saveAsTable(as.DataFrame(stage3), fq("demo_stage3_ultimate"),
            source = "delta", mode = "overwrite")
cat("Seeded", fq("demo_stage3_ultimate"), "\n")

# ── 2 · read it back as a governed table (the actual demo beat) ─────────────
ultimate <- collect(sql(sprintf("
  SELECT accident_year, cum_paid_latest, cdf_to_ultimate, ultimate_loss,
         applied_selection_id, applied_selection_source
  FROM %s
  WHERE line_of_business_code = 'COMMERCIAL_PROPERTY'
  ORDER BY accident_year", fq("demo_stage3_ultimate"))))

cat("Read", nrow(ultimate), "accident years from Unity Catalog\n")

# ── 3 · the assumption this indication stands on ─────────────────────────────
# In the serverless build this is read from selected_development_pattern.
cat("\n--- Assumption behind this indication ---\n")
cat("selection :", ultimate$applied_selection_id[1], "\n")
cat("source    :", ultimate$applied_selection_source[1], "\n")
cat("approved  : chief.actuary\n")
cat("rationale : Overrode the empirical 12-24m factor (distorted by a late-reported\n")
cat("            large loss) and held the prior 1.667x pattern; the large loss is\n")
cat("            reserved individually.\n\n")

# ── 4 · the indication ───────────────────────────────────────────────────────
earned_premium <- data.frame(
  accident_year  = as.character(2019:2026),
  earned_premium = c(2050000, 2630000, 2700000, 3040000, 2140000,
                     1610000, 3160000, 3310000),
  stringsAsFactors = FALSE
)

ind <- merge(ultimate, earned_premium, by = "accident_year")
ind$ultimate_loss <- as.numeric(ind$ultimate_loss)
ind$loss_ratio    <- ind$ultimate_loss / ind$earned_premium

ANNUAL_TREND      <- 0.05
PROSPECTIVE_YR    <- 2027
TARGET_LOSS_RATIO <- 0.62

ind$years_of_trend   <- PROSPECTIVE_YR - as.numeric(ind$accident_year)
ind$trended_lr       <- ind$loss_ratio * (1 + ANNUAL_TREND) ^ ind$years_of_trend
ind$indicated_change <- ind$trended_lr / TARGET_LOSS_RATIO - 1

# AY2026 excluded — at one development period it is too immature to weight.
w <- c("2022" = 0.15, "2023" = 0.20, "2024" = 0.25, "2025" = 0.40)
recent <- ind[ind$accident_year %in% names(w), ]
recent$weight <- as.numeric(w[recent$accident_year])
overall <- sum(recent$trended_lr * recent$weight) / sum(recent$weight)
overall_indication <- overall / TARGET_LOSS_RATIO - 1

cat("--- Indication by accident year ---\n")
print(ind[, c("accident_year", "ultimate_loss", "earned_premium",
              "loss_ratio", "trended_lr", "indicated_change")], digits = 4)

cat(sprintf("\nWeighted trended loss ratio : %.4f\n", overall))
cat(sprintf("Target (permissible) LR     : %.4f\n", TARGET_LOSS_RATIO))
cat(sprintf(">>> INDICATED RATE CHANGE   : %+.2f%%\n", overall_indication * 100))

# ── 5 · write the result, carrying the assumption id ────────────────────────
out <- data.frame(
  line_of_business_code = "COMMERCIAL_PROPERTY",
  prospective_year      = PROSPECTIVE_YR,
  weighted_trended_lr   = overall,
  target_loss_ratio     = TARGET_LOSS_RATIO,
  indicated_rate_change = overall_indication,
  annual_trend          = ANNUAL_TREND,
  applied_selection_id  = ultimate$applied_selection_id[1],
  produced_by           = "indication_e2.R",
  stringsAsFactors      = FALSE
)
saveAsTable(as.DataFrame(out), fq("demo_r_indication"),
            source = "delta", mode = "overwrite")

cat("\nWrote", fq("demo_r_indication"), "\n")
