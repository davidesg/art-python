"""The card of implied dynamics — the engine's half of the domain procedure.

docs/DISENO-dominio-en-los-ordenes.md §4.3, decided 2026-09-30 (§10.bis): when
the identification leaves a GENUINE tie (BUG-0198's band), the engine computes
for each tied candidate what dynamics it implies, and the analyst (or the LLM)
reads it against the expectations declared in the `dominio` node BEFORE the
candidates were seen. The engine computes; it does not choose.

For each candidate, on the transformed series and conditioned on (d, D):

* ψ₀…ψ_H, the impulse response of the stationary series, and its minimum
  (an overshoot the process has to explain);
* the roots: real or complex, modulus, period (the cycles);
* the forecast weights π on the past LEVELS, from
  ∇^d ∇_s^D φ(B) Φ(Bˢ) / θ(B) Θ(Bˢ) — do they alternate?;
* Σψ, the long-run multiplier: the cumulated effect of a shock on the level;
* the reading of each MA paired with a difference (§5): 0 < θ < 1 is a
  stochastic mean (or seasonality) and 1 − θ how much of a shock moves it;
  θ < 0 alternates; θ near 1 is a question of d or D, not of orders (§10.4);
* between candidates, the largest difference of their forecasts to H = 2s in
  σ units: the MATERIALITY (§4.5; under 0.25 σ the choice is interpretative).

Convention: Box-Jenkins, (1 − φ₁B − …) wₜ = (1 − θ₁B − …) aₜ.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

MATERIALITY = 0.25          # σ; §10.3, the starting convention (calibrate with E1)
CANCEL = 0.90               # |θ| from here the MA nearly cancels its difference


def _poly(c, step=1):
    """1 − Σ cᵢ B^{i·step}, increasing powers."""
    c = np.asarray(c, float)
    out = np.zeros(len(c) * step + 1)
    out[0] = 1.0
    for i, v in enumerate(c):
        out[(i + 1) * step] = -v
    return out


def _roots(c, step=1):
    """[(modulus of the inverse root, period or None)] of 1 − Σ cᵢ B^{i·step}."""
    c = np.asarray(c, float)
    if c.size == 0:
        return []
    inv = np.roots(_poly(c, 1))          # inverse roots: z^k − c₁z^{k−1} − … = 0
    out = []
    for z in inv:
        mod = abs(z)
        ang = abs(np.angle(z))
        if step > 1:                     # a seasonal operator: its roots live in Bˢ
            per = None
        elif ang < 1e-8:
            per = None
        elif abs(ang - math.pi) < 1e-8:
            per = 2.0
        else:
            per = 2 * math.pi / ang
        out.append((float(mod), None if per is None else float(per)))
    # a complex pair once
    seen, uniq = set(), []
    for mod, per in out:
        key = (round(mod, 6), None if per is None else round(per, 6))
        if key not in seen:
            seen.add(key)
            uniq.append((mod, per))
    return uniq


@dataclass
class Card:
    label: str
    psi: np.ndarray
    psi_min: float
    ar_roots: list
    ma_roots: list
    pi: np.ndarray
    pi_alternates: bool
    pi_finite: bool
    long_run: float
    pairs: list = field(default_factory=list)     # (what, θ, reading)

    def cycles(self):
        return [(m, p) for m, p in self.ar_roots if p is not None]


def card(label, phi=(), theta=(), Phi=(), Theta=(), d=1, D=0, s=1, H=None):
    """The card of one candidate. H defaults to 2s (two years; 8 for s = 1)."""
    from scipy.signal import lfilter
    H = int(H or max(2 * s, 8))
    ar = np.convolve(_poly(phi), _poly(Phi, s))
    ma = np.convolve(_poly(theta), _poly(Theta, s))
    imp = np.zeros(H + 1)
    imp[0] = 1.0
    psi = lfilter(ma, ar, imp)
    # forecast weights on the past LEVELS: 1 − Σ πⱼ Bʲ = ∇^d ∇_s^D ar(B) / ma(B)
    full = ar.copy()
    for _ in range(d):
        full = np.convolve(full, [1.0, -1.0])
    for _ in range(D):
        full = np.convolve(full, _poly([1.0], s))
    n = max(H, 12) + 1
    x = np.zeros(n)
    x[:min(n, len(full))] = full[:n]
    pi_poly = lfilter([1.0], ma, x)                    # full(B) / ma(B)
    pi = -pi_poly[1:H + 1]
    # finite weights (no MA: they vanish after d + D·s + p + P·s lags) or an
    # infinite tail; an infinite tail that keeps changing sign ALTERNATES
    # without end — the forecast overshoots and corrects (§5.1, §7).
    finite = bool(np.allclose(ma[1:], 0.0))
    if finite:
        alternates = False
    else:
        tail = -pi_poly[len(full):n]
        tail = tail[np.abs(tail) > 1e-6]
        alternates = bool(tail.size >= 2 and np.mean(np.sign(tail[1:]) != np.sign(tail[:-1])) > 0.5)
    # long run: the cumulated effect of a shock on the level of the series in
    # its own differences — Σψ over a long horizon of the stationary part
    far = lfilter(ma, ar, np.r_[1.0, np.zeros(400)])
    pairs = []
    # a real positive MA root near 1 cancels a regular difference, whatever the
    # MA's order: (1 − rB) with r ≈ 1 against ∇ = (1 − B) — the question is
    # d, not the orders (§5.3, §10.4). The muskrat's ARMA(1,2): r = 0.99.
    cancel = []
    if d >= 1 and len(theta):
        for z in np.roots(_poly(theta)):
            if abs(z.imag) < 1e-8 and z.real >= CANCEL:
                cancel.append(float(z.real))
    for r in cancel:
        pairs.append(("∇ con raíz MA", r, _reading(r, "media")))
    for i, th in enumerate(np.asarray(theta, float)[:1]):
        if d >= 1 and not cancel and len(theta) == 1:
            pairs.append(("∇ con θ₁", float(th), _reading(float(th), "media")))
    for i, th in enumerate(np.asarray(Theta, float)[:1]):
        if D >= 1:
            pairs.append(("∇ₛ con Θ₁", float(th), _reading(float(th), "estacionalidad")))
    return Card(label, psi, float(psi[1:].min()) if H else 0.0,
                _roots(phi) + _roots(Phi, s), _roots(theta) + _roots(Theta, s),
                pi, alternates, finite, float(far.sum()), pairs)


def _reading(th, what):
    if th >= CANCEL:
        return (f"θ = {th:.2f} ≥ {CANCEL}: casi cancela la diferencia — la pregunta es "
                f"de {'d' if what == 'media' else 'D'}, no de órdenes: vuelve a ese nodo "
                "con esta ficha (DCD / MEG)")
    if th > 0:
        return (f"{what} estocástica: 1 − θ = {1 - th:.2f} de cada choque la mueve de "
                "forma permanente")
    if th < 0:
        return "θ < 0: los pesos de previsión alternan — sobrepasa y corrige"
    return "θ = 0"


def forecast_gap(w, fits, d, D, s, H=None):
    """Largest |ŷ_A − ŷ_B| on the transformed LEVEL, h = 1..H, in σ units,
    between the first two fits [(phi, theta, Phi, Theta)], each filtered on the
    stationary series w (conditional). σ: the mean residual s.d."""
    from scipy.signal import lfilter
    H = int(H or max(2 * s, 8))
    w = np.asarray(w, float)
    mu = w.mean()
    paths, sds = [], []
    for phi, theta, Phi, Theta in fits[:2]:
        ar = np.convolve(_poly(phi), _poly(Phi, s))
        ma = np.convolve(_poly(theta), _poly(Theta, s))
        e = lfilter(ar, ma, w - mu)
        sds.append(float(np.std(e[len(ar):])))
        x = list(w - mu)
        ee = list(e)
        fut = []
        for _h in range(H):
            v = -sum(ar[k] * x[-k] for k in range(1, len(ar))) \
                + sum(ma[k] * ee[-k] for k in range(1, len(ma)))
            x.append(v)
            ee.append(0.0)
            fut.append(v + mu)
        # back to the transformed level: cumulate the differences
        lev = np.asarray(fut)
        for _ in range(d):
            lev = np.cumsum(lev)
        if D:
            # a seasonal sum: y_t = y_{t−s} + w_t, from zero (gaps compare alike)
            acc = np.zeros(H)
            for t in range(H):
                acc[t] = lev[t] + (acc[t - s] if t >= s else 0.0)
            lev = acc
        paths.append(lev)
    if len(paths) < 2:
        return None
    sig = max(np.mean(sds), 1e-12)
    return float(np.max(np.abs(paths[0] - paths[1])) / sig)


def render(cards, gap=None):
    """The card as markdown, one column per candidate (fixed format)."""
    head = "| | " + " | ".join(c.label for c in cards) + " |"
    rows = [head, "|---|" + "---|" * len(cards)]

    def fmt(v):
        return ", ".join(f"{x:.2f}" for x in v)

    rows.append("| ψ₁, ψ₂, ψ₃ | " + " | ".join(fmt(c.psi[1:4]) for c in cards) + " |")
    rows.append("| mínimo de ψ (sobreoscilación) | " + " | ".join(f"{c.psi_min:.2f}" for c in cards) + " |")
    rows.append("| raíces AR (módulo, período) | " + " | ".join(
        "; ".join(f"{m:.2f}" + (f", {p:.1f}" if p else ", real") for m, p in c.ar_roots) or "—"
        for c in cards) + " |")
    rows.append("| raíces MA (módulo, período) | " + " | ".join(
        "; ".join(f"{m:.2f}" + (f", {p:.1f}" if p else ", real") for m, p in c.ma_roots) or "—"
        for c in cards) + " |")
    def weights(c):
        tag = ("finitos" if c.pi_finite else
               "infinitos, **alternan sin fin**" if c.pi_alternates else "infinitos")
        return fmt(c.pi[:5]) + f" — {tag}"
    rows.append("| pesos de previsión π₁…π₅ (niveles) | " + " | ".join(
        weights(c) for c in cards) + " |")
    rows.append("| multiplicador de largo plazo Σψ | " + " | ".join(f"{c.long_run:.2f}" for c in cards) + " |")
    pair_rows = [c for c in cards if c.pairs]
    out = rows
    if pair_rows:
        out += ["", "**El par (∇, MA)** (§5 del estudio):"]
        for c in pair_rows:
            for what, th, reading in c.pairs:
                out.append(f"- {c.label}: {what} = {th:.2f} → {reading}")
    if gap is not None:
        interp = gap < MATERIALITY
        out += ["", f"**Materialidad:** la mayor diferencia de previsión entre los dos "
                    f"primeros a H = 2s es **{gap:.2f} σ**"
                    + (f" (< {MATERIALITY} σ): la elección es **interpretativa** — casi no "
                       "cambia la previsión, sólo la lectura." if interp else
                       f" (≥ {MATERIALITY} σ): la elección **cambia la previsión**.")]
    return "\n".join(out)
