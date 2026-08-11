> **⚠️ Superseded by `MASTER_PLAN.md`** (2026-08-11). Kept as the reasoning behind the plan; the plan of record is the master.

# SA review — page clarity, agents, MCP-by-chat, and the end-to-end story

*Reviewed wearing the Databricks SA hat, against the project's own dev language: every page carries
a "what am I seeing" explainer + a per-datapoint "why decided", real Databricks services (not faked),
Claude via FMAPI, one schema / numbered tables, scale-to-zero. This is a plan, not a build.*

---

## 1 · Page-by-page: is each page's purpose clear? (the dev-language check)

Every page **already has** an `explain()` block — good, that half of the rule holds. The gap is the
*second* half of the rule: **per-datapoint "why decided"**. The explainers say what the page is;
several don't yet let you unfold *why this specific number is what it is*. Findings per page:

| Page | Explainer present? | Purpose clear? | Gap to fix |
|---|---|---|---|
| **Today** | ✓ | ✓ strong | Add a one-line hover on each attention flag: *why* this cohort was flagged (residual value, restated £, mapping id). The rule wants per-datapoint reasons, not just the page intro. |
| **Ingestion & data controls** | ✓ (best on the app) | ✓ | Each of the six tabs needs its own one-liner sub-header — right now the page explainer covers all six, so a viewer landing on tab 4 has no local "what is this tab". |
| **Triangle & selection** | ✓ | ✓ | The factor grid needs a **"why this factor"** unfold per column (n years, outlier dropped, prior held). This is the page where "why decided" matters most and is thinnest. |
| **Methods & estimates** | ✓ | partial | "Methods sit side by side" — but it doesn't say *which one is booked and why*. Add a "booked basis" marker + reason. |
| **Diagnostics** | ✓ | ✓ | AvE breach needs a per-row "why flagged" (it says residual, not the story). |
| **Expert judgement** | ✓ | ✓ | Clear. Approval routing is self-explaining. |
| **Committee** | ✓ | ✓ | Clear; agent brief is well-scoped. |
| **Workbench AI** | ✓ | partial | Tiles say scope but not **what each agent reads** in one glance — see §2. |
| **Engines & your models** | ✓ | ✓ | This becomes the positioning page (separate plan). |
| **Governance & sign-off** | ✓ | ✓ strong | The spine page; clear. |
| **Learn / Assets** | ✓ | ✓ | Fine. |

**One structural SA note:** the nav has grown to ~11 destinations. For a big-screen demo that's a
lot of doors. Consider a visible **"you are here in the close"** breadcrumb (Trust → Select →
Analyse → Decide → Sign off) on every page, so a viewer never loses the thread. Cheap, high-clarity.

**Verdict:** page *purpose* is clear everywhere; the **per-datapoint "why"** is the consistent gap,
and it's exactly the half of the dev-language rule that makes an actuary trust a number. Small,
per-page unfolds — not new pages.

---

## 2 · Where agents make sense — small picture and big picture

There are already **5 specialists + a supervisor** (Senior Reserving Actuary, Movement Explainer,
Data-Quality Investigator, Committee-Note Drafter, Reserving Peer Reviewer), all real FMAPI calls,
all traced to the audit log. The question is where *more* agents earn their place versus where
they'd be decoration. SA rule of thumb: **an agent earns its place when it removes a genuine
manual grind and every output is checkable against a governed table.**

### Agents that clearly earn a place (add these)

| Agent | The grind it removes | Reads | Big/small |
|---|---|---|---|
| **Data-Diff Narrator** | "What changed since last quarter and does it matter?" — turns the movement table into a written close-open briefing | `1_raw_data_movement`, reconciliation | small: one more specialist, high daily value |
| **Selection Rationale Drafter** | Writes the *first draft* of the override rationale from the factor pattern (actuary edits) — the box everyone leaves blank | triangle, prior/empirical factors | small; directly serves the audit trail |
| **Method-Recommender** | "For this cohort, which method/blend and why" — CL for mature, BF for green, with the maturity reasoning stated | estimates, AvE, maturity | big-picture: this is the judgement-support agent |
| **Back-test Commentator** | Narrates champion/challenger results: "chain-ladder has run 4% hot on GL for 3 quarters" | `method_backtest` (planned) | big-picture; only exists once C3 in the build plan lands |
| **Reproduce-as-at Explainer** | Auditor asks about Q2; the agent reconstructs *what was known then and why the number was set* from the as-at snapshot | audit trail, signoff, data version | big-picture: turns reproducibility into a conversation |

