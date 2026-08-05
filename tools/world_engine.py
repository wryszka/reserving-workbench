#!/usr/bin/env python3
"""reserving-workbench synthetic world engine.

Deterministically generates ONE reserving world for Bricksurance SE and writes
it to the claim ledger (1_raw_claim + 1_raw_claim_transaction). Everything the
workbench shows is DERIVED from this ledger - the triangle is a view over these
movements, so it reconciles to the penny and there is no separately-stored
triangle to drift. No business-level duplication.

Design invariants (so this merges cleanly into the gen2 World Engine later):
  * Golden-thread hero CLM-2026-000001 is preserved: Commercial Property, fire,
    accident year 2026, GBP, 450k incurred / 180k paid / 270k outstanding.
  * Losses develop monotonically to a plausible ultimate per line of business.
  * A DELIBERATE anomaly is seeded (Commercial Property, AY2023, the 12->24m
    step) so the empirical factor spikes and the override moment has a reason.
  * Fully deterministic (seeded) - reruns reproduce byte-identical amounts.

Usage (local dry-run writing CSVs to build/world/):
    uv run --native-tls --with pyyaml tools/world_engine.py --dry-run
On Databricks (writes Delta via the notebook wrapper) the same functions are
imported; --dry-run is for local inspection and the smoke test's expectations.
"""

import argparse
import csv
import random
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = 20260728

# Line-of-business "true" development: incremental paid as a fraction of
# ultimate in each development year (index = development lag, 0-based). These
# sum to < 1.0 before the tail; the tail closes the remainder.
LOB_DEV = {
    # long-tail liability develops slowly; property/motor faster
    "COMMERCIAL_PROPERTY":   [0.42, 0.28, 0.14, 0.08, 0.05, 0.02, 0.01],
    "COMMERCIAL_MOTOR":      [0.30, 0.30, 0.18, 0.10, 0.06, 0.04, 0.02],
    "GENERAL_LIABILITY":     [0.15, 0.22, 0.22, 0.16, 0.12, 0.08, 0.05],
    "PROFESSIONAL_INDEMNITY":[0.12, 0.20, 0.22, 0.18, 0.14, 0.09, 0.05],
    "MARINE":                [0.50, 0.25, 0.13, 0.07, 0.03, 0.01, 0.01],
}
# Case-reserve adequacy: incurred runs ahead of paid, converging to ultimate.
# Fraction of the yet-unpaid ultimate that is held as case reserve at each lag.
CASE_ADEQUACY = [0.85, 0.80, 0.72, 0.60, 0.45, 0.30, 0.0]

VALUATION_YEAR = 2026          # latest diagonal
ACCIDENT_YEARS = list(range(2019, 2027))
CCY = "GBP"

# Per-LOB expected ultimate for a "typical" accident year and claim counts.
LOB_PROFILE = {
    "COMMERCIAL_PROPERTY":    dict(claims=(8, 14),  sev=(60_000, 240_000)),
    "COMMERCIAL_MOTOR":       dict(claims=(10, 18), sev=(20_000, 120_000)),
    "GENERAL_LIABILITY":      dict(claims=(5, 10),  sev=(80_000, 400_000)),
    "PROFESSIONAL_INDEMNITY": dict(claims=(4, 8),   sev=(90_000, 500_000)),
    "MARINE":                 dict(claims=(4, 9),   sev=(50_000, 300_000)),
}


def _round2(x):
    return round(x + 1e-9, 2)


def _dev_fractions(lob):
    """Return incremental-paid fractions that sum to exactly 1.0 (tail closes it)."""
    base = LOB_DEV[lob][:]
    s = sum(base)
    base.append(_round2(1.0 - s))   # tail bucket closes to ultimate
    return base


