# Databricks notebook source
# MAGIC %md
# MAGIC # LDF selection — the analyst's door
# MAGIC
# MAGIC The app is built for the **sign-off moment**: one line of business, one decision, recorded.
# MAGIC That is the right shape for the person who owns the number.
# MAGIC
# MAGIC It is the wrong shape for the analyst who wants to *dig* — all lines at once, several
# MAGIC averaging bases side by side, a tail factor to push on, a year to exclude and see what
# MAGIC happens. That work belongs in a notebook, and this is it.
# MAGIC
# MAGIC **The point:** this notebook writes to the *same* `selected_development_pattern` table the
# MAGIC app writes to. Same governed row, same audit trail, same guard on stage 3, same downstream.
# MAGIC The record does not care which door the decision came through.
# MAGIC
# MAGIC That also answers "can the selection happen in a tool we already use?" concretely — if a
# MAGIC notebook can write a first-class selection, so can R, so can an external actuarial tool.
# MAGIC
# MAGIC Reads `demo_stage2_triangle` and `demo_stage2_empirical_ldf` (stage 2 output).

# COMMAND ----------
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema", "reserving_workbench")
dbutils.widgets.text("valuation_date", "2026-12-31")
dbutils.widgets.text("analyst", "a.reserving.analyst")
CAT = dbutils.widgets.get("catalog"); SCH = dbutils.widgets.get("schema")
VAL = dbutils.widgets.get("valuation_date"); WHO = dbutils.widgets.get("analyst")
FQ = f"{CAT}.{SCH}"
spark.sql(f"USE CATALOG {CAT}"); spark.sql(f"USE SCHEMA {SCH}")

import json
import pandas as pd

tri = spark.table(f"{FQ}.demo_stage2_triangle").toPandas()
ind = spark.table(f"{FQ}.demo_stage2_empirical_ldf").toPandas()
for c in ["accident_year", "development_lag"]:
    tri[c] = tri[c].astype(int)
tri["cum_paid"] = tri["cum_paid"].astype(float)
for c in ["from_lag", "to_lag", "accident_year"]:
    ind[c] = ind[c].astype(int)
ind["individual_factor_paid"] = ind["individual_factor_paid"].astype(float)
print(f"{len(tri)} triangle rows, {len(ind)} individual factors, "
      f"{tri.line_of_business_code.nunique()} lines of business")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1 · Every line of business at once
# MAGIC
# MAGIC The app shows one line at a time, deliberately. Here is the whole book's first
# MAGIC development step, so an analyst can see which lines are stable and which are not without
# MAGIC clicking through five screens.

# COMMAND ----------
step0 = (ind[ind.from_lag == 0]
         .pivot_table(index="line_of_business_code", columns="accident_year",
                      values="individual_factor_paid")
         .round(3))
display(step0)

# The spread across accident years is the diagnostic that matters: a tight row is a stable
# pattern, a wide one has something in it. Quantified rather than eyeballed:
spread = (ind[ind.from_lag == 0]
          .groupby("line_of_business_code")["individual_factor_paid"]
          .agg(n="count", lo="min", median="median", hi="max"))
spread["hi_over_median"] = (spread["hi"] / spread["median"]).round(2)
display(spread.sort_values("hi_over_median", ascending=False).round(3))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2 · Several averaging bases, side by side
# MAGIC
# MAGIC The app has a dropdown — one basis at a time. An analyst defending a selection wants them
# MAGIC together, because the argument for a pick is usually *"it holds under more than one basis"*.

