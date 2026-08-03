"""Live reserving math for the interactive selection module — triangle → empirical
factors under a chosen averaging basis → chain-ladder ultimate. Pure Python over
rows read from the loss_development view; no heavy deps. Deterministic."""
from . import config, sql

F = config.fqn


def read_triangle(lob):
    """Return {ay: {lag: cumulative_paid}} for one line of business."""
    rows = sql.query(
        f"SELECT accident_year, development_lag, cumulative_paid "
        f"FROM {F('loss_development')} WHERE line_of_business_code = '{sql.esc(lob)}' "
        f"ORDER BY accident_year, development_lag")
    tri = {}
    for r in rows:
        tri.setdefault(int(r["accident_year"]), {})[int(r["development_lag"])] = float(r["cumulative_paid"])
    return tri


def max_lag(tri):
    return max((max(r) for r in tri.values()), default=0)


def empirical_factors(tri, basis="VOLUME_WEIGHTED", last_n=5):
    """Age-to-age factors under the chosen averaging basis. Returns {lag: factor}."""
    ml = max_lag(tri)
    factors = {}
    for k in range(ml):
        pairs = [(tri[ay][k], tri[ay][k + 1], ay) for ay in tri if k in tri[ay] and (k + 1) in tri[ay]]
        if not pairs:
            factors[k] = 1.0
            continue
        if basis == "VOLUME_WEIGHTED":
            num = sum(b for _, b, _ in pairs); den = sum(a for a, _, _ in pairs)
            f = num / den if den else 1.0
        elif basis == "SIMPLE_AVERAGE":
            r = [b / a for a, b, _ in pairs if a]
            f = sum(r) / len(r) if r else 1.0
        elif basis == "LAST_N":
            recent = sorted(pairs, key=lambda p: p[2])[-int(last_n):]
            num = sum(b for _, b, _ in recent); den = sum(a for a, _, _ in recent)
            f = num / den if den else 1.0
        elif basis == "MEDIAN":
            r = sorted(b / a for a, b, _ in pairs if a)
            f = r[len(r) // 2] if r else 1.0
        elif basis == "GEOMETRIC":
            r = [b / a for a, b, _ in pairs if a and b > 0]
            prod = 1.0
            for x in r:
                prod *= x
            f = prod ** (1.0 / len(r)) if r else 1.0
        else:
            num = sum(b for _, b, _ in pairs); den = sum(a for a, _, _ in pairs)
            f = num / den if den else 1.0
        factors[k] = round(f, 4)
    return factors


def latest_diagonal(tri):
    return {ay: (max(r), r[max(r)]) for ay, r in tri.items()}


def ultimate_ibnr(tri, factors, tail=1.0):
    """Chain-ladder ultimate + IBNR across all accident years given a factor set."""
    ml = max_lag(tri)
    diag = latest_diagonal(tri)
    ult_total = paid_total = 0.0
    per_ay = []
    for ay, (lag, paid) in diag.items():
        cdf = tail
        for k in range(lag, ml):
            cdf *= factors.get(k, 1.0)
        ult = paid * cdf
        ult_total += ult; paid_total += paid
        per_ay.append({"accident_year": ay, "paid": round(paid, 2), "ultimate": round(ult, 2),
                       "ibnr": round(max(ult - paid, 0.0), 2)})
    return {"ultimate": round(ult_total, 2), "paid": round(paid_total, 2),
            "ibnr": round(max(ult_total - paid_total, 0.0), 2),
            "outstanding": round(ult_total - paid_total, 2), "per_ay": per_ay}


def compute(lob, basis="VOLUME_WEIGHTED", last_n=5, tail=1.01, overrides=None):
    """Recompute empirical factors (with any manual overrides applied) + resulting reserve.
    overrides: {lag(str/int): factor} — manual per-factor overrides layered on the basis."""
    tri = read_triangle(lob)
    factors = empirical_factors(tri, basis, last_n)
    applied = dict(factors)
    if overrides:
        for k, v in overrides.items():
            try:
                applied[int(k)] = round(float(v), 4)
            except (TypeError, ValueError):
                pass
    res = ultimate_ibnr(tri, applied, tail)
    return {"lob": lob, "basis": basis, "last_n": last_n, "tail": tail,
            "empirical_factors": factors, "applied_factors": applied, "reserve": res}


def prior_reserve(lob, tail=1.01):
    """The reserve implied by the current APPROVED prior selection (for delta comparison)."""
    import json
    row = sql.query_one(
        f"SELECT development_factors, tail_factor FROM {F('selected_development_pattern')} "
        f"WHERE line_of_business_code = '{sql.esc(lob)}' AND source_code = 'PRIOR_SELECTION' "
        f"AND status_code = 'APPROVED' ORDER BY valuation_date DESC LIMIT 1")
    tri = read_triangle(lob)
    if not row or not row.get("development_factors"):
        return None
    try:
        arr = json.loads(row["development_factors"])
    except Exception:
        return None
    factors = {i: float(f) for i, f in enumerate(arr)}
    t = float(row.get("tail_factor") or tail)
    return ultimate_ibnr(tri, factors, t)