def generate(seed=SEED):
    """Build claims + movements. Returns (claims, transactions) as dict lists."""
    rng = random.Random(seed)
    claims, txns = [], []
    claim_seq = 0
    tx_seq = 0

    def new_claim_id(ay):
        nonlocal claim_seq
        claim_seq += 1
        return f"CLM-{ay}-{claim_seq:06d}"

    def add_txn(claim_id, tyear, ttype, amount):
        nonlocal tx_seq
        tx_seq += 1
        txns.append(dict(
            claim_transaction_id=f"CTX-{tx_seq:07d}",
            claim_id=claim_id,
            transaction_year=tyear,
            transaction_date=f"{tyear}-06-30",
            claim_transaction_type_code=ttype,
            amount=_round2(amount),
            currency_code=CCY,
        ))

    def emit_claim(claim_id, lob, ay, ultimate, policy_id):
        """Emit the movement stream for one claim developing to `ultimate`."""
        fracs = _dev_fractions(lob)
        max_lag = VALUATION_YEAR - ay        # lags observable by the valuation date
        cum_paid = 0.0
        for lag, frac in enumerate(fracs):
            tyear = ay + lag
            if tyear > VALUATION_YEAR:
                break
            inc_paid = ultimate * frac
            # split paid into indemnity (85%) + expense (15%)
            add_txn(claim_id, tyear, "INDEMNITY_PAYMENT", inc_paid * 0.85)
            add_txn(claim_id, tyear, "EXPENSE_PAYMENT", inc_paid * 0.15)
            cum_paid += inc_paid
            # case reserve movement: set case so incurred = paid + case ≈ adequacy view
            unpaid = max(ultimate - cum_paid, 0.0)
            target_case = unpaid * CASE_ADEQUACY[min(lag, len(CASE_ADEQUACY) - 1)]
            # movement is change vs previous case; previous tracked implicitly
            add_txn(claim_id, tyear, "CASE_RESERVE_MOVEMENT", target_case - _prev_case.get(claim_id, 0.0))
            _prev_case[claim_id] = target_case

    _prev_case = {}

    # ---- the golden-thread hero, pinned exactly -------------------------------
    hero_id = "CLM-2026-000001"
    claims.append(dict(claim_id=hero_id, policy_id="POL-2026-000001",
                       accident_year=2026, loss_date="2026-03-14",
                       line_of_business_code="COMMERCIAL_PROPERTY",
                       report_date="2026-03-20"))
    # 450k incurred / 180k paid / 270k outstanding at the 2026 valuation (lag 0)
    add_txn(hero_id, 2026, "INDEMNITY_PAYMENT", 153_000.00)   # 85% of 180k
    add_txn(hero_id, 2026, "EXPENSE_PAYMENT", 27_000.00)      # 15% of 180k
    add_txn(hero_id, 2026, "CASE_RESERVE_MOVEMENT", 270_000.00)  # case = 270k
    _prev_case[hero_id] = 270_000.00
    claim_seq = 1   # hero consumed 000001 for AY2026

    # ---- the rest of the world ------------------------------------------------
    for lob, prof in LOB_PROFILE.items():
        for ay in ACCIDENT_YEARS:
            n = rng.randint(*prof["claims"])
            for _ in range(n):
                # keep AY2026 CP from clobbering the hero id space cleanly
                cid = new_claim_id(ay)
                if cid == hero_id:
                    cid = new_claim_id(ay)
                sev_lo, sev_hi = prof["sev"]
                ultimate = rng.uniform(sev_lo, sev_hi)
                claims.append(dict(claim_id=cid,
                                   policy_id=f"POL-{ay}-{rng.randint(1,900000):06d}",
                                   accident_year=ay,
                                   loss_date=f"{ay}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
                                   line_of_business_code=lob,
                                   report_date=None))
                emit_claim(cid, lob, ay, ultimate, cid)

    # ---- seed the DELIBERATE anomaly -----------------------------------------
    # Commercial Property, AY2023: inflate the 12->24m (lag 1) incremental paid
    # with a large late-reported loss, so the empirical 12-24 factor spikes and
    # the actuary has a reason to override with the prior pattern. Auditable.
    anomaly_id = "CLM-2023-ANOMALY"
    claims.append(dict(claim_id=anomaly_id, policy_id="POL-2023-500001",
                       accident_year=2023, loss_date="2023-11-02",
                       line_of_business_code="COMMERCIAL_PROPERTY",
                       report_date="2024-08-15"))
    # nothing paid at lag 0 (late reported); a big spike lands in 2024 (lag 1)
    add_txn(anomaly_id, 2024, "INDEMNITY_PAYMENT", 900_000.00)
    add_txn(anomaly_id, 2024, "EXPENSE_PAYMENT", 150_000.00)
    add_txn(anomaly_id, 2024, "CASE_RESERVE_MOVEMENT", 400_000.00)
    # partial run-off afterwards
    add_txn(anomaly_id, 2025, "INDEMNITY_PAYMENT", 250_000.00)
    add_txn(anomaly_id, 2025, "CASE_RESERVE_MOVEMENT", -200_000.00)

    # ---- seed REOPENED claims -------------------------------------------------
    # Reopens are a real and painful movement type at every close: a claim that
    # settled years ago comes back, and a mature cohort that should be quietly
    # running off suddenly develops. Without them the "what changed in my data"
    # view is missing its most interesting row, so the world carries a handful.
    #
    # Deliberately placed on MATURE cohorts (2019-2021) in lines OTHER than the
    # Commercial Property AY2023 step, so the seeded 12->24m anomaly and the
    # factor story around it are untouched: a 2026 movement on a 2019 accident
    # year lands at development lag 7, nowhere near the 0->1 factor.
    #
    # The ledger shape is what makes these detectable downstream: pay, close
    # (case released to zero), a GAP of quiet years, then activity again.
    reopens = [
        # (accident_year, lob, closed_after_year, reopen_paid, reopen_case)
        (2019, "GENERAL_LIABILITY", 2021, 185_000.00, 120_000.00),
        (2020, "GENERAL_LIABILITY", 2022, 96_000.00, 64_000.00),
        (2019, "PROFESSIONAL_INDEMNITY", 2021, 240_000.00, 160_000.00),
        (2021, "COMMERCIAL_MOTOR", 2023, 42_000.00, 28_000.00),
        (2020, "COMMERCIAL_PROPERTY", 2022, 78_000.00, 52_000.00),
    ]
    for i, (ay, lob, closed_after, paid, case) in enumerate(reopens, 1):
        rid = f"CLM-{ay}-RE{i:04d}"
        claims.append(dict(claim_id=rid, policy_id=f"POL-{ay}-9{i:05d}",
                           accident_year=ay, loss_date=f"{ay}-05-{10+i:02d}",
                           line_of_business_code=lob, report_date=f"{ay}-06-{10+i:02d}"))
        # original life of the claim: pays down and closes (case released to zero)
        original = paid * 1.6
        for lag, frac in enumerate([0.45, 0.35, 0.20]):
            tyear = ay + lag
            if tyear > closed_after:
                break
            add_txn(rid, tyear, "INDEMNITY_PAYMENT", original * frac * 0.85)
            add_txn(rid, tyear, "EXPENSE_PAYMENT", original * frac * 0.15)
        add_txn(rid, closed_after, "CASE_RESERVE_MOVEMENT", 0.0)   # closed: no case held
        # ... then a gap of quiet years, and the reopen at the current valuation
        add_txn(rid, VALUATION_YEAR, "INDEMNITY_PAYMENT", paid * 0.85)
        add_txn(rid, VALUATION_YEAR, "EXPENSE_PAYMENT", paid * 0.15)
        add_txn(rid, VALUATION_YEAR, "CASE_RESERVE_MOVEMENT", case)
        _prev_case[rid] = case

    return claims, txns


