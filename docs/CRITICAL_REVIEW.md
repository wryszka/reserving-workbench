# Critical Review — Reserving Workbench (2026-08-03)

Reviewed from three viewpoints, as asked: (1) Daniel Tully / a reserving actuary,
(2) a Hiscox US pricing analyst, (3) Laurence (vs the other workbenches + house
style). Honest assessment. **Headline: the app is a read-only dashboard, not a
workbench. It shows the process; it doesn't let anyone *do* the process.**

## The core defect (all three personas hit it)
14 GET endpoints + 1 agent button + 1 line-of-business dropdown + a Genie embed.
**Zero writeback, zero recorded decision, zero what-if lever, zero job trigger.**
Worst of all: **the LDF override — the entire Hiscox ask — is shown as a pre-baked
audit-trail table, not something the user does.** The one interaction that should
be the star of the demo is a static display of a decision someone already made.

This is the opposite of the family DNA. Every sibling workbench is built on
**human-in-the-loop actions with writeback**:
- **Pricing:** run a quote on the live endpoint; MTA what-if (change sum insured → reprice); promote/rollback a champion model.
- **Solvency II:** draft an overlay → submit → **approve** (magnitude-routed) → it writes to `6_gov_overlays` and appears in the audit panel instantly; ORSA reverse-stress what-if.
- **Claims:** AI recommends → handler **accepts or overrides with a reason** → writes to the decision log. Human judgement trumps the model *and is recorded*.

The "magic moment" in each is a **click that changes state**. Mine has no such moment.

---

## Persona 1 — Daniel Tully / a reserving actuary
**Verdict: interesting to look at once, not useful to work in.**

- Daniel asked for **practitioner workflows, not toy notebooks**. This is neither — it's a set of exhibits. He can't select factors, can't run a method, can't record a judgement, can't sign anything off. He'd watch it, nod, and ask "ok, but what do *I* do in it?"
- The triangle is read-only. A reserving actuary's whole job is **selecting** — picking factors, overriding, choosing a method, adding an overlay, signing off. None of that is possible here; it's all pre-decided and displayed.
- The Senior Reserving Actuary agent is genuinely good (real, grounded). But one working button in a sea of static screens reads as "the AI does it, you watch" — the opposite of the "second set of eyes for a practitioner" pitch.
- **What would make it useful for him:** let him *make the selection* (pick averaging method / last-N, see factors recompute, elect empirical vs prior, type a rationale, save it → new audited row). Let him *raise and approve an overlay*. Let him *run a method* and see the ultimate move. That's his day job.

## Persona 2 — Hiscox US pricing analyst (John's team)
**Verdict: doesn't demonstrate the thing they asked for.**

- Their explicit ask was a **decision module**: view empirical LDFs, compare to a prior set, and **elect** empirical vs prior — the stop-and-override moment their Discovery SQL script can't do. In the app that election is a finished table row. **We're showing them a screenshot of the feature they asked us to prototype, not the feature.**
- To land Aug 6 the presenter needs to *click*: here are the empirical factors, here's the AY2023 anomaly, **I override it** (type why), **I save** → watch the reserve/indication move and the audit row appear. Right now you can only narrate that over a static grid.
- The triangle + anomaly visual is strong and correct. But without the interaction it proves we *understand* the ask, not that we've *built* it.
- **What would make it strong for them:** the selection screen must be a live decision — change the averaging basis and watch factors move; click override on the anomalous factor; enter a rationale; save; see the elected pattern flow to the estimate. That single flow *is* the Aug 6 win.

## Persona 3 — Laurence (vs the workbench family + design language)
**Verdict: design language now ✅, workbench behaviour ❌.**

- **Design:** fixed — light theme, 264px dark sidebar, white cards, #2563eb, page explainers, About-this-demo. Visually it's now in the family.
- **Behaviour:** it is **not** in the family. Every other workbench is action-first (approve / override / promote / what-if / run), audit-first (every action logs user+timestamp+reason), with a clear human-in-the-loop moment. This app is dashboard-first. It looks like a sibling and behaves like a report.
- **The gap is specific and closeable** — it needs the family's proven patterns, which already exist to copy:
  1. **A real selection/override flow** (the Claims accept/override pattern, applied to LDF): change basis → recompute → elect/override + rationale → `POST` writeback → new audited row appears. This is THE one to build; it serves both Hiscox rooms.
  2. **An overlay approval workflow** (lift Solvency II's `overlays.py` almost verbatim): raise an expert judgement → submit → approve (magnitude-routed) → writes + shows in audit. We already have the `expert_judgement` table; it's currently read-only.
  3. **A method/what-if lever:** pick a method (or nudge a tail factor) → ultimate + IBNR recompute live → show the delta. (Solvency II's what-if pattern.)
  4. Optional: a "run the reserving job" trigger with polling (pricing/solvency pattern) for the "it's a real pipeline" beat.

---

## Recommendation (priority order)
1. **Build the live LDF selection/override flow** — the single highest-value change; it fixes personas 1 and 2 at once and is the Aug 6 demo. Backend: `POST /api/selection` (recompute for a chosen basis) + `POST /api/selection/elect` (writeback new row, retire prior). Frontend: basis controls + per-factor override + rationale + save, on the existing Triangle page.
2. **Make expert judgement interactive** — raise → submit → approve, writing to the existing table (copy `overlays.py`).
3. **Add a method/tail what-if** on the estimates page — recompute ultimate live, show delta.
4. Keep the read-only views (methodology library, diagnostics, committee, assets, engines) — they're fine as *supporting* context once the workbench has real actions at its centre.

Until at least #1 exists, the honest status is **in-progress / not demo-ready as a workbench** — which is exactly why the tile is (correctly) marked in-progress.