# COMMAND ----------
def bases_for(lob, exclude_years=()):
    """Volume-weighted / simple / median / geometric / last-3, per development step.

    exclude_years lets you answer "what if we drop the anomalous year?" — the single most
    common ad-hoc question, and the reason an analyst wants a notebook and not a dropdown.
    """
    t = tri[(tri.line_of_business_code == lob) & (~tri.accident_year.isin(exclude_years))]
    cum = {}
    for _, r in t.iterrows():
        cum.setdefault(r.accident_year, {})[r.development_lag] = r.cum_paid
    max_lag = max(max(v) for v in cum.values())
    rows = []
    for k in range(max_lag):
        pairs = [(v[k], v[k + 1], ay) for ay, v in cum.items() if k in v and k + 1 in v and v[k]]
        if not pairs:
            continue
        ratios = sorted(b / a for a, b, _ in pairs)
        recent = [p for p in sorted(pairs, key=lambda p: p[2])[-3:]]
        geo = 1.0
        for x in ratios:
            geo *= x
        rows.append({
            "step": f"{k*12}-{(k+1)*12}m",
            "n_years": len(pairs),
            "volume_weighted": sum(b for _, b, _ in pairs) / sum(a for a, _, _ in pairs),
            "simple_average": sum(ratios) / len(ratios),
            "median": ratios[len(ratios) // 2],
            "geometric": geo ** (1.0 / len(ratios)),
            "last_3": sum(b for _, b, _ in recent) / sum(a for a, _, _ in recent),
        })
    return pd.DataFrame(rows).round(4)


LOB = "COMMERCIAL_PROPERTY"
print(f"{LOB} — all bases, all years included:")
display(bases_for(LOB))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3 · Ad-hoc exclusion — the question a dropdown can't answer
# MAGIC
# MAGIC AY2023 carries a single late-reported large loss. *"What does the pattern look like without
# MAGIC it?"* is the question every actuary asks next, and in the current process it means editing a
# MAGIC script. Here it is one argument.

# COMMAND ----------
with_all = bases_for(LOB)
without_23 = bases_for(LOB, exclude_years=(2023,))
cmp = with_all[["step", "volume_weighted", "median"]].merge(
    without_23[["step", "volume_weighted", "median"]], on="step",
    suffixes=("_all_years", "_ex_2023"))
cmp["vw_drop"] = (cmp.volume_weighted_ex_2023 - cmp.volume_weighted_all_years).round(4)
display(cmp)

print("The first step is the whole story: the volume-weighted factor falls once AY2023 comes out,")
print("and the median barely moves — which is exactly the argument for holding ~1.667.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4 · Tail factor — what it's actually worth
# MAGIC
# MAGIC The tail sits beyond the observed triangle, so it is pure judgement. Worth knowing how much
# MAGIC the answer moves before defending a number.

# COMMAND ----------
def ultimate_on(factors, lob, tail):
    """Chain-ladder ultimate across all accident years for a factor set + tail."""
    t = tri[tri.line_of_business_code == lob]
    cum = {}
    for _, r in t.iterrows():
        cum.setdefault(r.accident_year, {})[r.development_lag] = r.cum_paid
    max_lag = max(max(v) for v in cum.values())
    total = 0.0
    for ay, v in cum.items():
        lag = max(v); paid = v[lag]; cdf = tail
        for k in range(lag, max_lag):
            cdf *= factors.get(k, 1.0)
        total += paid * cdf
    return total


vw = {i: r.volume_weighted for i, r in bases_for(LOB).iterrows()}
held = dict(vw); held[0] = 1.667          # the selection being argued for
tails = pd.DataFrame([
    {"tail": tl,
     "ultimate_on_empirical": round(ultimate_on(vw, LOB, tl), 0),
     "ultimate_on_held": round(ultimate_on(held, LOB, tl), 0)}
    for tl in (1.00, 1.01, 1.02, 1.05)])
tails["difference"] = (tails.ultimate_on_empirical - tails.ultimate_on_held).round(0)
display(tails)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 5 · Write the selection — to the SAME governed table as the app
# MAGIC
# MAGIC This is the part that matters. The row below is indistinguishable in kind from one the app
# MAGIC writes: same table, same columns, same status flow, and stage 3's guard treats it
# MAGIC identically. The only difference is `selected_by` and that the id says where it came from.
# MAGIC
# MAGIC It lands as **PENDING_APPROVAL** — an analyst proposes, an approver disposes. Nothing here
# MAGIC lets a notebook quietly approve its own selection.

# COMMAND ----------
SELECTED = [1.667, 1.20, 1.08, 1.05, 1.02, 1.01]     # what this analysis argues for
TAIL = 1.01
RATIONALE = ("Held the prior 12-24m factor at 1.667. The volume-weighted empirical factor is "
             "inflated by a single late-reported large loss in AY2023; excluding that year the "
             "volume-weighted and median bases agree at ~1.667, and the large loss is reserved "
             "individually. Explored in the analyst notebook across all five bases and a "
             "1.00-1.05 tail range.")

sel_id = f"SEL-NB-{LOB[:4]}-{VAL.replace('-','')}"
spark.sql(f"""
DELETE FROM {FQ}.selected_development_pattern WHERE selection_id = '{sel_id}'""")
spark.sql(f"""
INSERT INTO {FQ}.selected_development_pattern (
  selection_id, valuation_date, accident_year, line_of_business_code, currency_code,
  source_code, averaging_method_code, last_n_years, development_factors, tail_factor,
  prior_selection_id, status_code, rationale, selected_by, selected_at, approved_by, approved_at)
VALUES (
  '{sel_id}', DATE'{VAL}', NULL, '{LOB}', 'GBP',
  'MANUAL', NULL, NULL, '{json.dumps(SELECTED)}', {TAIL},
  NULL, 'PENDING_APPROVAL', '{RATIONALE.replace("'", "''")}',
  '{WHO}', current_timestamp(), NULL, NULL)""")
print(f"Wrote {sel_id} as PENDING_APPROVAL — visible in the app's selection audit trail.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 6 · Proof it is the same record
# MAGIC
# MAGIC App-authored and notebook-authored selections, in one table. Nothing about the governance
# MAGIC depends on which door was used — which is the answer to *"can the selection happen in a tool
# MAGIC we already use?"*: yes, if it can write this row.

# COMMAND ----------
display(spark.sql(f"""
SELECT selection_id, source_code, status_code, selected_by, approved_by,
       development_factors, tail_factor
FROM {FQ}.selected_development_pattern
WHERE line_of_business_code = '{LOB}'
ORDER BY selected_at DESC NULLS LAST, selection_id"""))

# COMMAND ----------
# MAGIC %md
# MAGIC ### Where this goes next
# MAGIC
# MAGIC Approve it — in the app (**Triangle & selection -> Approve & run stage 3**) or by an approver
# MAGIC running the update here — and stage 3's guard opens, the loss cost rebuilds on these factors,
# MAGIC and the R indication reads them by name. The analyst dug, the approver decided, and the
# MAGIC pipeline picked up from the decision.