def write_csvs(claims, txns, out=ROOT / "build" / "world"):
    out.mkdir(parents=True, exist_ok=True)
    with (out / "1_raw_claim.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["claim_id", "policy_id", "accident_year",
                                          "loss_date", "line_of_business_code", "report_date"])
        w.writeheader()
        w.writerows(claims)
    with (out / "1_raw_claim_transaction.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["claim_transaction_id", "claim_id", "transaction_year",
                                          "transaction_date", "claim_transaction_type_code",
                                          "amount", "currency_code"])
        w.writeheader()
        w.writerows(txns)
    return out


def summarise(claims, txns):
    hero = [t for t in txns if t["claim_id"] == "CLM-2026-000001"]
    paid = sum(t["amount"] for t in hero if t["claim_transaction_type_code"] in ("INDEMNITY_PAYMENT", "EXPENSE_PAYMENT"))
    case = sum(t["amount"] for t in hero if t["claim_transaction_type_code"] == "CASE_RESERVE_MOVEMENT")
    print(f"Claims: {len(claims)}  Transactions: {len(txns)}")
    print(f"Hero CLM-2026-000001: paid={paid:,.2f} case={case:,.2f} incurred={paid+case:,.2f} "
          f"(expect paid=180,000.00 case=270,000.00 incurred=450,000.00)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="write CSVs to build/world/ and summarise")
    args = ap.parse_args()
    claims, txns = generate()
    summarise(claims, txns)
    if args.dry_run:
        out = write_csvs(claims, txns)
        print(f"Wrote CSVs to {out}")


if __name__ == "__main__":
    main()
