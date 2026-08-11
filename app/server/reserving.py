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


def apply_reinsurance(gross_ultimate, qs_pct, xol_attach=None, xol_limit=None, xol_expected_recovery=None):
    """Take a GROSS aggregate ultimate to NET.

    IMPORTANT — grain matters, and getting it wrong is exactly what makes an actuary
    distrust a tool. Quota share is proportional, so it applies cleanly to the line
    AGGREGATE ultimate. An excess-of-loss layer attaches PER CLAIM (or per event),
    NOT to the aggregate ultimate — attaching a £3m XoL to a £13m line total would
    nonsensically cede most of the book. So at the aggregate we cede:
      * quota share on the whole ultimate, plus
      * an expected XoL recovery (modelled from the large losses that pierce the
        layer), if supplied — a single expected amount, not the layer applied to
        the aggregate.
    Returns (net_ultimate, ceded). xol_attach/xol_limit are carried only to describe
    the layer in the UI; they are not applied to the aggregate here.
    """
    g = float(gross_ultimate or 0.0)
    qs = float(qs_pct or 0.0)
    ceded_qs = g * qs
    ceded_xol = float(xol_expected_recovery or 0.0)   # expected recovery on large losses, per-risk
    net = g - ceded_qs - ceded_xol
    return round(max(net, 0.0), 2), round(ceded_qs + ceded_xol, 2)


def programme_for(lob):
    """The outwards RI programme for a line, or None. Read once; cheap."""
    row = sql.query_one(
        f"SELECT quota_share_pct, xol_attachment, xol_limit, xol_expected_recovery, note "
        f"FROM {F('reinsurance_programme')} WHERE line_of_business_code = '{sql.esc(lob)}'")
    if not row:
        return None
    return {"quota_share_pct": float(row.get("quota_share_pct") or 0.0),
            "xol_attachment": (float(row["xol_attachment"]) if row.get("xol_attachment") is not None else None),
            "xol_limit": (float(row["xol_limit"]) if row.get("xol_limit") is not None else None),
            "xol_expected_recovery": (float(row["xol_expected_recovery"]) if row.get("xol_expected_recovery") is not None else None),
            "note": row.get("note")}


