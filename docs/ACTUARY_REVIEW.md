# Reserving Workbench — reviewed from the actuary's chair

*Written wearing the hat of the person who actually does this monthly/quarterly: the reserving
actuary booking the number, and the pricing actuary who needs LDF triangles for the indication.
The question throughout: how much of my real job can I do here, and would I switch?*

---

## 1 · The frame — what my month actually is

Nobody's job is "select a development factor". That's ten minutes of a six-week close. The month is:

1. **Get the data out** — claims extract, premium, exposure, from systems that fight me.
2. **Reconcile it** — does paid tie to the GL? does the extract tie to last quarter?
3. **Understand what moved** — new claims, reopens, large losses, a re-map nobody told me about.
4. **Build triangles** — paid *and* incurred, indemnity *and* counts, gross *and* net, by segment, on the right cohort basis (accident / underwriting / report year).
5. **Select factors** — averaging period, drop outliers, **fit and smooth the tail**, sense-check against benchmarks.
6. **Pick and blend methods per cohort** — CL for mature years, BF/ELR/Cape Cod for green ones, weight the blend by maturity.
7. **Get to ultimates** — IBNR, IBNER, then **gross-to-net** through the reinsurance programme.
8. **Diagnose** — actual-vs-expected, residual plots, hindsight/back-testing, roll-forward.
9. **Range it** — Mack, **bootstrap**, a full distribution, percentiles the capital team asks for.
10. **Overlay judgement** — and record why.
11. **Discount and load** — PV, SII risk margin, IFRS 17 risk adjustment.
12. **Explain the movement** — "why is the GL £3m heavier than last quarter?"
13. **Sign off, feed downstream** — TPs, IFRS 17 LIC, capital model, planning.
14. **Answer the ad-hoc all month** — "what if inflation runs 2pts hot?", "impact of that £5m loss?"

I'll score the workbench against *that*, not against a demo script.

---

## 2 · What's genuinely easy and self-explanatory (no training needed)

- **The triangle and the individual factors.** I open it and I understand it instantly — accident year down, development across, the 3.63× sitting red against a column of 1.67×. That's the picture I live in. No learning curve.
- **The averaging-basis dropdown + live recompute.** Volume-weighted / simple / last-N / median / geometric, and the ultimate moves as I switch. That's exactly the muscle memory of factor selection, and seeing the reserve move live is better than my spreadsheet, where I recalc and squint.
- **Override one factor, watch the ultimate change, save with a reason.** The core gesture, done cleanly.
- **"What changed since last quarter."** The movement view is the first thing I actually want and rarely have in one place.
- **The book cockpit** ranking lines by what needs attention. At 5 lines it's obvious; the idea scales.

This is the part where an actuary nods. It matches the mental model without a manual.

---

## 3 · The genuine WOW moments (few, and real)

Not "AI" — actuaries are cynical about that. The things that would actually make me sit up:

1. **The monolith-vs-governed diff: £369k on one line, same claims, same day.** *This* is the WOW, because I have lived the opposite — a number I couldn't defend because I couldn't see how it was built. Showing that the unreviewed pattern over-reserves by a quantifiable amount is the most persuasive thing in the whole app.
2. **Reconciliation to the GL, to the penny, as a control I didn't run by hand.** Every reserving actuary has lost days to this. Seeing it tie automatically is quietly enormous.
3. **Reproduce-as-at + full audit trail.** "The regulator asks in March about the Q2 number, one click." I have spent weeks of my life on exactly this archaeology. This is the feature I'd tell a colleague about.
4. **My own R model registered as a first-class method, versioned, off my laptop.** The key-person-risk fix. Every team has the model that lives in one person's script; this kills that.
5. **The guard.** An empirical pick *cannot* reach the loss cost until a human approved it, and the pipeline fails loudly if it hasn't. That's a control I'd want and don't have.

Note what's on this list: **data, governance, reproducibility, orchestration.** Not the actuarial engine. Hold that thought — it's the whole conclusion.

---

## 4 · What's difficult, thin, or quietly misleading

