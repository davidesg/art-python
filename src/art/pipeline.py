"""
art.pipeline — execution layer for the Box-Jenkins-Treadway process.

Architectural role (see docs/ARCHITECTURE.md §6): the suite separates
    evidence   (describe.py)
    policy     (policy.py — the decision rules)
    execution  (THIS module — builds, writes, fits and diagnoses a spec)

This module owns the low-level model-construction / .inp I/O primitives
(_make_model, _write_inp, _load_fitted, …) and the two orchestration entry
points used by both the guided and autonomous MCP tools:

    build_and_fit(ts, spec, ...)  — one make→write→fit→diagnose step
    run_full(ts, ...)             — the full autonomous BJT loop

Keeping a single implementation of the outlier-addition loop here removes the
duplication that used to live, copied, inside build_model and batch_build.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _load_ts_model(path: str):
    """Load (ts, model) from an .inp file."""
    import fue
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    return fue.inp.load(path)


def _write_bare_inp(ts, path: str) -> None:
    """Write a minimal fue .inp with only series data and no model spec."""
    freq    = ts.freq
    begyear = int(ts.start[0])
    begtime = int(ts.start[1]) if freq > 1 else begyear  # annual: year repeated twice
    n_ifadf = freq // 2 + 1 if freq > 1 else 1
    lines = [
        "************************************************",
        "* Input file for program FUE                   *",
        "* DOCTYPE ATSW-interface SYSTEM                *",
        "************************************************",
        "",
        "** Frequency of time series: either 1(A), 4(Q) or 12(M):",
        f" {freq}",
        "** Number of observations and starting date of time series:",
        f" {ts.nobs} {begtime:2d} {begyear} {ts.name}",
        "** Number of deterministic variables (including seasonal components):",
        " 0",
        "**Number and orders of regular AR operators:",
        " 0",
        "** Number and orders of annual AR operators:",
        " 0",
        "** Number and orders of regular MA operators:",
        " 0",
        "** Number and orders of anual MA operators:",
        " 0",
        "** Number and frequencies of regular AR(2) operators with fixed frequency:",
        " 0",
        "** Number and frequencies of regular MA(2) operators with fixed frequency:",
        " 0",
        "** Mean parameter (mu):",
        "0",
        "** Box-Cox lambda, regular differences and complete annual differences:",
        "1.00 0 0",
        "** Individual factors of the annual difference (from freq 0.0): ",
        " " + " ".join(["0"] * n_ifadf),
        "** ACF/PACF bands (0 Automatic) and reescaling factor: ",
        f" 0 {_RESCALE_FACTOR:.2f}",
        "** Time series (stochastic and non-standard deterministic variables): ",
    ]
    for v in ts.data:
        lines.append(f"{v:.10f} ")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def _load_fitted(path: str):
    """Load and fit a model from .pre or .inp file."""
    import fue
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    ts, m = fue.load(path)
    m.fit()
    return ts, m


def _obs_to_date(begyear, begtime, freq, at_0based):
    """Convert 0-based obs index to (period, year) for writing .inp files."""
    offset = begtime - 1 + at_0based
    return offset % freq + 1, begyear + offset // freq


def _write_inp(ts, model, output_path: str) -> None:
    """
    Write a fue .inp file from a (ts, model) pair.

    Replicates the format produced by gtk_fue file_io.c:write_inp_file().
    Handles cos/sin/alter/pulse/step/ramp deterministic variables and
    AR/MA operators (regular and seasonal).
    """
    import numpy as np
    freq = ts.freq
    start = ts.start
    start_list = list(start) if hasattr(start, '__iter__') else [int(start), 1]
    beg_year   = start_list[0]
    beg_period = start_list[1] if freq > 1 else 1
    n    = ts.nobs
    name = ts.name or "series"

    itvs = list(model.interventions or [])
    ndet = len(itvs)

    def _itv_line(itv):
        t = itv.type
        if t in ("pulse", "impulse", "compimp"):
            period, year = _obs_to_date(beg_year, beg_period, freq, itv.at)
            c_type = "compimp" if t == "compimp" else "impulse"
            return f"{c_type} {period} {year}" if freq > 1 else f"impulse {year}"
        elif t in ("step", "ramp"):
            period, year = _obs_to_date(beg_year, beg_period, freq, itv.at)
            return f"{t} {period} {year}" if freq > 1 else f"{t} {year}"
        elif t in ("cos", "sin"):
            h = int(itv.harmonic) if hasattr(itv, "harmonic") else 1
            return f"{t} {h}"
        elif t == "alter":
            return "alter"
        elif t in ("trend", "easter"):
            return t
        else:
            return t  # unknown: just emit the type name

    lines = [
        "************************************************",
        "* Input file for program FUE                   *",
        "* DOCTYPE ATSW-interface SYSTEM                *",
        "************************************************",
        "",
        "** Frequency of time series: either 1(A), 4(Q) or 12(M):",
        f" {freq}",
        "** Number of observations and starting date of time series:",
    ]
    if freq > 1:
        lines.append(f" {n}  {beg_period} {beg_year} {name}")
    else:
        lines.append(f" {n}  1 {beg_year} {name}")

    lines += [
        "** Number of deterministic variables (including seasonal components):",
        f"{ndet}",
    ]

    if ndet > 0:
        lines.append("**")
        for itv in itvs:
            lines.append(_itv_line(itv))
        lines.append("**")

        # Omega orders (MA order of each det var's transfer function)
        omega_orders = []
        for itv in itvs:
            om = itv.omega if hasattr(itv, "omega") and itv.omega else [0.0]
            omega_orders.append(len(om) - 1)
        lines.append(" ".join(str(o) for o in omega_orders))

        # Omega coefs per det var
        for itv in itvs:
            om   = itv.omega      if (hasattr(itv, "omega")      and itv.omega)      else [0.0]
            omf  = itv.omega_free if (hasattr(itv, "omega_free") and itv.omega_free) else [True] * len(om)
            lines.append("**")
            for v, f in zip(om, omf):
                lines.append(f"{v:.6f}  {1 if f else 0}")

        # Delta orders
        lines.append("**")
        delta_orders = []
        for itv in itvs:
            dl = itv.delta if hasattr(itv, "delta") and itv.delta else []
            delta_orders.append(len(dl))
        lines.append(" ".join(str(o) for o in delta_orders))

        # Delta coefs (only where delta_order > 0)
        for itv, dord in zip(itvs, delta_orders):
            if dord > 0:
                dl  = itv.delta
                dlf = itv.delta_free if (hasattr(itv, "delta_free") and itv.delta_free) else [True] * dord
                lines.append("**")
                for v, f in zip(dl, dlf):
                    lines.append(f"{v:.6f}  {1 if f else 0}")

    def _arma_block(factors, free_lists, orders, label):
        n_ops = len(factors)
        if n_ops == 0:
            return [f"** {label}", "0"]
        order_str = " ".join(str(o) for o in orders)
        block = [f"** {label}", f"{n_ops} {order_str}"]
        for coefs, frees in zip(factors, free_lists):
            block.append("**")
            for v, f in zip(coefs, frees):
                block.append(f"{v:.6f}  {1 if f else 0}")
        return block

    def _free_or_default(factors, free_lists):
        """Return free_lists if present, else list of all-True lists matching factors."""
        if free_lists is None:
            return [[True] * len(f) for f in factors]
        return free_lists

    ar   = model.ar   or []
    ar_f = _free_or_default(ar,   model.ar_free)
    ma   = model.ma   or []
    ma_f = _free_or_default(ma,   model.ma_free)
    ar_s = model.ar_s or []
    ar_sf= _free_or_default(ar_s, model.ar_s_free if hasattr(model, "ar_s_free") else None)
    ma_s = model.ma_s or []
    ma_sf= _free_or_default(ma_s, model.ma_s_free if hasattr(model, "ma_s_free") else None)

    def _orders(factors):
        return [len(f) for f in factors]

    lines += _arma_block(ar,   ar_f,  _orders(ar),  "Number and orders of regular AR operators:")
    lines += _arma_block(ar_s, ar_sf, _orders(ar_s), "Number and orders of annual AR operators:")
    lines += _arma_block(ma,   ma_f,  _orders(ma),  "Number and orders of regular MA operators:")
    lines += _arma_block(ma_s, ma_sf, _orders(ma_s), "Number and orders of anual MA operators:")

    # Fixed-frequency AR2/MA2
    ar2f = getattr(model, "ar_f", None) or []
    ma2f = getattr(model, "ma_f", None) or []

    def _ffixed_block(factors, label):
        if not factors:
            return [f"** {label}", "0"]
        freqs_str = " ".join(str(int(f.freq)) for f in factors)
        block = [f"** {label}", f"{len(factors)} {freqs_str}"]
        for f in factors:
            block.append("**")
            block.append(f"{f.coef:.6f}  {1 if f.free else 0}")
        return block

    lines += _ffixed_block(ar2f, "Number and frequencies of regular AR(2) operators with fixed frequency:")
    lines += _ffixed_block(ma2f, "Number and frequencies of regular MA(2) operators with fixed frequency:")

    # Mean
    mu      = float(getattr(model, "mu0", 0.0) or 0.0)
    mu_free = bool(getattr(model, "estimate_mu", False) or False)
    lines += ["** Mean parameter (mu):"]
    if mu_free:
        lines.append(f"{mu:.6f} 1")
    else:
        lines.append("0")

    # Box-Cox and differences
    lam = model.boxlam if model.boxlam is not None else 1.0
    d   = model.d   or 0
    D   = model.D   or 0
    lines += [
        "** Box-Cox lambda, m. Regular differences and complete annual differences:",
        f" {lam:.2f}  {d}  {D}",
        "** Individual factors of the annual difference (starting at freq 0.0):",
    ]
    if freq > 1:
        ifadf = getattr(model, "ifadf", None)
        if ifadf is None:
            ifadf = [0] * (freq // 2 + 1)
        lines.append(" ".join(str(v) for v in ifadf))
    else:
        lines.append(" 0")

    lines += [
        "** ACF/PACF bands (0 Automatic) and reescaling factor:",
        f" 0 {_RESCALE_FACTOR:.2f}",
        "** Time series (stochastic and non-standard deterministic variables):",
    ]
    for v in np.asarray(ts.data, dtype=float):
        lines.append(f"{v:.6f} ")

    with open(output_path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


# ── ARMA starting values: Yule-Walker (AR) + Hannan-Rissanen (MA) ───────────
# New AR/MA parameters are initialised from data-driven pre-estimations instead
# of crude constants (old: AR 0.0, MA -0.3), so each iterative step starts near
# the optimum. fue stores MA in the Box-Jenkins convention N_t = (1 - θB) a_t
# (θ>0), so Hannan-Rissanen returns θ = -b (b = regression coef on the innovation
# proxy). The MEG over-differencing witness keeps its own rule (coef=-0.9) and is
# NOT touched here.

def _autocov(x, maxlag):
    import numpy as np
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    x = x - x.mean()
    n = len(x)
    if n <= maxlag + 1:
        maxlag = max(0, n - 2)
    return np.array([float(np.dot(x[: n - k], x[k:])) / n for k in range(maxlag + 1)])


def _shrink_stationary(coef):
    """Shrink coef geometrically until 1 - Σ coef_k z^k has all roots strictly
    outside the unit circle (stationary AR / invertible MA in fue's convention)."""
    import numpy as np
    coef = np.asarray(coef, float)
    if coef.size == 0 or not np.all(np.isfinite(coef)):
        return np.zeros(coef.shape)
    for c in (1.0, 0.9, 0.8, 0.6, 0.4, 0.2):
        test = coef * (c ** np.arange(1, coef.size + 1))
        # characteristic polynomial 1 - Σ test_k z^k, highest degree first for
        # np.roots; stationary/invertible ⟺ all roots strictly outside unit circle.
        roots = np.roots(np.concatenate([-test[::-1], [1.0]]))
        if roots.size == 0 or np.min(np.abs(roots)) > 1.001:
            return test
    return np.zeros(coef.shape)


def _yw_ar(x, p, s=1):
    """Yule-Walker AR(p) at lag spacing s (s=1 regular, s=freq seasonal).
    Returns φ in (1 - φ₁B^s - … - φ_pB^{ps}); stationary."""
    import numpy as np
    if p <= 0:
        return []
    ac = _autocov(x, p * s)
    g = ac[0::s][: p + 1]
    if g.size < p + 1 or g[0] <= 0:
        return [0.0] * p
    R = np.array([[g[abs(i - j)] for j in range(p)] for i in range(p)])
    try:
        phi = np.linalg.solve(R, g[1: p + 1])
    except np.linalg.LinAlgError:
        return [0.0] * p
    return [float(v) for v in _shrink_stationary(phi)]


def _hr_ma(x, q, s=1):
    """Hannan-Rissanen MA(q) at lag spacing s. Returns θ in fue's Box-Jenkins
    convention (1 - θ₁B^s - …), i.e. θ = -b; invertible."""
    import numpy as np
    if q <= 0:
        return []
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    x = x - x.mean()
    n = len(x)
    k = int(min(max(10, 3 * q * s), max(1, n // 4)))
    phi = np.asarray(_yw_ar(x, k), float)
    if phi.size < k:
        phi = np.concatenate([phi, np.zeros(k - phi.size)])
    e = np.zeros(n)
    for t in range(k, n):
        e[t] = x[t] - float(np.dot(phi, x[t - 1:: -1][:k]))
    lags = [j * s for j in range(1, q + 1)]
    maxlag = k + max(lags)
    if n - maxlag < q + 2:
        return [-0.3] * q
    Y = x[maxlag:]
    X = np.column_stack([e[maxlag - L: n - L] for L in lags])
    try:
        b, *_ = np.linalg.lstsq(X, Y, rcond=None)
    except Exception:
        return [-0.3] * q
    return [float(v) for v in _shrink_stationary(-np.asarray(b, float))]


def _arma_starts(resid, p, q, P, Q, s):
    """(ar, ma, ar_s, ma_s) initial-value lists from a residual/differenced series,
    Yule-Walker for AR/AR_s and Hannan-Rissanen for MA/MA_s. Falls back to the old
    constants (AR 0.0, MA -0.3) if resid is unusable."""
    import numpy as np
    ok = (resid is not None and np.size(resid) > 8
          and np.all(np.isfinite(np.asarray(resid, float))))
    if not ok:
        return ([0.0] * p, [-0.3] * q, [0.0] * P, [-0.3] * Q)
    ar   = (_yw_ar(resid, p)      if p > 0 else []) or [0.0] * p
    ma   = (_hr_ma(resid, q)      if q > 0 else []) or [-0.3] * q
    ar_s = (_yw_ar(resid, P, s=s) if P > 0 else []) or [0.0] * P
    ma_s = (_hr_ma(resid, Q, s=s) if Q > 0 else []) or [-0.3] * Q
    return (ar, ma, ar_s, ma_s)


# Rescaling factor written into every .inp (see _write_inp / the minimal writer).
# fue estimates on  refactor * BoxCox_lam(data)  (fue_api.c: DataMat = refactor *
# transform(data)), so mu lives in this rescaled space and its seed must too.
_RESCALE_FACTOR = 100.0


def _mu_seed(ts, lam, d, D, estimate_mu):
    """Pre-estimate of mu for the .inp: the sample mean of the *transformed,
    differenced* series, in the rescaled space fue estimates in.

    fue estimates mu on ``refactor * BoxCox_lam(data)`` after ``d`` regular and
    ``D`` seasonal differences.  For d=0 this is the level mean (e.g. ~126 for an
    untransformed series, ~6.76 for log CPI); for d>=1 it is ~0 (a drift).
    Seeding mu at 0 while the (rescaled) data sit far from 0 strands the exact-ML
    optimiser in a degenerate optimum where a near-unit AR root absorbs the level
    (BUG-0001).  Returns 0.0 when mu is not estimated or the series is unusable.
    """
    if not estimate_mu:
        return 0.0
    import numpy as np
    try:
        yv = np.asarray(getattr(ts, "data", getattr(ts, "values", None)), float)
        yv = np.log(yv) if abs(lam) < 1e-8 else np.sign(yv) * np.abs(yv) ** lam
        w = yv
        freq = int(getattr(ts, "freq", 1) or 1)
        for _ in range(int(d or 0)):
            w = np.diff(w)
        for _ in range(int(D or 0)):
            w = w[freq:] - w[:-freq]
        if w.size == 0 or not np.all(np.isfinite(w)):
            return 0.0
        return _RESCALE_FACTOR * float(np.mean(w))
    except Exception:
        return 0.0


def _build_arma_on_model(m_base, p: int, q: int,
                         P: int = 0, Q: int = 0,
                         estimate_mu: bool = False):
    """
    Return a new unfitted fue.Model that keeps all interventions and harmonics
    from m_base but replaces the ARMA specification with (p, q, P, Q).

    Used by confirm_and_estimate(base_pre_path=...) to add ARMA to a model
    that already has its outlier interventions estimated.
    """
    import fue
    import numpy as np

    # Data-driven starting values for the NEW ARMA parameters, from the residuals
    # of the (fitted) base model — Yule-Walker (AR/AR_s), Hannan-Rissanen (MA/MA_s).
    resid = None
    try:
        if getattr(m_base, "_result", None) is None:
            m_base.fit()
        r = m_base.residuals
        resid = np.asarray(getattr(r, "data", getattr(r, "values", r)), float)
    except Exception:
        resid = None
    s_freq = int(getattr(m_base.series, "freq", 12))
    ar_i, ma_i, ars_i, mas_i = _arma_starts(resid, p, q, P, Q, s_freq)

    if p > 0:
        ar   = [ar_i]
        ar_f = [[True] * p]
    elif q == 0 and P == 0 and Q == 0:
        # Keep the p=0,q=0 workaround only when there is truly no ARMA at all
        ar   = m_base.ar or [[0.0]]
        ar_f = m_base.ar_free or [[False]]
    else:
        ar   = []
        ar_f = []

    ma   = [ma_i] if q > 0 else []
    ma_f = [[True]  * q] if q > 0 else []

    ar_s_val  = [ars_i] if P > 0 else []
    ar_sf_val = [[True] * P] if P > 0 else []
    ma_s_val  = [mas_i] if Q > 0 else []
    ma_sf_val = [[True] * Q] if Q > 0 else []

    return fue.Model(
        m_base.series,
        d=m_base.d, D=m_base.D, boxlam=m_base.boxlam,
        ar=ar,       ar_free=ar_f       if ar   else None,
        ma=ma,       ma_free=ma_f       if ma   else None,
        ar_s=ar_s_val,  ar_s_free=ar_sf_val if ar_s_val  else None,
        ma_s=ma_s_val,  ma_s_free=ma_sf_val if ma_s_val  else None,
        interventions=list(m_base.interventions or []),
        ifadf=list(m_base.ifadf or []),
        mu=_mu_seed(m_base.series, m_base.boxlam, m_base.d, m_base.D, estimate_mu),
        estimate_mu=estimate_mu,
        refactor=m_base.refactor,
    )


def _make_model(ts, lam: float, d: int, D: int,
                p: int, q: int, n_harmonics: int,
                extra_itvs: list | None = None,
                P: int = 0, Q: int = 0,
                estimate_mu: bool = False):
    """
    Build a fue.Model from SARIMA(p,d,q)(P,D,Q)_s spec.

    When D=0: harmonic det-vars (cos/sin + alter) + optional extra interventions.
    When D=1: seasonal AR/MA operators; no harmonics added.
    extra_itvs : list of (at_0based, form_str) tuples for pulse/step/ramp

    Known fue C backend bug: combining ar_s (P≥1) AND ma_s (Q≥1) simultaneously
    crashes the C estimator (Aborted/segfault — see fue/TODO.md, AR_s+MA_s entry).
    Only P=0,Q≥1 or P≥1,Q=0 are safe.  Use estimate_py() as workaround if needed.
    """
    import fue
    import numpy as np
    freq = ts.freq

    # Data-driven ARMA starting values (Yule-Walker AR / Hannan-Rissanen MA) from
    # the differenced Box-Cox series. For D=1 (no harmonics) this is the clean
    # ∇^d∇_s series; for D=0 the harmonics are not yet removed, so it is a rough
    # start for the regular AR/MA (still better than the old constants).
    resid_ref = None
    try:
        yv = np.asarray(getattr(ts, "data", getattr(ts, "values", None)), float)
        yv = np.log(yv) if abs(lam) < 1e-8 else np.sign(yv) * np.abs(yv) ** lam
        w = yv
        for _ in range(int(d)):
            w = np.diff(w)
        for _ in range(int(D)):
            w = w[freq:] - w[:-freq]
        resid_ref = w
    except Exception:
        resid_ref = None
    ar_i, ma_i, ars_i, mas_i = _arma_starts(resid_ref, p, q, P, Q, freq)

    # Workaround for fue C crash when nar=0 AND nma=0: add AR(1) phi=0 fixed.
    if p > 0:
        ar   = [ar_i]
        ar_f = [[True] * p]
    elif q == 0:
        ar   = [[0.0]]
        ar_f = [[False]]
    else:
        ar   = []
        ar_f = []
    ma   = [ma_i] if q > 0 else []
    ma_f = [[True]  * q] if q > 0 else []

    if D == 0:
        # Deterministic seasonality: pairs 1..freq//2-1 + alter (Nyquist harmonic).
        max_pairs = max(freq // 2 - 1, 0)
        n_harm    = min(n_harmonics, max_pairs)
        itvs = []
        for k in range(1, n_harm + 1):
            itvs.append(fue.Intervention("cos", at=0, omega=[0.0], omega_free=[True], harmonic=float(k)))
            itvs.append(fue.Intervention("sin", at=0, omega=[0.0], omega_free=[True], harmonic=float(k)))
        # The Nyquist harmonic `alter`=(−1)ᵗ only exists for a seasonal period
        # s>=2; for annual series (freq=1) there is no seasonality, so adding it
        # injects a spurious deterministic biannual oscillation (see TODO.md).
        if freq >= 2:
            itvs.append(fue.Intervention("alter", at=0, omega=[0.0], omega_free=[True]))
        # Stationary stochastic seasonality on top of the deterministic harmonics:
        # a free annual AR/MA operator (no seasonal differencing). YW/HR-initialised.
        ar_s_val  = [ars_i] if P > 0 else []
        ar_sf_val = [[True] * P] if P > 0 else []
        ma_s_val  = [mas_i] if Q > 0 else []
        ma_sf_val = [[True] * Q] if Q > 0 else []
    else:
        itvs = []
        ar_s_val  = [ars_i] if P > 0 else []
        ar_sf_val = [[True] * P] if P > 0 else []
        ma_s_val  = [mas_i] if Q > 0 else []
        ma_sf_val = [[True] * Q]  if Q > 0 else []

    if extra_itvs:
        for at_0, form in extra_itvs:
            itvs.append(fue.Intervention(form, at=int(at_0), omega=[0.0], omega_free=[True]))

    return fue.Model(
        ts,
        d=d, D=D, boxlam=lam,
        ar=ar, ar_free=ar_f,
        ma=ma, ma_free=ma_f,
        ar_s=ar_s_val, ar_s_free=ar_sf_val if ar_sf_val else None,
        ma_s=ma_s_val, ma_s_free=ma_sf_val if ma_sf_val else None,
        interventions=itvs,
        ifadf=[0] * (freq // 2 + 1),
        mu=_mu_seed(ts, lam, d, D, estimate_mu), estimate_mu=estimate_mu,
    )


# ---------------------------------------------------------------------------
# Orchestration layer
# ---------------------------------------------------------------------------

@dataclass
class ModelSpec:
    """A confirmed model specification, ready to build + fit."""
    lam: float
    d: int
    D: int
    p: int
    q: int
    n_harmonics: int
    P: int = 0
    Q: int = 0
    interventions: list = field(default_factory=list)  # list of (at_0based, form)
    estimate_mu: bool = False


@dataclass
class FitResult:
    """Outcome of a single build→write→fit→diagnose step."""
    model: object        # fitted fue.Model
    diag: object         # art.diagnosis.DiagnosisResult
    spec: ModelSpec


@dataclass
class RoundResult:
    """One round of the autonomous outlier-addition loop."""
    round_num: int
    model: object        # fitted fue.Model for this round
    diag: object
    added: list          # interventions added for the NEXT round: (at_0, form)
    stop_reason: str     # "" | "clean" | "no_new"


@dataclass
class PipelineResult:
    """Full result of run_full(): decisions + every round + the final model."""
    lam: float
    d: int
    D: int
    p: int
    q: int
    n_harmonics: int
    decision: str
    boxcox_data: dict
    seasonality_data: dict
    orders_specs: list
    rounds: list
    final_model: object
    final_diag: object
    interventions: list  # final accumulated (at_0, form)


def build_and_fit(ts, spec: ModelSpec, output_path: str,
                  z_threshold: float) -> FitResult:
    """Build the .inp for *spec*, fit it, and diagnose the residuals.

    The single make→write→fit→diagnose step shared by the guided and
    autonomous paths.
    """
    from art.diagnosis import diagnose
    m = _make_model(ts, spec.lam, spec.d, spec.D, spec.p, spec.q,
                    spec.n_harmonics, extra_itvs=spec.interventions,
                    P=spec.P, Q=spec.Q, estimate_mu=spec.estimate_mu)
    _write_inp(ts, m, output_path)
    _, m_fit = _load_fitted(output_path)
    diag = diagnose(m_fit, z_threshold=z_threshold)
    return FitResult(model=m_fit, diag=diag, spec=spec)


def run_full(ts, output_path: str, max_rounds: int = 5,
             z_threshold: float | None = None,
             decision_policy=None) -> PipelineResult:
    """Box-Jenkins-Treadway pipeline driven by a decision policy.

    *decision_policy* is a policy.Policy instance:
      - DefaultPolicy() (the default) → fully autonomous: the heuristic decides.
      - ClaudePolicy(lam=…, d=…, …)  → guided: uses the analyst/Claude-confirmed
        choices, falling back to the heuristic for anything not provided.
    Both run the SAME engine; only who supplies each decision differs.

    Decides (λ, d, D, harmonics, p, q), then runs the outlier-addition loop
    until the diagnosis is clean, no new interventions are found, or max_rounds.

    Returns a PipelineResult; rendering (text log, figures) is the caller's
    responsibility — this function performs no I/O beyond writing output_path.
    """
    from art.describe import (describe_boxcox, describe_seasonality,
                              describe_unit_root)
    from art.model_detection import suggest_orders
    from art import policy as _policymod

    pol = decision_policy if decision_policy is not None else _policymod.DefaultPolicy()
    if z_threshold is None:
        z_threshold = _policymod.THRESHOLDS["outlier_autonomous"]

    # ── Decisions (evidence → policy) ─────────────────────────────────────
    bc   = describe_boxcox(ts)
    lam  = pol.decide_lambda(bc.data)
    seas = describe_seasonality(ts)
    D, decision, n_harmonics = pol.decide_seasonal_structure(seas.data, ts.freq)
    urt  = describe_unit_root(ts, lam=lam)
    d    = pol.decide_d(urt.data)
    specs = suggest_orders(ts, d=d, D=D, lam=lam, top_n=5)
    p, q = pol.decide_orders(specs)

    # ── Outlier-addition loop ─────────────────────────────────────────────
    extra_itvs: list = []
    rounds: list = []
    m_fit = None
    diag  = None
    for round_num in range(1, max_rounds + 1):
        spec = ModelSpec(lam=lam, d=d, D=D, p=p, q=q,
                         n_harmonics=n_harmonics, interventions=list(extra_itvs))
        fr = build_and_fit(ts, spec, output_path, z_threshold)
        m_fit, diag = fr.model, fr.diag

        if pol.should_stop(diag.clean, len(diag.extreme)):
            rounds.append(RoundResult(round_num, m_fit, diag, [], "clean"))
            break

        new_itvs = pol.decide_interventions(
            diag.extreme, [at for at, _ in extra_itvs])
        if not new_itvs:
            rounds.append(RoundResult(round_num, m_fit, diag, [], "no_new"))
            break

        extra_itvs.extend(new_itvs)
        rounds.append(RoundResult(round_num, m_fit, diag, new_itvs, ""))

    return PipelineResult(
        lam=lam, d=d, D=D, p=p, q=q, n_harmonics=n_harmonics, decision=decision,
        boxcox_data=bc.data, seasonality_data=seas.data, orders_specs=specs,
        rounds=rounds, final_model=m_fit, final_diag=diag,
        interventions=extra_itvs,
    )
