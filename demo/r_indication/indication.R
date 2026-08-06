# =============================================================================
# RATE INDICATION — in R, on Databricks
#
# This is the "your R code runs unchanged" beat. The point being made:
#   * the LDF selection is made and GOVERNED upstream (stage 2 election);
#   * this script CONSUMES the elected pattern from a Unity Catalog table;
#   * so the assumption behind the indication is auditable, and the indication
#     itself stays in the language the pricing team already writes it in.
#
# Runs as: a notebook cell (%r) or an R task in a Databricks job.
# Reads:   demo_stage3_ultimate  (losses developed on the ELECTED pattern)
#          selected_development_pattern (the assumption + who approved it)
# Writes:  demo_r_indication  (the indicated rate change per accident year)
#
# NOTE: synthetic data, illustrative method. Swap in the real indication logic —
# the contract this reads (ultimate loss by accident year + the assumption id)
# does not change.
# =============================================================================

library(SparkR)
sparkR.session()

CATALOG <- "lr_dev_aws_us_catalog"
SCHEMA  <- "reserving_workbench"
fq <- function(t) paste0(CATALOG, ".", SCHEMA, ".", t)

# ── 1 · read the developed losses (produced on the ELECTED pattern) ──────────
ultimate <- collect(sql(sprintf("
  SELECT accident_year, cum_paid_latest, cdf_to_ultimate, ultimate_loss,
         applied_selection_id, applied_selection_source
  FROM %s
  WHERE line_of_business_code = 'COMMERCIAL_PROPERTY'
  ORDER BY accident_year", fq("demo_stage3_ultimate"))))

cat("Developed losses read:", nrow(ultimate), "accident years\n")

# ── 2 · show the assumption we are standing on ───────────────────────────────
# This is the governance point: the indication can name the exact selection it
# used, who approved it, and why — straight from the table.
assumption <- collect(sql(sprintf("
  SELECT selection_id, source_code, selected_by, approved_by, rationale
  FROM %s
  WHERE selection_id = '%s'", fq("selected_development_pattern"),
  ultimate$applied_selection_id[1])))

cat("\n--- Assumption behind this indication ---\n")
cat("selection :", assumption$selection_id[1], "\n")
cat("source    :", assumption$source_code[1], "\n")
cat("approved  :", assumption$approved_by[1], "\n")
cat("rationale :", assumption$rationale[1], "\n\n")

# ── 3 · the indication (illustrative) ────────────────────────────────────────
# Earned premium per accident year — in the real thing this comes from the
# premium tables already in Databricks (Rich noted premium has landed).
earned_premium <- data.frame(
  accident_year  = as.character(2019:2026),
  earned_premium = c(2050000, 2630000, 2700000, 3040000, 2140000,
                     1610000, 3160000, 3310000)
)

ind <- merge(ultimate, earned_premium, by = "accident_year")

# loss ratio on developed (ultimate) losses
ind$ultimate_loss  <- as.numeric(ind$ultimate_loss)
ind$loss_ratio     <- ind$ultimate_loss / ind$earned_premium

# trend each year's loss ratio to the prospective period, then compare with the
# target. Indicated change = trended experience LR / permissible LR - 1.
ANNUAL_TREND    <- 0.05
PROSPECTIVE_YR  <- 2027
TARGET_LOSS_RATIO <- 0.62   # permissible LR (after expense/profit provision)

ind$years_of_trend <- PROSPECTIVE_YR - as.numeric(ind$accident_year)
ind$trended_lr     <- ind$loss_ratio * (1 + ANNUAL_TREND) ^ ind$years_of_trend
ind$indicated_change <- ind$trended_lr / TARGET_LOSS_RATIO - 1

# credibility-weight the recent years into a single indication (illustrative:
# more weight on the more relevant years). AY2026 is deliberately EXCLUDED —
# at one development period it is too immature to carry weight in an indication.
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

# ── 4 · write the indication back, carrying the assumption id ────────────────
# The output names the assumption it used, so the indicated rate is traceable
# all the way back to the LDF election and the person who approved it.
out <- data.frame(
  line_of_business_code = "COMMERCIAL_PROPERTY",
  prospective_year      = PROSPECTIVE_YR,
  weighted_trended_lr   = overall,
  target_loss_ratio     = TARGET_LOSS_RATIO,
  indicated_rate_change = overall_indication,
  annual_trend          = ANNUAL_TREND,
  applied_selection_id  = ultimate$applied_selection_id[1],
  produced_by           = "indication.R",
  stringsAsFactors      = FALSE
)

saveAsTable(as.DataFrame(out), fq("demo_r_indication"),
            source = "delta", mode = "overwrite")

cat("\nWrote", fq("demo_r_indication"), "\n")