### Where an agent does NOT make sense (resist)

- **Doing the selection itself.** The whole thesis is *the human decides*. An agent that picks the
  factor undermines the governance story. It may *challenge* (the peer reviewer does), never decide.
- **The maths.** Chain-ladder / bootstrap are deterministic engine work — a model, not an agent. Do
  not wrap arithmetic in an LLM.
- **Anything without a governed table behind it.** If an agent's answer can't be checked against a
  real table, it's a hallucination surface, not a feature.

**Big-picture framing:** the agents cluster into three honest roles — **explain** (movement,
data-diff, reproduce-as-at), **draft** (committee note, selection rationale), **challenge** (peer
review, method-recommender). That triad is the story: *the AI explains, drafts and challenges; the
actuary decides.* Keep every new agent inside that triad.

---

## 3 · MCP — operating the workbench by chat

There is **no MCP server today** (verified). Pricing-workbench has `routes/mcp.py` (a JSON-RPC MCP
with `get_quote_requirements`, `price_motor_risk`, `explain_price`, …) — a proven pattern to mirror.

**Is it worth it here? Yes, and it's a strong beat**, because it answers a real question a
Databricks-native customer asks: *"can I drive this from my own assistant / from Genie / from
Claude, not just your UI?"* The whole app is already thin over governed tables and endpoints — an
MCP is a second front door onto the same governed operations. That's on-message with "any door,
same governed row."

### Proposed MCP tool surface (mirror pricing's `routes/mcp.py`)

Read tools (safe, no writeback):
- `get_triangle(lob, basis)` — the triangle + empirical factors
- `compare_selection(lob)` — prior vs empirical vs selected, factor by factor
- `get_estimates(lob)` — ultimates/IBNR by method
- `get_diagnostics(lob)` — AvE breaches, movement drivers
- `whatif(lob, inflation_pts, tail, large_loss)` — the scratch-pad scenario (writes nothing)
- `explain_movement(lob)` — routes to the Movement Explainer agent

Write tools (governed, human-in-the-loop — the interesting ones):
- `propose_selection(lob, factors, tail, rationale)` — writes a `PENDING_APPROVAL` row (same as the
  app / notebook / SQL). **Never auto-approves.**
- `approve_selection(selection_id, approver)` — the maker/checker gate, over chat
- `run_pipeline_stage3()` — triggers the governed Job (the guard still applies)

**The demo beat:** *"Show the triangle for Commercial Property, compare to the prior, propose holding
1.667 with a rationale"* — typed into Claude/an assistant, and it lands as a `PENDING_APPROVAL` row
in the same governed table the UI writes to, visible in the app's audit trail. That proves the thesis
harder than any screen: **the governance is in the platform, not the UI.**

**SA caution to bake in:** the write tools must enforce the *same* rules as the app — rationale
required on override, magnitude-routed approval, no self-approval — or the MCP becomes a governance
bypass. Reuse the endpoint logic, don't re-implement it. (Pricing's MCP calls the same route
handlers; do the same.)

**Sizing:** one `routes/mcp.py` + a manifest, reusing existing endpoints. ~1–2 days because the
operations already exist; the MCP is a thin JSON-RPC skin.

---

## 4 · The end-to-end story — is there enough data to tell it well?

The point of this section: an SA needs a **concise, true, memorable** narrative, and it must be
backed by data that actually reconciles end to end. Assessment:

### What the data already supports (the spine is real)
- **One golden thread reconciles the whole way down:** claim ledger → triangle (a view) → factors →
  ultimate → estimate → sign-off → (planned) downstream. The paid triangle ties to the ledger to the
  penny; the monolith-vs-governed **£369k** diff is a real computed number. That's a *provable*
  story, not a slide.
- **The anomaly is one traceable object** (CLM-2023-ANOMALY, £1.05m, backdated) that appears in the
  data-diff, drives the 3.63× factor, triggers the override, and shows in the audit trail. **One fact
  threads five pages** — that's the gift of the synthetic world and it's what makes the story stick.