- **The decision module shows *empirical* and *selected* — but not the *prior pattern* as factors.** I compare factor-to-factor; I want prior 1.667 sitting under empirical 1.897 so I can decide between them. Right now the prior only appears as a money delta, so I'd have to remember or look up last quarter's pattern. This is the single most-missed thing on the core screen, and it's the actuary's actual comparison.
- **The tail is one input box.** In real long-tail work the tail *is* the job — I fit an exponential / inverse-power / Weibull curve to the last few factors and smooth. A single `1.01` typed in is a demo simplification an actuary spots in two seconds.
- **No smoothing across the selected pattern.** I can override one factor, but I can't smooth the whole curve, and jagged selected factors are a red flag.
- **Paid-centric.** The data has incurred, but the selection gesture is built around paid. Half my work is the incurred triangle and the paid/incurred consistency check; that's not front-and-centre.
- **"Reserves recompute live" / "Selected IBNR" on what a pricing actuary is told is a pricing tool.** The language flips between reserving and pricing framing depending on the screen — a pricing actuary reads "reserves" and thinks *this wasn't built for me*.
- **The AI peer review button** currently reviews without the prior pattern in hand, so it can't do the one comparison that matters. As shown it invites a question it can't answer well.
- **Methods sit side by side but I can't blend them.** Real reserving weights CL and BF by maturity (Benktander / Cape Cod / manual weights per AY). Showing five ultimates in a row isn't selecting — selecting is choosing and blending per cohort.

None of these are fatal. But each is a place where a working actuary can tell the difference between "built by someone who books reserves" and "built to demo the platform".

---

## 5 · What's missing, mapped to the real job

These are the gaps that decide whether this is *my reserving system* or *the platform around it*. Ordered by how often they bite.

| The job needs… | In the workbench? | Severity |
|---|---|---|
| **Gross-to-net (reinsurance)** — every reserve is booked gross *and* net | **Absent.** No RI programme, no ceded triangles, no net ultimate. | ★★★ dealbreaker as an engine |
| **Tail curve fitting** (exp / inverse-power / Weibull) | Single tail input, no fit | ★★★ |
| **Method blending per cohort** (CL↔BF by maturity, Cape Cod, Benktander) | Methods shown side by side, not blended/weighted | ★★★ |
| **Bootstrap / full predictive distribution** (ODP bootstrap, not just Mack CoV) | Mack CoV + 75th/95th only | ★★ |
| **Count & average-cost triangles** (frequency-severity) | Paid/incurred only; no counts, no closure, no avg cost | ★★ (★★★ for pricing) |
| **Editable BF/ELR a-priori per cohort** | Methods run with fixed priors; not user-set in the UI | ★★ |
| **Discounting to present value** (SII best estimate, IFRS 17) | Absent | ★★ |
| **Cohort basis choice** — underwriting / report year, not just accident year | Accident year only | ★★ |
| **Attritional-vs-large split as triangles** (+ cat loading) | A large-loss flag, but not a split triangle you reserve separately | ★★ |
| **Segment depth** — real books are 30–100 reserving classes | 5 lines of business | ★★ (mechanics scale; not shown at depth) |
| **Cell-level actual-vs-expected / residual heatmap** | Cohort-level, first step only | ★ |
| **Earning patterns / UPR / premium development** | Absent | ★ (matters more for pricing) |

The honest summary: the **data, control, governance and orchestration layer is more complete than most teams have**. The **actuarial engine is a competent chain-ladder demo** — real bases, real averaging, real Mack, real override, registered methods — but it stops well short of what I use to actually book a number, and the three ★★★ gaps (net, tail-fit, blending) are ones I hit *every single quarter*.

---

## 6 · Angle 1 — I'm a ResQ (or Reserve Pro / ic ) user

ResQ already does everything in §5: every triangle basis, curve-fit tails, CL/BF/Cape Cod/Bornhuetter-Ferguson, bootstrap, gross-to-net, IFRS 17, discounting, decades of actuarial edge cases.

**If you pitch this workbench as a ResQ *replacement*, I take it apart in five minutes** — "where's my tail fit, where's net of cat XL, where's the bootstrap distribution, where do I blend BF and CL by year?" It isn't close, and pretending otherwise loses my trust for the rest of the meeting.

**If you pitch it as the layer *around* ResQ, I lean in.** My ResQ pain isn't ResQ — it's everything either side of it: getting clean data in, reconciling it, versioning it, explaining the movement, and getting the selected pattern back out into a governed, auditable, reproducible place that the capital team and the auditor can both trust. The workbench does that, and the `source = RESQ` seam means my pattern lands in the same governed table as a native one. **That's a real proposition:** *keep ResQ for the craft; we do the data in, the governance around, and the narrative out.*