def fit_tail(factors, method="EXPONENTIAL", n_extrapolate=6):
    """Fit a decay curve to the observed age-to-age factors and extrapolate a TAIL factor
    beyond the triangle — the thing a single '1.01' box can't do and an actuary always does.

    factors: {lag: factor} the selected/empirical development factors (the observed pattern).
    Returns {method, tail, fitted_factors, r2} where tail = product of the extrapolated
    factors' excess-over-1, i.e. the cumulative development still to come after the last
    observed lag.

    Methods, all fit to the *excess* development (f-1), which decays to zero:
      EXPONENTIAL   — (f_k - 1) = a * exp(-b*k)      [log-linear fit]
      INVERSE_POWER — (f_k - 1) = a * k^(-b)          [log-log fit]
    Both are standard tail families; we fit on the tail half of the pattern (where decay is
    visible) and extrapolate n_extrapolate periods, which is where >99% of the tail sits.
    Pure Python — no scipy — so it runs anywhere the app runs.
    """
    import math
    lags = sorted(factors)
    # excess development, only where it's positive (a factor below 1 isn't tail-shaped)
    pts = [(k, factors[k] - 1.0) for k in lags if factors[k] and factors[k] - 1.0 > 1e-6]
    if len(pts) < 2:
        return {"method": method, "tail": 1.0, "fitted_factors": [], "r2": None,
                "note": "not enough decaying factors to fit a tail"}
    # fit on the back half — the mature end, where the tail actually lives
    tail_pts = pts[len(pts) // 2:] if len(pts) >= 4 else pts

    def _linfit(xs, ys):
        n = len(xs); sx = sum(xs); sy = sum(ys)
        sxx = sum(x * x for x in xs); sxy = sum(x * y for x, y in zip(xs, ys))
        denom = n * sxx - sx * sx
        if abs(denom) < 1e-12:
            return None
        b = (n * sxy - sx * sy) / denom
        a = (sy - b * sx) / n
        # r2
        ymean = sy / n
        ss_tot = sum((y - ymean) ** 2 for y in ys) or 1e-12
        ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
        return a, b, 1.0 - ss_res / ss_tot

    if method == "INVERSE_POWER":
        xs = [math.log(k + 1) for k, _ in tail_pts]           # k+1 avoids log(0)
        ys = [math.log(e) for _, e in tail_pts]
        fit = _linfit(xs, ys)
        if not fit:
            return {"method": method, "tail": 1.0, "fitted_factors": [], "r2": None}
        a, b, r2 = fit
        model = lambda k: math.exp(a) * ((k + 1) ** b)
    else:  # EXPONENTIAL (default)
        xs = [k for k, _ in tail_pts]
        ys = [math.log(e) for _, e in tail_pts]
        fit = _linfit(xs, ys)
        if not fit:
            return {"method": method, "tail": 1.0, "fitted_factors": [], "r2": None}
        a, b, r2 = fit
        model = lambda k: math.exp(a) * math.exp(b * k)

    last = lags[-1]
    fitted = []
    tail = 1.0
    for i in range(1, n_extrapolate + 1):
        k = last + i
        excess = max(model(k), 0.0)
        if excess < 1e-5:
            break
        f = 1.0 + excess
        fitted.append(round(f, 5))
        tail *= f
    return {"method": method, "tail": round(tail, 5),
            "fitted_factors": fitted, "r2": (round(r2, 4) if r2 is not None else None)}


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
    # gross-to-net: every reserve is booked gross AND net. If a programme applies,
    # take the ultimate through it so the decision module shows both live.
    prog = programme_for(lob)
    if prog:
        net, ceded = apply_reinsurance(res["ultimate"], prog["quota_share_pct"],
                                       prog["xol_attachment"], prog["xol_limit"],
                                       prog["xol_expected_recovery"])
        res["ultimate_net"] = net
        res["ceded"] = ceded
        res["reinsurance"] = prog
    return {"lob": lob, "basis": basis, "last_n": last_n, "tail": tail,
            "empirical_factors": factors, "applied_factors": applied, "reserve": res}


def prior_selection(lob):
    """The genuine PRIOR quarter's approved pattern — the thing an actuary compares against,
    factor by factor. Deliberately NOT this quarter's elected row: we want the pattern carried
    forward from last close (id ...-PRIOR), the lowest valuation_date, so 'prior' means prior."""
    import json
    row = sql.query_one(
        f"SELECT selection_id, development_factors, tail_factor FROM {F('selected_development_pattern')} "
        f"WHERE line_of_business_code = '{sql.esc(lob)}' AND source_code = 'PRIOR_SELECTION' "
        f"AND status_code = 'APPROVED' AND selection_id LIKE '%PRIOR' "
        f"ORDER BY valuation_date ASC LIMIT 1")
    if not row or not row.get("development_factors"):
        # fall back to the oldest approved prior-selection row if the naming differs
        row = sql.query_one(
            f"SELECT selection_id, development_factors, tail_factor FROM {F('selected_development_pattern')} "
            f"WHERE line_of_business_code = '{sql.esc(lob)}' AND source_code = 'PRIOR_SELECTION' "
            f"AND status_code = 'APPROVED' ORDER BY valuation_date ASC LIMIT 1")
    if not row or not row.get("development_factors"):
        return None
    try:
        arr = [round(float(f), 4) for f in json.loads(row["development_factors"])]
    except Exception:
        return None
    return {"selection_id": row.get("selection_id"), "factors": arr,
            "tail": float(row.get("tail_factor") or 1.01)}


def prior_reserve(lob, tail=1.01):
    """The reserve implied by the genuine prior selection (for the delta) PLUS the prior factors
    themselves, so the UI can show prior-vs-empirical-vs-selected factor by factor."""
    p = prior_selection(lob)
    if not p:
        return None
    tri = read_triangle(lob)
    factors = {i: f for i, f in enumerate(p["factors"])}
    res = ultimate_ibnr(tri, factors, p["tail"])
    # carry the factor array + id so the decision grid can render the prior row
    res["factors"] = p["factors"]
    res["tail"] = p["tail"]
    res["selection_id"] = p["selection_id"]
    return res