- **Cross-team data exists:** policy + premium read live from the pricing schema, so the loss-ratio /
  indication half is reachable, and "one book, two teams" is backed by real rows.

### What's thin for the story (fill for a *complete* narrative)
- **The downstream close is stubbed.** Lifecycle stages 7–8 (roll-forward → ranges → committee →
  Solvency II TP / IFRS 17 LIC / GL recon / capital) are marked "next". The story currently *ends* at
  sign-off; the compelling version continues into "and here's the number landing in the SII technical
  provisions." Even a single worked downstream cell would close the arc.
- **No time depth.** Everything is one valuation date (2026-Q4 vs a Q3 prior). The back-testing /
  champion-challenger story (and the agent that narrates it) needs **several historical quarters** of
  selections and outcomes. Right now "which method has been most accurate over 8 quarters" has no data
  behind it. This is the single biggest data gap for the *differentiator* story.
- **One segment grain.** 5 lines of business; the "we run 30+ classes" claim is asserted, not shown.
  A deeper synthetic segmentation (state × class, or 20+ classes) would let the book cockpit actually
  demonstrate scale.

### The concise story to tell (3 sentences, all data-backed today)
> *"Your claim ledger becomes a governed triangle that reconciles to the penny — no more_v7_FINAL.xlsx.
> The one late large loss that would have quietly over-reserved you by £369k is caught in the data,
> flagged for a human, overridden with a recorded reason, and the whole basis is reproducible six
> months later for the auditor. And every method — chain-ladder, your own R model, or a package you
> plug in — runs the same governed pipeline, so the number is defensible however it was produced."*

That story is **true and demonstrable on today's data.** The *bigger* story (MLOps for reserving,
downstream to capital, scale to 30+ classes) needs the three data fills above — which is why they
belong in the build plan's data workstream, not just the engine one.

### Data to add, in story-priority order
1. **Historical quarters** (≥6) of triangles, selections and emergence — unlocks back-testing,
   champion/challenger, the accuracy agents, and "time depth" in every diagnostic. Highest story value.
2. **One worked downstream landing** — the signed ultimate flowing into a Solvency II TP cell or an
   IFRS 17 LIC line — closes the arc from ledger to regulatory number.
3. **Deeper segmentation** — 20+ classes so the cockpit shows real scale.

---

## 5 · How this folds into the build plan

This review adds three things to `BUILD_PLAN_ENGINE_AND_POSITIONING.md`, none of which were in it:

- **A new small workstream E · Clarity** — per-datapoint "why" unfolds on every page (§1), and the
  "you are here in the close" breadcrumb. Hours, and it's the dev-language rule made whole.
- **Extends workstream C (AI)** — the five new agents in §2, kept inside the explain/draft/challenge
  triad; and a **new MCP capability** (§3) as its own item, mirroring pricing's `routes/mcp.py`.
- **A new workstream F · Story data** — the three data fills in §4, sequenced by story value
  (historical depth first). This is the prerequisite for the back-testing differentiator and the
  end-to-end narrative, and it's currently missing from the plan.

### Suggested phase placement
- **Phase 1** gains: E (clarity unfolds + breadcrumb) — cheap, and it's the "review each page" ask.
- **Phase 3** (the MLOps differentiator) gains: F1 (historical quarters) as its **data prerequisite**
  — without it, back-testing has nothing to test — plus the back-test/accuracy agents.
- **New Phase 3.5**: the MCP-by-chat capability, once the write endpoints are stable, so the
  "operate it by chat, same governance" beat has real operations behind it.
- **Phase 4** gains: F2 (downstream landing) and F3 (deeper segmentation) for the complete arc.

---

## 6 · The one thing to get right

Everything above serves a single SA principle: **the demo's credibility is the reconciliation, not
the UI.** Per-datapoint "why" (§1), agents that only explain/draft/challenge (§2), an MCP that writes
the *same governed row* the UI does (§3), and data that reconciles end to end (§4) all say the same
thing to the customer — *the governance lives in the platform, and you can reach it from any door.*
That is the story worth telling, and it's the story the data can already mostly back.