What would actually move me: show me the ResQ pick flowing through stage 3's guard and into the same audit trail as everything else. The seam existing in the schema is necessary; the seam *demonstrated end-to-end* is what closes it.

**Verdict (ResQ user):** Not an engine replacement, and shouldn't claim to be. A genuinely attractive **data + governance + orchestration wrapper** — provided the pitch is honest about the boundary.

---

## 7 · Angle 2 — I'm an Excel + R/Python actuary

This is where the workbench is strongest, because my pain *is* the 90% it solves.

My reality: triangles in Excel with a wall of INDEX/MATCH, factor selection by eye, a tail I fudge, `_v4_FINAL_use_this.xlsx`, no audit trail, no reconciliation I didn't do by hand, and the one clever bootstrap that lives in my R script that nobody else can run. When someone asks "why did it move?", I rebuild it.

**What the workbench gives me that I don't have:** the reconciliation, the movement view, the audit trail, reproduce-as-at, and — crucially — **a governed home for my R**. I keep `ChainLadder`/`MackChainLadder`/`BootChainLadder`, register it as a first-class method, and it comes off my laptop with versioning and lineage I never built. The analyst notebook path (all lines, all bases, ad-hoc exclusions, writes the same governed row the app does) is *exactly* how I actually work — dig in code, then commit a decision.

**But be honest with me too:** R's `ChainLadder` package already does Mack, ODP bootstrap, curve-fit tails and Clark methods. So the app's *engine* is thinner than the R I already run. The right framing isn't "use our engine instead of your R" — it's "**keep your R, we make it reproducible, reconciled and auditable, and we give you the data layer you've been faking in Excel.**" Framed that way, I'm very interested. Framed as "replace your R with these five buttons", I know my buttons are better.

**Verdict (Excel/R user):** The most compelling of the two. It removes my worst pain (data, reconciliation, version chaos, key-person risk) and dignifies my R instead of replacing it. The gaps in §5 don't hurt here, because I bring my own engine — I just want it governed.

---

## 8 · The one conclusion that holds for both personas

Every honest answer above lands in the same place:

> **This is a data, governance, orchestration and narrative platform *around* the actuarial engine — not the engine.**

- Pitch it as **the engine**, and any real actuary (ResQ user or R user) finds the holes in §5 within one screen — net, tail-fit, blending, bootstrap — and stops trusting the rest.
- Pitch it as **the platform the engine plugs into**, and the §5 gaps become roadmap rather than dealbreakers, the seam (ResQ / R / notebook / SQL, same governed row) becomes the whole point, and the §3 WOWs (the £369k diff, the GL tie, reproduce-as-at, own-model-as-method, the guard) are things neither ResQ nor a pile of spreadsheets gives me.

The workbench is already built the right way for this — the seam, the registered-method pattern, the "your methodology, our governance" line are all there. The risk is purely in the *positioning*: the demo occasionally talks like it's the reserving engine ("reserves recompute live", five methods shown as if that's selection), and that's the version an actuary punctures.

---

## 9 · If I had a short list to close the gap to "credible engine for a first cohort"

Not the whole §5 table — just the few that would stop an actuary dismissing it, in value order:

1. **Prior pattern as a factor row + a "hold prior" button** on the decision module. Small, and it completes the actuary's actual comparison (and it's the ask already flagged).
2. **A fitted, smoothed tail** — even one curve family (exponential) with the fitted factors shown beyond the triangle. Turns the biggest "toy" tell into a real capability.
3. **Method blend per cohort** — a weight slider or a maturity rule (CL beyond N, BF before). This is what "selection" actually means beyond one factor.
4. **Gross and net** — even a single flat RI layer, so "net ultimate" exists on screen. The absence is the loudest silence for a reserving actuary.
5. **Fix the framing** — "ultimates", not "reserves", on the pricing path; and either wire the AI review to see the prior or hide it.

Items 1 and 5 are hours. 2–4 are the difference between "nice platform, thin engine" and "I could run a cohort in this".

---

*Reviewer's stance: I want this to be real, and the platform half already is. The engine half is honest chain-ladder — good enough to be the front door, not yet good enough to be the whole house. Sell the front door and the house you plug in behind it, and I'm buying.*
