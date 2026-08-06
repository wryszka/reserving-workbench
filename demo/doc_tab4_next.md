# What we need from you

Two items from the discovery session are still outstanding. Both are what turn this from
a synthetic demonstration into your actual process.

## 1 · The LDF script, split into three parts

Split on the seams shown on tab 2 — it does not need to be tidy, and a simplified
version is fine:

- **Part 1 — data ingestion and pre-processing:** the up-front loss data build, including
  large-loss adjustment, claim exclusions, and claim-to-coverage remapping.
- **Part 2 — the selection point:** where the empirical factors are calculated and where
  a manual override would need to sit.
- **Part 3 — output and formatting:** what the downstream tables expect.

What we are looking for specifically is **where the decision points actually are** in the
current logic, so the intervention point lands in the right place rather than where we
have guessed it.

## 2 · A sample R indication

Synthetic or redacted is completely fine — the structure matters far more than the
numbers. What we need to see: what it reads, what shape it expects, and what it produces.
That tells us whether the contract on tab 3 is right.

## 3 · Federation to Discovery

The demonstration reads synthetic data. The real wire-up is a Lakehouse Federation
connection reading Discovery in place — **no ingestion project, and no waiting on the
OneShield loss feed to be validated**. To progress it we need:

- Connection details and a service account with read access to the relevant Discovery
  objects
- Confirmation of which tables the triangle should read
- Whoever owns network access between the two, to confirm the path

Premium data is already in Databricks, so that side needs nothing.

## Suggested sequence

| Step | What | Owner |
|---|---|---|
| 1 | Send the split script and a sample R indication | Hiscox |
| 2 | Point stage 1 at Discovery via Federation | Databricks, with Hiscox platform team |
| 3 | Reproduce one quarter's factors and reconcile against the current process | Joint |
| 4 | Wire the real R indication as a task in the job | Joint |
| 5 | Agree the review and approval routing for elections | Hiscox actuarial |

Step 3 is the one that matters: reproducing a known quarter and tying out to the existing
output is what makes this trustworthy enough to run alongside, and eventually replace,
the current script.

## Open questions for discussion

- Which line of business would you want to prove this on first?
- Who approves an LDF election, and does the threshold for review differ by line or by
  size of variance?
- Do you want the selection step to stay in Databricks, or is there an external tool
  that should keep making the pick? Either works — the step is a pluggable seam.
- How far back does a reproduction need to go to satisfy you that it ties out?
