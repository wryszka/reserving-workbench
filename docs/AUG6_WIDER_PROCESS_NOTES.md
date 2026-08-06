# Aug 6 — the wider pricing process: what they're really doing, and where we're thin

**Internal prep note.** Not for sharing. Written to answer: why did they pick LDFs as the
starting point, what else matters to them, is what we show strong enough, and where does this
data need to go next.

---

## 1 · Why LDFs, and why it's not really about LDFs

LDF selection is **step one of the quarterly loss ratio process**, not a standalone task. Rich's
framing on 10 July was explicit — development factors on **four bases** feeding the loss ratio
work, with the up-front data build (large-loss adjustment, exclusions, coverage remapping)
"required for every part of our quarterly loss ratio process."

So the actual chain in their heads is:

**losses → develop to ultimate → ultimate loss ratio by segment → trend and adjust → indicated
rate → rate filing / Earnix deployment**

They picked LDFs to show us because it's the **most painful and most self-contained** link — the
one where the black box hurts most and where a fix is provable without touching everything else.
It is a wedge, not the destination. If we treat it as the whole job we solve 15% of their quarter.

**The consequence for today:** after showing the factor, the question to ask is *"and what happens
to this number next?"* Their answer tells us whether we're building a component or the process.

---

## 2 · What they'll care about that we haven't led with

| Their concern | Where we stand |
|---|---|
| **Four bases** — paid, incurred, closed-with-pay counts, reported counts | **Paid and incurred are real. The two count bases are NOT built.** Be straight. |
| **Loss ratio, not just ultimate** | Ultimate is real; the loss ratio needs premium — see §3. This is our biggest gap. |
| **Segment granularity** — they price by state / class / programme, not by 5 broad lines | Ours is 5 lines of business. The mechanics are grain-agnostic but we've never shown it at their grain. |
| **Credibility weighting** — small segments need blending | The R indication does this; the app does not surface it. |
| **Consistency between quarters** | Strong — this is what the prior-vs-empirical comparison, the mapping-change flag and the version history are for. |
| **Minimise rework when the loss source moves off Discovery** | Strong — stage 1 is the only thing bound to the source; stages 2–3 and the indication are untouched. |
| **Rate filing / regulator defensibility** | The audit trail is exactly this, and we've been selling it as governance rather than as filing support. Reframe for a US room: **this is your rate filing exhibit**. |

**The honest summary:** what we show is strong on *transparency, control and auditability* of one
step. It is thin on the *loss ratio itself* — which is the thing their process is named after.

---

## 3 · The biggest gap: there is no premium

The loss ratio needs earned premium and **we don't have it**. Verified: no premium or exposure
column anywhere in the schema. The R indication hardcodes premium as a data frame.

That matters because:

- **Their premium is already in Databricks.** Rich said so on 10 July — premium has migrated,
  it's the loss side that's stuck in Discovery. So the *one half they've already done* is the half
  we're not using.
- It's the natural next build and it's small: a premium table by accident year and segment,
  joined to ultimate, gives loss ratio as a governed measure rather than an R-local calculation.

**How to play it today:** don't hide it. *"Your premium is already on the platform — that's the
half of the loss ratio we haven't wired yet. Wire it and the loss ratio becomes a governed number
instead of something each analyst recomputes."* That turns a gap into their next step, and it
uses work they've already paid for.

---

## 4 · Where does this data need to go? (they will ask)

This is the question behind "will they want to surface it elsewhere" — and the answer is yes, in
four directions. **We have a real answer for three of them.**

### a · Excel — where actuaries actually live
Non-negotiable and easy to under-sell. Analysts will not adopt anything that ends the numbers in
a web app they can't pivot. The metric view is queryable from Excel through the Databricks
connector, live, against governed definitions — **no more "which extract is this?"**. Verified
working:

```sql
SELECT line_of_business, MEASURE(paid_to_date), MEASURE(paid_ratio)
FROM lr_dev_aws_us_catalog.reserving_workbench.reserving_metrics
WHERE currency_code = 'GBP' GROUP BY line_of_business;
```
→ Commercial Property 12,218,724, paid ratio 0.854 (and four other lines).

**The line:** one definition of "paid to date", consumed identically by Excel, a dashboard, Genie
and the R indication. Today every one of those is someone's own SQL.

### b · Earnix — the deployment target they're mid-implementation on
They told us in July: Earnix for model deployment, and getting data **back** from Earnix is the
hard part. Delta Sharing handles the outbound; the return path needs the Earnix team. Worth
naming because it shows we remember their landscape — but don't over-promise the return leg.

### c · Dashboards / self-serve for the pricing team
Same metric view, so a dashboard cannot disagree with Excel or with the indication. This is the
"build once, consume everywhere" argument made concrete rather than asserted.

### d · The reserving team
Their reserving colleagues develop the same triangles for booked reserves. One governed triangle,
two consumers — the argument we've already made, but it's also an internal-politics asset for John:
he isn't asking for a pricing-only tool.

**What we do NOT have:** any actual downstream consumer wired. No dashboard, no Excel workbook, no
Earnix connection. The metric view is the *capability*; nothing consumes it yet. If they ask "show
me it in Excel", we can't today.

---

## 5 · Is what we show strong enough?

**For today's stated purpose — yes.** They asked for three things and a review of a prototype;
they get all three working, plus the staged pipeline, plus the R indication running, plus five ways
to see into the methodology. That over-delivers on the ask.

**As an answer to their quarterly loss ratio process — no, and we shouldn't pretend otherwise.**
We have one step of maybe six, done well. The credible position is:

> *"This is the step you said hurt most, done properly — transparent, stoppable, audited, and it
> feeds your R unchanged. It is deliberately one step. The same pattern extends to the rest of the
> quarterly process, and the next most valuable piece is the loss ratio itself, because your
> premium is already here."*

That's stronger than claiming completeness, because they'd find the gaps in ten minutes of using it.

---

## 6 · Three questions to ask them today

Worth more than anything we show, because they determine whether this becomes their process:

1. **"Once the factors are selected, what happens next — and who does it?"** Reveals the real
   downstream, and whether the LDF step is even the bottleneck.
2. **"What grain do you actually price at?"** If it's state × class × programme, our 5-line demo
   is a toy at their scale and we need to say how it holds up.
3. **"Where does the loss ratio live today, and who disagrees with whom about it?"** If different
   analysts get different loss ratios from different extracts, the governed-measure argument sells
   itself and premium becomes the obvious next build.

---

## 7 · If asked something we can't do

- **Count bases** — not built. Same shape, swap the measure. Small addition to stage 2. Don't imply.
- **Loss ratio as a governed measure** — not built; needs premium, which is already on their platform.
- **Their pricing grain** — never tested at state/class level. Say so and offer to prove it on
  their real segments.
- **Excel / dashboard live** — the metric view is queryable, but nothing is built. Offer to stand
  one up as the immediate follow-up; it's a small piece of work with high visibility.
- **Earnix return path** — needs their Earnix team. Don't own that on the call.
