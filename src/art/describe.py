"""
LLM-friendly descriptions of ART analysis results.

Each function runs the corresponding ART computation and returns a
Description with structured markdown text, an optional embedded figure
(base64 PNG), and a recommendation for the analyst's next decision.

These are the building blocks for the MCP server and for any LLM
integration — they are independent of the transport protocol.
"""

from __future__ import annotations

import base64
import io
import math
from dataclasses import dataclass, field

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import art
from .identification import (
    boxcox_selection, plot_boxcox_selection,
    identification_listing, save_identification_report,
    apply_differences, boxcox_transform, transform_label,
    _listing_figure,
)
from .seasonal_detection import detect_seasonality, plot_seasonality
from .model_detection import suggest_orders
from .diagnosis import diagnose, plot_diagnosis
from .formal_tests import dcd, dcd_f, rv, meg, shin_fuller
from .interventions import diagnose_interventions
from .full_report import _meg_suitable, _try


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class Description:
    """
    LLM-consumable result from an ART analysis step.

    Attributes
    ----------
    summary : str
        Markdown text. Key numbers in **bold**. Concise — 3-10 lines.
    figure_b64 : str | None
        Base64-encoded PNG figure, or None if not applicable.
    recommendation : str
        What the analyst should decide or do next.
    data : dict
        Structured data for programmatic use (key numbers, flags).
    """
    summary: str
    figure_b64: str | None
    recommendation: str
    data: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Box-Cox
# ---------------------------------------------------------------------------

def describe_boxcox(ts) -> Description:
    """Compute Box-Cox selection and recommend lambda."""
    import numpy as np
    result = boxcox_selection(ts)
    fig    = plot_boxcox_selection(ts)
    b64    = _fig_b64(fig)
    plt.close(fig)

    s = result.name or ts.name or "series"
    n = ts.nobs

    def _abscorr(mdt):
        x, y = np.array(mdt.means_std), np.array(mdt.stds_std)
        if x.std() < 1e-10 or y.std() < 1e-10:
            return 0.0
        return abs(float(np.corrcoef(x, y)[0, 1]))

    corr_raw = _abscorr(result.mdt_raw)
    corr_log = _abscorr(result.mdt_log)
    gap      = corr_raw - corr_log          # >0 → log mejor
    ambiguous = abs(gap) < 0.10
    prefers_log = corr_log < corr_raw
    rec_lam = 0.0 if prefers_log else 1.0
    rec_str = "log (λ=0)" if prefers_log else "identidad (λ=1)"

    lines = [
        f"## Box-Cox — {s}  (n={n})",
        f"- Correlación media-std con λ=1 (original): **{corr_raw:.3f}**",
        f"- Correlación media-std con λ=0 (log):      **{corr_log:.3f}**",
        f"- Recomendación: **{rec_str}**",
    ]

    if ambiguous:
        lines += [
            "",
            f"⚠ **Decisión ambigua** — la diferencia entre escalas es pequeña "
            f"(Δcorr={abs(gap):.3f} < 0.10). Ambas transformaciones son razonables.",
            "- λ=0 (log) es preferible si la serie es un índice de precios o magnitud "
            "multiplicativa, porque estabiliza la varianza a largo plazo.",
            "- λ=1 (original) es preferible si la variabilidad no depende del nivel "
            "o si se necesita interpretabilidad directa.",
        ]
    elif prefers_log:
        lines += [
            "",
            f"La escala log reduce la correlación media-std de {corr_raw:.3f} a "
            f"{corr_log:.3f}: la varianza es más homogénea entre períodos.",
            "Esto es habitual en índices de precios y series multiplicativas.",
        ]
    else:
        lines += [
            "",
            f"La escala original ya tiene varianza homogénea (corr={corr_raw:.3f}). "
            "La transformación log no mejora la estabilidad.",
        ]

    if ambiguous:
        rec = (
            f"Decisión ambigua (Δ={abs(gap):.3f}). "
            f"Si la serie es un índice de precios, confirma λ=0.0 (log) por convención. "
            f"Si no, puedes usar λ=1.0 (original). "
            f"Siguiente paso: detección de estacionalidad."
        )
    else:
        rec = (
            f"Confirma λ={rec_lam}. "
            f"Siguiente paso: detección de estacionalidad."
        )

    return Description(
        summary="\n".join(lines),
        figure_b64=b64,
        recommendation=rec,
        data={
            "prefers_log": prefers_log,
            "recommended_lambda": rec_lam,
            "corr_raw": corr_raw,
            "corr_log": corr_log,
            "ambiguous": ambiguous,
            "gap": gap,
        },
    )


# ---------------------------------------------------------------------------
# Seasonal detection
# ---------------------------------------------------------------------------

def describe_seasonality(ts) -> Description:
    """Run HAC F-test for seasonality and recommend d, D and decision A/B1/B2."""
    import numpy as np
    from statsmodels.tsa.stattools import adfuller, kpss

    result = detect_seasonality(ts)
    fig    = plot_seasonality(result)
    b64    = _fig_b64(fig)
    plt.close(fig)

    s     = ts.name or "series"
    det   = result.seasonal_detected
    freqs = result.freq_results or []

    # ADF and KPSS on the log-differenced series (d=1) to support d recommendation
    try:
        import fue as _fue
        y = np.array(ts.data, dtype=float)
        if any(v <= 0 for v in y):
            y_diff = np.diff(y)
        else:
            y_diff = np.diff(np.log(y))
        adf_stat, adf_p, *_ = adfuller(y_diff, autolag="AIC")
        kpss_stat, kpss_p, *_ = kpss(y_diff, regression="c", nlags="auto")
        adf_ok   = adf_p  < 0.05   # rejects unit root → stationary
        kpss_ok  = kpss_p > 0.05   # does not reject stationarity
        d_ok     = adf_ok and kpss_ok
        unit_root_text = (
            f"ADF p={adf_p:.4f} ({'rechaza raíz unitaria ✓' if adf_ok else 'no rechaza ✗'}), "
            f"KPSS p={kpss_p:.4f} ({'estacionaria ✓' if kpss_ok else 'no estacionaria ✗'})"
        )
    except Exception:
        d_ok = True
        unit_root_text = "(tests de raíz unitaria no disponibles)"

    sig_freqs = [
        f"f={fr.freq_idx} (χ²={fr.wald_stat:.1f}, p={fr.p_value:.4f})"
        for fr in freqs if fr.p_value < 0.05
    ]

    # Decision A / B1 / B2
    if not det:
        decision = "A"
    else:
        decision = "B1"   # start with D=0 + harmonics; MEG will clarify

    lines = [
        f"## Detección de estacionalidad — {s}",
        f"- F-test HAC conjunto: **F={result.f_stat:.2f}**, p={result.p_value:.4f}",
        f"- Estacionalidad detectada: **{'Sí' if det else 'No'}**",
    ]
    if sig_freqs:
        lines.append(f"- Frecuencias significativas: {', '.join(sig_freqs)}")
    else:
        lines.append("- Ninguna frecuencia armónica significativa.")

    lines += ["", f"**Tests raíz unitaria sobre ∇log(y):** {unit_root_text}"]

    if decision == "A":
        lines += [
            "",
            "**Decisión A — sin estacionalidad.**",
            "- d=1 (o d=2 si los tests lo sugieren), D=0, sin armónicos cos/sin.",
            "- La serie diferenciada es estacionaria: el modelo ARMA sobre ∇y es apropiado.",
        ]
    else:
        lines += [
            "",
            "**Decisión B1 — estacionalidad determinista (punto de partida recomendado).**",
            "- d=1, D=0, con armónicos cos/sin para cada frecuencia significativa.",
            "- Los armónicos absorben el patrón estacional fijo (igual cada año).",
            "- MEG (etapa 3, tras estimar) determinará si alguna frecuencia es",
            "  estocástica y conviene pasar a **Decisión B2** (D=1 para esa frecuencia).",
            "",
            "**Decisión B2** (alternativa, si MEG detecta estacionalidad estocástica):",
            "- d=1, D=1 para la frecuencia confirmada por MEG.",
            "- Sustituye los armónicos de esa frecuencia por la diferencia estacional.",
            "- Solo adoptar B2 tras confirmar MEG — no anticipar.",
        ]

    if not d_ok:
        lines += [
            "",
            f"⚠ Los tests de raíz unitaria sugieren que ∇log(y) puede no ser "
            "estacionaria. Considera d=2.",
        ]

    rec = (
        f"Decisión {decision}. "
        + (
            "Confirma d=1, D=0 con armónicos. MEG validará si alguna frecuencia "
            "requiere D=1 más adelante."
            if decision == "B1"
            else "Confirma d=1, D=0, sin armónicos."
        )
        + " Siguiente paso: listado de identificación (p, q)."
    )

    return Description(
        summary="\n".join(lines),
        figure_b64=b64,
        recommendation=rec,
        data={
            "seasonal_detected": det,
            "decision": decision,
            "f_stat": result.f_stat,
            "p_value": result.p_value,
            "recommended_d": 1,
            "recommended_D": 0,
            "d_stationary": d_ok,
            "significant_frequencies": [fr.freq_idx for fr in freqs if fr.p_value < 0.05],
        },
    )


# ---------------------------------------------------------------------------
# Identification (ACF/PACF + order suggestions)
# ---------------------------------------------------------------------------

def describe_identification(ts, d: int, D: int, lam: float = 0.0) -> Description:
    """Generate identification listing and suggest ARMA orders with per-candidate reasoning."""
    import numpy as np
    specs = suggest_orders(ts, d=d, D=D, lam=lam, top_n=5)

    s = ts.name or "series"

    def _pattern_label(sp):
        """One-line interpretation of the ACF/PACF pattern for a ModelSpec."""
        if sp.p == 0 and sp.q == 0:
            return "sin estructura ARMA — ruido blanco tras diferenciación"
        if sp.p == 0 and sp.q >= 1:
            return (f"ACF se corta en lag {sp.q}, PACF decrece → "
                    f"proceso MA({sp.q}) puro")
        if sp.q == 0 and sp.p >= 1:
            return (f"PACF se corta en lag {sp.p}, ACF decrece → "
                    f"proceso AR({sp.p}) puro")
        return (f"ambas ACF/PACF decrecen sin corte claro → "
                f"proceso ARMA({sp.p},{sp.q}) mixto")

    lines = [
        f"## Identificación — {s}  (d={d}, D={D}, λ={lam})",
        "",
        "**Candidatos ARMA** (similitud ACF/PACF teórica vs empírica):",
    ]
    for i, sp in enumerate(specs, 1):
        marker = "→" if i == 1 else "  "
        label  = _pattern_label(sp)
        lines.append(
            f"{marker} {i}. ARIMA({sp.p},{sp.d},{sp.q})({sp.P},{sp.D},{sp.Q})_{sp.s}"
            f"  sim={sp.similarity:.3f}  —  {label}"
        )

    # Ambiguity: top-2 gap < 0.05
    ambiguous = len(specs) >= 2 and (specs[0].similarity - specs[1].similarity) < 0.05
    top_gap   = (specs[0].similarity - specs[1].similarity) if len(specs) >= 2 else 1.0

    if ambiguous:
        lines += [
            "",
            f"⚠ **Decisión ambigua** — los dos primeros candidatos difieren en sólo "
            f"{top_gap:.3f} de similitud. El patrón ACF/PACF no discrimina claramente "
            f"entre ellos.",
            "  Recomendación: estimar ambos y comparar AIC/BIC y calidad de residuos.",
        ]
    elif specs:
        lines += ["", f"El patrón favorece claramente el modelo 1 (gap={top_gap:.3f})."]

    rec_p = specs[0].p if specs else 0
    rec_q = specs[0].q if specs else 1

    if ambiguous:
        rec = (
            f"Decisión ambigua entre ARIMA({specs[0].p},{d},{specs[0].q}) y "
            f"ARIMA({specs[1].p},{d},{specs[1].q}). "
            f"Estima ambos y elige por AIC/BIC y diagnosis de residuos. "
            f"Recuerda añadir armónicos cos/sin si D=0."
        )
    else:
        rec = (
            f"Confirma ARIMA({rec_p},{d},{rec_q}) como punto de partida. "
            f"Revisa la figura ACF/PACF antes de estimar. "
            f"Recuerda añadir armónicos cos/sin si D=0."
        )

    # ACF/PACF figure for the chosen (d, D): show all differentiation levels up to (d, D)
    # so the analyst can see why d was chosen and what the clean series looks like.
    b64_ident = None
    try:
        listing = identification_listing(ts, lam=lam, max_d=d, max_D=D)
        start   = getattr(ts, "start", (1, 1))
        if D == 0:
            panels = listing.panels                  # d=0, 1, ..., d_chosen (all D=0)
        else:
            # panels order: [D=0, d=0..d_chosen], [D=1, d=0..d_chosen]
            # We show only the D=1 panels (the analyst has already decided D=1)
            n_per_D = d + 1
            panels  = listing.panels[n_per_D:]      # D=1 panels
        fig = _listing_figure(listing, panels, start)
        b64_ident = _fig_b64(fig)
        plt.close(fig)
    except Exception:
        b64_ident = None

    return Description(
        summary="\n".join(lines),
        figure_b64=b64_ident,
        recommendation=rec,
        data={
            "d": d, "D": D, "lam": lam,
            "ambiguous": ambiguous,
            "top_gap": top_gap,
            "suggestions": [
                {"p": sp.p, "q": sp.q, "P": sp.P, "Q": sp.Q,
                 "similarity": sp.similarity, "pattern": _pattern_label(sp)}
                for sp in specs
            ],
        },
    )


# ---------------------------------------------------------------------------
# Model equation (Bloque O)
# ---------------------------------------------------------------------------

def model_equation(ts, model) -> str:
    """
    Render the estimated model as two polynomial-operator equations (Unicode).

    Two-equation form (B-J-T thesis notation):
      (1) Level:  [transform] yₜ = Dₜ + Nₜ
      (2) Noise:  ∇ᵈ∇ₛᴰ [φ(B)] [Nₜ − μ] = [θ(B)] aₜ

    Each estimated parameter shows SE aligned below it (\\est{}{} equivalent).
    Returns plain text ready for Claude Code chat (monospace rendering).
    """
    import numpy as np
    from math import gcd

    params   = list(model.params)
    ses      = list(model.std_errors)
    n_params = len(params)

    class _PI:
        def __init__(self):
            self.i = 0
        def pop(self):
            if self.i >= n_params:
                return 0.0, 0.0
            v, se = params[self.i], ses[self.i]
            self.i += 1
            return v, se

    pi = _PI()

    freq    = ts.freq
    d       = model.d
    D       = model.D
    lam     = model.boxlam
    ts_name = (ts.name or "y").strip()

    # ── formatting helpers ────────────────────────────────────────────────

    def _fv(v: float) -> str:
        a = abs(v)
        if a == 0:
            return "0"
        if a < 0.001:
            return f"{v:.6f}"
        if a < 0.01:
            return f"{v:.5f}"
        if a < 0.1:
            return f"{v:.4f}"
        if a < 10:
            return f"{v:.4f}"
        return f"{v:.3f}"

    def _fse(se: float) -> str:
        a = abs(se)
        if a == 0:
            return ""
        if a < 0.001:
            return f"({se:.6f})"
        if a < 0.01:
            return f"({se:.5f})"
        if a < 0.1:
            return f"({se:.4f})"
        return f"({se:.4f})"

    def _sign_det(v: float) -> str:
        """Sign for deterministic terms: raw coefficient sign."""
        return "+" if v >= 0 else "−"

    def _sign_arma(v: float) -> str:
        """Sign for ARMA terms: fue stores value to subtract, so positive→−, negative→+."""
        return "−" if v >= 0 else "+"

    def _sup(n: int) -> str:
        sup_map = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
        return str(n).translate(sup_map)

    def _harm_label(ttype: str, harmonic: float) -> str:
        h = int(round(harmonic))
        if ttype == "alter":
            return "(−1)ᵗ"
        half = freq // 2
        g    = gcd(h, half)
        num, den = h // g, half // g
        if den == 1:
            frac = "π" if num == 1 else f"{num}π"
        else:
            frac = f"π/{den}" if num == 1 else f"{num}π/{den}"
        fn = "cos" if ttype == "cos" else "sin"
        return f"{fn}({frac}·t)"

    def _diff_str() -> str:
        parts = []
        if d == 1:
            parts.append("∇")
        elif d > 1:
            parts.append(f"∇{_sup(d)}")
        if D == 1:
            parts.append(f"∇_{freq}")
        elif D > 1:
            parts.append(f"∇_{freq}{_sup(D)}")
        return "".join(parts)

    def _transform_label() -> str:
        if lam == 0.0:
            return f"ln {ts_name}ₜ"
        if lam == 0.5:
            return f"√{ts_name}ₜ"
        if lam == 1.0:
            return f"{ts_name}ₜ"
        return f"{ts_name}ₜ^(λ={lam:.2f})"

    def _obs_to_date(at_0based: int) -> str:
        start  = list(ts.start)
        by, bp = start[0], (start[1] if freq > 1 else 1)
        off    = bp - 1 + at_0based
        p, y   = off % freq + 1, by + off // freq
        if freq == 1:
            return str(y)
        if freq == 4:
            return f"Q{p}/{y}"
        return f"{p}/{y}"

    # ── Two-line polynomial builder ───────────────────────────────────────
    # Builds two parallel strings: value line + SE line
    # SE values are placed starting at the column where the coefficient digit begins

    class _TwoLine:
        def __init__(self):
            self.v = []   # chars for value line
            self.s = []   # chars for SE line (may be longer than v)

        def add(self, text: str, se: str = ""):
            """
            Append text to value line.
            If se given, write it into se line starting at the current column
            (where this text begins), without padding the value line.
            """
            col = len(self.v)   # current position in value line
            self.v += list(text)
            # Ensure s has at least col+len(text) spaces
            while len(self.s) < col + len(text):
                self.s.append(" ")
            if se:
                for i, c in enumerate(se):
                    pos = col + i
                    while pos >= len(self.s):
                        self.s.append(" ")
                    self.s[pos] = c

        def val(self) -> str:
            return "".join(self.v).rstrip()

        def se_line(self) -> str:
            s = "".join(self.s).rstrip()
            return s if s.strip() else ""

    def _fmt_poly(factor, freel, lag_mult: int = 1) -> tuple[str, str]:
        """
        Format one polynomial factor (1 ± v₁·B ± v₂·B² ...).
        ARMA sign convention: positive stored value → subtract (−).
        Returns (val_line, se_line).
        """
        tl = _TwoLine()
        tl.add("(1")
        for lag_idx, (v0, free) in enumerate(zip(factor, freel)):
            lag  = (lag_idx + 1) * lag_mult
            bpow = "·B" if lag == 1 else f"·B{_sup(lag)}"
            if free:
                v, se = pi.pop()
            else:
                v, se = v0, 0.0
            sign  = _sign_arma(v)
            v_str = _fv(abs(v))
            tl.add(f" {sign} ")          # " − " separator (no SE)
            tl.add(v_str, _fse(se))      # coefficient with SE below it
            tl.add(bpow)                 # B^k (no SE)
        tl.add(")")
        return tl.val(), tl.se_line()

    # ── Part 1: Deterministic component Dₜ ───────────────────────────────

    det_rows: list[tuple[str, str]] = []   # (val_line, se_line)

    # Collect harmonics to pair cos+sin on one row
    harm_buf: dict[int, dict] = {}   # h_idx → {type: (v, se, free)}

    for itv in (model.interventions or []):
        t    = itv.type
        om   = list(itv.omega)     if itv.omega     else []
        om_f = (list(itv.omega_free)
                if (hasattr(itv, "omega_free") and itv.omega_free)
                else [True] * len(om))
        h    = int(round(getattr(itv, "harmonic", 1)))

        if t in ("cos", "sin", "alter"):
            if om_f[0]:
                v, se = pi.pop()
            else:
                v, se = (om[0] if om else 0.0), 0.0
            harm_buf.setdefault(h, {})[t] = (v, se, om_f[0])

        elif t in ("step", "pulse", "impulse", "ramp", "compimp"):
            date_str = _obs_to_date(itv.at)
            xi_sup   = {"step": "S", "pulse": "I", "impulse": "I",
                        "ramp": "R", "compimp": "CI"}.get(t, "?")
            xi_str   = f"ξₜ^{{{xi_sup},{date_str}}}"

            if len(om) == 1:
                v, se = (pi.pop() if om_f[0] else (om[0], 0.0))
                tl = _TwoLine()
                tl.add(f"  {_sign_det(v)} ")
                tl.add(_fv(abs(v)), _fse(se) if om_f[0] else "")
                tl.add(f" {xi_str}")
                det_rows.append((tl.val(), tl.se_line()))
            else:
                tl = _TwoLine()
                tl.add("  + (")
                for i, (v0, free) in enumerate(zip(om, om_f)):
                    v, se = (pi.pop() if free else (v0, 0.0))
                    if i == 0:
                        tl.add(_fv(v), _fse(se) if free else "")
                    else:
                        bpow = "·B" if i == 1 else f"·B{_sup(i)}"
                        tl.add(f"  {_sign_det(v)} ")
                        tl.add(_fv(abs(v)), _fse(se) if free else "")
                        tl.add(bpow)
                tl.add(f") {xi_str}")
                det_rows.append((tl.val(), tl.se_line()))

    # Flush harmonics in sorted order (pairs cos+sin on one line)
    for h_idx in sorted(harm_buf.keys()):
        grp = harm_buf[h_idx]
        tl  = _TwoLine()
        first = True
        for ttype in ("cos", "sin", "alter"):
            if ttype not in grp:
                continue
            v, se, free = grp[ttype]
            label = _harm_label(ttype, h_idx)
            if not first:
                tl.add("   ")
            tl.add(f"  {_sign_det(v)} ")
            tl.add(_fv(abs(v)), _fse(se) if free else "")
            tl.add(f" {label}")
            first = False
        det_rows.append((tl.val(), tl.se_line()))

    # ── Part 2: Noise model ───────────────────────────────────────────────

    left_blocks:  list[tuple[str, str]] = []
    right_blocks: list[tuple[str, str]] = []

    def _add_arma_blocks(target, factors, free_lists, lag_mult=1):
        if not factors:
            return
        frees = (free_lists if free_lists is not None
                 else [[True] * len(f) for f in factors])
        for factor, freel in zip(factors, frees):
            target.append(_fmt_poly(factor, freel, lag_mult))

    def _add_fixed_freq(target, ff_list):
        """AR_f / MA_f fixed-frequency quadratic factors."""
        for ff in (ff_list or []):
            f_idx   = int(round(ff.freq))
            tc_val, tc_lbl = _two_cos(f_idx, freq)

            # Format the B term:  " − √3·B" or " + √3·B" (when tc<0) or "" (when tc≈0)
            if abs(tc_val) < 1e-9:
                b_term = ""                          # f=3 monthly: (1 + coef·B²)
            elif tc_val > 0:
                lbl_b  = "B" if tc_lbl == "1" else f"{tc_lbl}·B"
                b_term = f" − {lbl_b}"              # f=1,2: (1 − √3·B + ...)
            else:
                lbl_b  = "B" if tc_lbl == "1" else f"{tc_lbl}·B"
                b_term = f" + {lbl_b}"              # f=4,5: (1 + B + ...)

            # Free coefficient: always show numeric value (never hide near-unit-root)
            if ff.free:
                v, se = pi.pop()
                c_str = f"{_fv(abs(v))}·B²"
                f_v   = f"(1{b_term} + {c_str})_f={f_idx}"
                se_offset = len(f"(1{b_term} + ")
                f_s   = " " * se_offset + _fse(se)
            else:
                v_c   = float(getattr(ff, "coef", 1.0))
                c_str = "B²" if abs(abs(v_c) - 1.0) < 0.001 else f"{_fv(abs(v_c))}·B²"
                f_v   = f"(1{b_term} + {c_str})_f={f_idx}"
                f_s   = ""
            target.append((f_v, f_s))

    def _add_ifadf_blocks(target, ifadf_list):
        """Add fixed individual factors of ∇_freq (ifadf) to LHS. All fixed, no SE."""
        if not ifadf_list:
            return
        nyquist = freq // 2
        for i, flag in enumerate(ifadf_list):
            if not flag:
                continue
            if i == 0:
                target.append(("(1 − B)", ""))
            elif i == nyquist:
                target.append((f"(1 + B)_f={i}", ""))
            else:
                tc_val, tc_lbl = _two_cos(i, freq)
                if abs(tc_val) < 1e-9:
                    target.append((f"(1 + B²)_f={i}", ""))
                elif tc_val > 0:
                    lbl_b = "B" if tc_lbl == "1" else f"{tc_lbl}·B"
                    target.append((f"(1 − {lbl_b} + B²)_f={i}", ""))
                else:
                    lbl_b = "B" if tc_lbl == "1" else f"{tc_lbl}·B"
                    target.append((f"(1 + {lbl_b} + B²)_f={i}", ""))

    _add_arma_blocks(left_blocks,  model.ar or [],  model.ar_free)
    if model.ar_s:
        ar_sf = model.ar_s_free if hasattr(model, "ar_s_free") else None
        _add_arma_blocks(left_blocks, model.ar_s, ar_sf, lag_mult=freq)
    _add_fixed_freq(left_blocks, model.ar_f)
    if getattr(model, "ifadf", None):
        _add_ifadf_blocks(left_blocks, model.ifadf)

    _add_arma_blocks(right_blocks, model.ma or [],  model.ma_free)
    if model.ma_s:
        ma_sf = model.ma_s_free if hasattr(model, "ma_s_free") else None
        _add_arma_blocks(right_blocks, model.ma_s, ma_sf, lag_mult=freq)
    _add_fixed_freq(right_blocks, model.ma_f)

    # ── mu: show value on eq line, SE below (like other params) ──────────
    mu_val_str = ""
    mu_se_str  = ""
    mu_sign    = ""
    mu_pfx_len = 0   # chars before mu value within nt_label: "(Nₜ − " = 6
    if model.estimate_mu:
        v_mu, se_mu = pi.pop()
        mu_sign    = "−" if v_mu >= 0 else "+"
        mu_val_str = _fv(abs(v_mu))
        mu_se_str  = _fse(se_mu)
        mu_pfx_len = len(f"(Nₜ {mu_sign} ")  # always 6

    diff_s  = _diff_str()
    has_ar  = bool(left_blocks)

    if mu_val_str:
        nt_label = f"(Nₜ {mu_sign} {mu_val_str})"
    elif has_ar:
        nt_label = "(Nₜ)"
    else:
        nt_label = "Nₜ"

    # Each item is (val_str, se_str) where se_str is pre-padded relative to
    # the block's own start (matching _TwoLine.add semantics).
    nt_se     = (" " * mu_pfx_len + mu_se_str) if (mu_se_str and mu_pfx_len) else ""
    lhs_items = []
    if diff_s:
        lhs_items.append((diff_s, ""))
    lhs_items.extend(left_blocks)
    lhs_items.append((nt_label, nt_se))

    rhs_items = list(right_blocks) + [("aₜ", "")]

    # ── Noise equation: line-wrap if needed, align continuations at "=" ──
    indent_noise = "  (2)  "
    lhs_str      = " ".join(v for v, _ in lhs_items)
    lhs_only     = f"{indent_noise}{lhs_str}"
    LINE_WRAP    = 72

    # When the LHS itself is too wide, put "= " on a new line rather than
    # extending cont_prefix to an unusable length.
    if len(lhs_only) + 3 <= LINE_WRAP:
        first_prefix = lhs_only + " = "
        cont_prefix  = " " * len(first_prefix)
        separate_lhs = False
    else:
        rhs_eq_prefix = " " * (len(indent_noise) + 4) + "= "
        cont_prefix   = " " * len(rhs_eq_prefix)
        separate_lhs  = True

    def _make_rhs_groups(start_len: int) -> list:
        groups: list = []
        cur_group: list = []
        cur_len = start_len
        for item in rhs_items:
            extra = (1 if cur_group else 0) + len(item[0])
            if cur_group and cur_len + extra > LINE_WRAP:
                groups.append(cur_group)
                cur_group = [item]
                cur_len = len(cont_prefix) + len(item[0])
            else:
                cur_group.append(item)
                cur_len += extra
        if cur_group:
            groups.append(cur_group)
        return groups

    single_rhs_len = sum(
        (1 if i > 0 else 0) + len(v) for i, (v, _) in enumerate(rhs_items)
    )

    if not separate_lhs and len(first_prefix) + single_rhs_len <= LINE_WRAP:
        rhs_groups = [rhs_items]
    elif separate_lhs:
        rhs_groups = _make_rhs_groups(len(rhs_eq_prefix))
    else:
        rhs_groups = _make_rhs_groups(len(first_prefix))

    noise_vis_lines: list[tuple[str, str]] = []
    if separate_lhs:
        # LHS on its own line (no SE — ifadf factors are all fixed)
        tl = _TwoLine()
        tl.add(indent_noise)
        for i, (v, s) in enumerate(lhs_items):
            if i > 0:
                tl.add(" ")
            tl.add(v, s)
        noise_vis_lines.append((tl.val(), tl.se_line()))
        # RHS lines, starting with "    = "
        for g_idx, group in enumerate(rhs_groups):
            tl = _TwoLine()
            tl.add(rhs_eq_prefix if g_idx == 0 else cont_prefix)
            for i, (v, s) in enumerate(group):
                if i > 0:
                    tl.add(" ")
                tl.add(v, s)
            noise_vis_lines.append((tl.val(), tl.se_line()))
    else:
        for g_idx, group in enumerate(rhs_groups):
            tl = _TwoLine()
            if g_idx == 0:
                tl.add(indent_noise)
                for i, (v, s) in enumerate(lhs_items):
                    if i > 0:
                        tl.add(" ")
                    tl.add(v, s)
                tl.add(" = ")
            else:
                tl.add(cont_prefix)
            for i, (v, s) in enumerate(group):
                if i > 0:
                    tl.add(" ")
                tl.add(v, s)
            noise_vis_lines.append((tl.val(), tl.se_line()))

    # Stats
    stat_line = ""
    try:
        sigma_raw = float(np.std(model.residuals.data))
        loglik    = float(model.loglik)
        aic_val   = float(model.aic)
        bic_val   = float(model.bic)
        refactor  = float(getattr(model, "refactor", 1.0))

        # fue scales residuals by `refactor` before estimation.
        # If refactor>=10 (e.g. ×100) the residuals.data are already in pct units.
        # For log models (lam=0) with no scaling, convert to % for display.
        if refactor >= 10:
            sigma_disp = f"{sigma_raw:.4f}%"
        elif lam == 0.0 and sigma_raw < 0.5:
            sigma_disp = f"{sigma_raw:.5f}  ({sigma_raw*100:.3f}%)"
        else:
            sigma_disp = f"{sigma_raw:.5f}"

        stat_line = (f"  σ̂ₐ = {sigma_disp}"
                     f"   |   ℓ = {loglik:.2f}"
                     f"   |   AIC = {aic_val:.2f}"
                     f"   |   BIC = {bic_val:.2f}")
    except Exception:
        pass

    # ── Assemble ──────────────────────────────────────────────────────────
    freq_labels = {1: "anual", 4: "trimestral", 12: "mensual"}
    freq_lbl    = freq_labels.get(freq, f"freq={freq}")
    sep = "─" * 64

    lines = [
        sep,
        f"  MODELO ESTIMADO: {ts_name}   (n={ts.nobs}, {freq_lbl})",
        sep,
        "",
        f"  (1)  {_transform_label()} = Dₜ + Nₜ",
        "",
        "  Dₜ:",
    ]
    for val_row, se_row in det_rows:
        lines.append(val_row)
        if se_row:
            lines.append(se_row)

    lines.append("")
    for val_line, se_line in noise_vis_lines:
        lines.append(val_line)
        if se_line:
            lines.append(se_line)

    lines += ["", stat_line, sep]
    return "\n".join(lines)


def _two_cos(f_idx: int, freq: int) -> tuple[float, str]:
    """
    Return (numeric_value, label_str) for the 2·cos(2πf/s) coefficient of
    the B term in a fixed-frequency AR/MA quadratic factor (1 − 2cos·B + c·B²).
    Label uses exact expressions (√3, 1, 0) where known.
    """
    from math import pi, cos
    val   = 2 * cos(2 * pi * f_idx / freq)
    known_labels = {
        12: {1: ("√3",  1.7321),
             2: ("1",   1.0),
             3: ("0",   0.0),
             4: ("1",  -1.0),   # abs value
             5: ("√3", -1.7321)},
        4:  {1: ("0",   0.0),
             2: ("2",  -2.0)},
    }
    if freq in known_labels and f_idx in known_labels[freq]:
        lbl, v = known_labels[freq][f_idx]
        return v, lbl
    return val, f"{abs(val):.4f}"


# ---------------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------------

def describe_diagnosis(model) -> Description:
    """Run diagnosis on a fitted model and summarize results for the LLM."""
    if model._result is None:
        raise RuntimeError("Model has not been fitted — call model.fit() first.")

    result = diagnose(model)
    fig    = plot_diagnosis(result, model)
    b64    = _fig_b64(fig)
    plt.close(fig)

    # Prepend model equation (Bloque O) as the first block of the summary
    try:
        eq_text = model_equation(model.series, model)
    except Exception:
        eq_text = ""

    verdict = "**APROBADO ✓**" if result.clean else "**REVISAR ✗**"
    wn      = "✓" if result.white_noise else "✗"
    nm      = "✓" if result.normal else "✗"

    q_fails = [
        f"lag {lag} (Q={q:.2f}, p={p:.4f})"
        for lag, q, p in zip(result.q_lags, result.q_stats, result.q_pvalues)
        if p < 0.05
    ]

    lines = [
        f"## Diagnosis — {result.label}",
        f"- Veredicto: {verdict}",
        f"- Ruido blanco (Q): {wn}  {'OK' if result.white_noise else ', '.join(q_fails)}",
        f"- Normalidad (JB): {nm}  JB={result.jb_stat:.3f}, p={result.jb_pvalue:.4f}",
        f"- Asimetría={result.skewness:.3f}, curtosis exceso={result.excess_kurtosis:.3f}",
    ]

    if result.seasonal and result.seasonal.seasonal_detected:
        lines.append(
            f"- ⚠ Estacionalidad residual: F={result.seasonal.f_stat:.2f}, "
            f"p={result.seasonal.p_value:.4f}"
        )

    if result.extreme:
        lines.append(
            f"- Residuos extremos (|z|>3): {len(result.extreme)} — "
            + ", ".join(f"obs {o} (z={z:+.2f})" for o, z in result.extreme[:5])
        )

    # Intervention form hints from extreme residuals
    intervention_hints = []
    if result.extreme:
        # Look for consecutive extreme obs (potential step) vs isolated (pulse)
        extreme_obs = sorted(o for o, _ in result.extreme)
        consecutive_pairs = [
            (extreme_obs[i], extreme_obs[i+1])
            for i in range(len(extreme_obs)-1)
            if extreme_obs[i+1] - extreme_obs[i] == 1
        ]
        for obs, z in result.extreme:
            # Check if this obs is part of a consecutive pair
            is_consec = any(obs in pair for pair in consecutive_pairs)
            if is_consec:
                hint = "step o par de pulses (observaciones consecutivas)"
            else:
                hint = "pulse (observación aislada)"
            intervention_hints.append((obs, z, hint))
        lines.append("")
        lines.append("**Intervenciones sugeridas:**")
        for obs, z, hint in intervention_hints:
            lines.append(f"  - obs {obs} (z={z:+.2f}): {hint}")
        if any("step" in h for _, _, h in intervention_hints):
            lines.append(
                "  ℹ Un step indica un cambio de nivel permanente; "
                "un pulse es un shock transitorio de un solo período."
            )

    # Over-parametrization warning (Bloque I)
    # Known false-positive cases where high correlation is structural (not a flaw):
    #   • AR(2) with complex roots + MA: AR and MA share signal structure → high corr expected.
    #     Check RV test (Bloque F) before concluding over-parametrization.
    #   • FLT transfer function (ω + δ): gain and decay rate are jointly identified from
    #     the impulse response ω·δ^t → high corr(ω, δ) is inherent, not redundant.
    def _overpar_note(lbl_i: str, lbl_j: str) -> str:
        ar_ma = (lbl_i.startswith("AR") and lbl_j.startswith("MA")) or \
                (lbl_i.startswith("MA") and lbl_j.startswith("AR"))
        flt   = (lbl_i.startswith("ω(") and lbl_j.startswith("δ")) or \
                (lbl_i.startswith("δ") and lbl_j.startswith("ω("))
        if ar_ma:
            return " ℹ puede ser normal en AR(2) con raíces complejas — verificar con test RV"
        if flt:
            return " ℹ normal en FLT (ω y δ se identifican conjuntamente)"
        return ""

    overpar_pairs = result.high_corr_pairs or []
    if overpar_pairs:
        lines.append("")
        lines.append("**⚠ Posible sobreparametrización** (|corr| > 0.7):")
        for _, _, r_val, lbl_i, lbl_j in overpar_pairs:
            note = _overpar_note(lbl_i, lbl_j)
            lines.append(f"  - corr({lbl_i}, {lbl_j}) = {r_val:+.3f}{note}")

    if result.clean:
        rec = "El modelo pasa la diagnosis. Procede a los contrastes formales (DCD, MEG)."
    else:
        parts = []
        if not result.white_noise and not result.extreme:
            parts.append(
                "los residuos no son ruido blanco — considera añadir términos ARMA "
                f"(falla en lags: {', '.join(str(l) for l, *_ in [(l,q,p) for l,q,p in zip(result.q_lags, result.q_stats, result.q_pvalues) if p < 0.05])})"
            )
        elif not result.white_noise and result.extreme:
            parts.append(
                "el Q-test falla pero hay outliers — añade las intervenciones antes "
                "de evaluar si el Q-test mejora"
            )
        if not result.normal and result.extreme:
            parts.append(
                "la no-normalidad (JB) está probablemente causada por los outliers — "
                "no es un fallo de especificación ARMA"
            )
        elif not result.normal and not result.extreme:
            parts.append("los residuos no son normales sin outliers — revisa la especificación")
        if result.seasonal and result.seasonal.seasonal_detected:
            sig = [str(fr.freq_idx) for fr in (result.seasonal.freq_results or [])
                   if fr.p_value < 0.05]
            parts.append(
                f"hay estacionalidad residual en freq={', '.join(sig)} — "
                "revisa si los armónicos de esas frecuencias están incluidos o "
                "si MEG sugiere que son estocásticas"
            )
        rec = "Reformulación necesaria: " + "; ".join(parts) + "."

    if overpar_pairs:
        pair_str = "; ".join(
            f"corr({lbl_i},{lbl_j})={r_val:+.3f}"
            for _, _, r_val, lbl_i, lbl_j in overpar_pairs
        )
        overpar_note = (
            f" Sobreparametrización: {pair_str}. "
            f"Considera eliminar el parámetro menos significativo de cada par."
        )
        rec = rec.rstrip(".") + "." + overpar_note

    summary_parts = []
    if eq_text:
        summary_parts.append(eq_text)
    summary_parts.append("\n".join(lines))

    return Description(
        summary="\n\n".join(summary_parts),
        figure_b64=b64,
        recommendation=rec,
        data={
            "clean": result.clean,
            "white_noise": result.white_noise,
            "normal": result.normal,
            "jb_stat": result.jb_stat,
            "jb_pvalue": result.jb_pvalue,
            "q_fails": q_fails,
            "n_extreme": len(result.extreme),
            "intervention_hints": [
                {"obs": o, "z": z, "form": h} for o, z, h in intervention_hints
            ],
            "high_corr_pairs": [
                {"i": i, "j": j, "corr": r_val, "label_i": li, "label_j": lj}
                for i, j, r_val, li, lj in overpar_pairs
            ],
            "param_labels": result.param_labels or [],
        },
    )


# ---------------------------------------------------------------------------
# Formal tests
# ---------------------------------------------------------------------------

def describe_formal_tests(model, run_meg: bool = True) -> Description:
    """Run Shin-Fuller, DCD, DCD_f, RV, MEG and summarize for the LLM."""
    if model._result is None:
        raise RuntimeError("Model has not been fitted — call model.fit() first.")

    sf_res    = _try(lambda: shin_fuller(model), None)
    dcd_res   = _try(lambda: dcd(model),   [])
    dcd_f_res = _try(lambda: dcd_f(model), [])
    rv_res    = _try(lambda: rv(model),    [])
    meg_res   = (_try(lambda: meg(model), [])
                 if run_meg and _meg_suitable(model) else [])

    lines = ["## Contrastes formales"]

    # Shin-Fuller (non-stationarity of AR component)
    # Φ̂₁ᵤ = L_free − L_constrained  (eq. 3.5); compare to Table II critical values.
    if sf_res is not None:
        sf_verdict = ("Estacionario ✓" if sf_res.stationary
                      else "Raíz unitaria — considerar d+1 ✗")
        lines.append(
            f"\n**Shin-Fuller (no estacionariedad AR)** "
            f"(H₀: ρ≈1−4/n={sf_res.phi_null:.4f},  n={sf_res.n})"
        )
        phi_str = ", ".join(f"{v:.4f}" for v in sf_res.phi_free)
        lines.append(f"- φ̂ = [{phi_str}]")
        lines.append(
            f"- Φ̂₁ᵤ={sf_res.phi_1u:.3f}"
            f"  (val. crít. 10%={sf_res.crit_10pct:.2f},"
            f" 5%={sf_res.crit_5pct:.2f},"
            f" 1%={sf_res.crit_1pct:.2f})"
            f" → {sf_verdict}"
        )

    # DCD
    if dcd_res:
        lines.append("\n**DCD — no invertibilidad MA regular** (H₀: θ=1, val. crít. 5%=1.94)")
        for r in dcd_res:
            verdict = "Invertible ✓" if r.lr >= 1.94 else "No invertible ✗"
            lines.append(f"- Factor {r.factor_index+1}: θ̂={r.coef_free:+.4f}, "
                         f"LR={r.lr:.3f} → {verdict}")

    # DCD_f
    if dcd_f_res:
        lines.append("\n**DCD_f — no invertibilidad MA estacional** (H₀: λ₂=−1, val. crít. 5%=2.02)")
        for r in dcd_f_res:
            verdict = "Invertible ✓" if r.lr >= 2.02 else "No invertible ✗"
            lines.append(f"- Factor {r.factor_index+1}: coef={r.coef_free:+.4f}, "
                         f"LR={r.lr:.3f} → {verdict}")

    # RV
    if rv_res:
        lines.append("\n**RV — frecuencia de AR(2)**")
        for r in rv_res:
            verdict = "No rechaza ✓" if r.pvalue >= 0.05 else "Rechaza ✗"
            lines.append(f"- f̂={r.freq_hat:.3f}, H₀:f={r.freq_null}: "
                         f"LR={r.lr:.3f}, p={r.pvalue:.4f} → {verdict}")

    # MEG
    stochastic_freqs = []
    if meg_res:
        lines.append("\n**MEG — estacionalidad estocástica** (val. crít. DCD_f 5%=2.02)")
        for r in meg_res:
            if r.dcd_result is None:
                lines.append(f"- freq={r.freq}: {r.status}")
            else:
                lines.append(
                    f"- freq={r.freq}: coef={r.coef_ma_f:.4f}, "
                    f"LR={r.dcd_result.lr:.3f} → **{r.status}**"
                )
                if r.stochastic:
                    stochastic_freqs.append(r.freq)
        if stochastic_freqs:
            lines += [
                "",
                f"  ℹ Frecuencia(s) **estocástica(s)**: {stochastic_freqs}. "
                "Esto significa que el patrón estacional en esas frecuencias cambia "
                "aleatoriamente en el tiempo — no es fijo año a año.",
                "  Acción: en el fichero .inp, activa `ifadf` para esa frecuencia "
                "(raíz unitaria estacional) y elimina los armónicos cos/sin correspondientes. "
                "Reestima y vuelve a diagnosticar.",
            ]
        det_freqs = [r.freq for r in meg_res if not r.stochastic and r.dcd_result]
        if det_freqs:
            lines.append(
                f"  ✓ Frecuencia(s) **determinista(s)**: {det_freqs}. "
                "Los armónicos cos/sin actuales son la especificación correcta."
            )
    elif run_meg and not _meg_suitable(model):
        lines.append(
            "\n*MEG no aplica: requiere D=0 con armónicos cos/sin en el modelo.*"
        )

    if not dcd_res and not dcd_f_res and not rv_res and not meg_res:
        lines.append("*Ningún contraste aplicable a esta especificación.*")

    # Build recommendation
    issues = []
    if sf_res is not None and not sf_res.stationary:
        issues.append(
            f"Shin-Fuller no rechaza H₀ (Φ̂₁ᵤ={sf_res.phi_1u:.3f} ≤ {sf_res.crit_5pct:.2f}): "
            "posible raíz unitaria en el componente AR. Considera aumentar d en 1."
        )
    non_invertible_ma = [r for r in dcd_res if r.lr < 1.94]
    for r in non_invertible_ma:
        issues.append(
            f"MA factor {r.factor_index+1} no es invertible (LR={r.lr:.2f} < 1.94): "
            "el factor θ=1 es una raíz unitaria en el polinomio MA. "
            "Considera eliminar ese factor MA o reducir q en 1."
        )
    for freq in stochastic_freqs:
        issues.append(
            f"freq={freq} es estocástica: activa ifadf[{freq}]=1 y elimina "
            f"los armónicos cos/sin de freq={freq}. Reestima."
        )

    if issues:
        rec = "Reformulación necesaria:\n" + "\n".join(f"  • {i}" for i in issues)
    else:
        rec = "Los contrastes formales no detectan problemas. El modelo es adecuado."

    return Description(
        summary="\n".join(lines),
        figure_b64=None,
        recommendation=rec,
        data={
            "shin_fuller": (
                {"phi_1u": sf_res.phi_1u, "crit_5pct": sf_res.crit_5pct,
                 "crit_1pct": sf_res.crit_1pct, "stationary": sf_res.stationary,
                 "phi_null": sf_res.phi_null, "phi_free": list(sf_res.phi_free)}
                if sf_res is not None else None
            ),
            "dcd": [{"factor": r.factor_index, "lr": r.lr, "coef": r.coef_free}
                    for r in dcd_res],
            "meg": [{"freq": r.freq, "status": r.status,
                     "lr": r.dcd_result.lr if r.dcd_result else None}
                    for r in meg_res],
        },
    )


# ---------------------------------------------------------------------------
# Interventions
# ---------------------------------------------------------------------------

def describe_interventions(model, threshold: float = 3.5) -> Description:
    """Detect extreme residuals and describe their impact for the LLM."""
    if model._result is None:
        raise RuntimeError("Model has not been fitted — call model.fit() first.")

    result = diagnose_interventions(model, threshold=threshold)

    # Residual plot: always include so the analyst can see extreme observations
    try:
        diag_result = diagnose(model, z_threshold=threshold)
        fig_diag    = plot_diagnosis(diag_result, model)
        b64_diag    = _fig_b64(fig_diag)
        plt.close(fig_diag)
    except Exception:
        b64_diag = None

    lines = [f"## Intervenciones — anomalías (|z| > {threshold})"]

    if not result.has_outliers:
        lines.append(f"No se detectan residuos extremos con |z| > {threshold}. "
                     f"No es necesaria ninguna intervención.")
        rec = "Sin anomalías. El modelo no requiere intervenciones."
    else:
        lines.append(f"Se detectan **{len(result.outliers)} residuo(s) extremo(s)**:")
        for w in result.outliers:
            lags = ", ".join(str(j) for j in w.acf_lags_affected) or "ninguno"
            lines.append(
                f"- **{w.date}**: z={w.z:+.3f}, "
                f"varianza%={100*w.variance_fraction:.1f}%, "
                f"lags ACF afectados: {lags}"
            )
        if result.jb_unreliable:
            lines.append(
                "\n⚠ El test Jarque-Bera no es fiable con anomalías presentes."
            )
        if result.q_unreliable:
            lines.append(
                "⚠ El estadístico Q de Ljung-Box no es fiable con anomalías presentes."
            )

        dates = [w.date for w in result.outliers]
        rec = (
            f"Hay {len(result.outliers)} anomalía(s) en {', '.join(dates)}. "
            f"Para cada una debes especificar la forma funcional de la intervención "
            f"(pulse, step, ramp) en el fichero .inp y reestimar. "
            f"Indica la fecha y el tipo de evento para que pueda ayudarte a elegir la forma."
        )

    return Description(
        summary="\n".join(lines),
        figure_b64=b64_diag,
        recommendation=rec,
        data={
            "has_outliers": result.has_outliers,
            "threshold": threshold,
            "outliers": [
                {"date": w.date, "z": w.z, "variance_fraction": w.variance_fraction,
                 "acf_lags": w.acf_lags_affected}
                for w in result.outliers
            ],
        },
    )


# ---------------------------------------------------------------------------
# Pre-identification outlier scan
# ---------------------------------------------------------------------------

def describe_prelim_scan(ts, d: int, D: int, lam: float = 0.0,
                          threshold: float = 3.5) -> Description:
    """
    Scan the differenced series for extreme observations BEFORE ARMA identification.

    "Lo más obvio primero": if a giant outlier is killing the ACF/PACF, treat it
    before choosing p and q — those tools are not robust to outliers.

    Returns a figure of the standardised ∇ᵈ∇ᴰ series with ±2σ bands and
    outliers marked, plus a list of candidate dates for intervention.
    """
    import numpy as np

    y     = np.asarray(ts.data, dtype=float)
    freq  = ts.freq
    start = getattr(ts, "start", (1, 1))
    name  = ts.name or "series"

    # Transform + difference
    z = boxcox_transform(y, lam)
    w = apply_differences(z, freq, d, D)

    # Standardise
    mu    = w.mean()
    sigma = w.std(ddof=0) if w.std(ddof=0) > 1e-10 else 1.0
    w_std = (w - mu) / sigma

    # Offset of first w observation relative to ts start
    n_lost = d + D * freq      # observations removed by differencing
    t_offset = n_lost          # 0-based index of w[0] in original series

    # Find extreme observations
    extreme_idx = np.where(np.abs(w_std) > threshold)[0]  # relative to w

    # Convert to (period, year) labels
    beg_year   = start[0] if hasattr(start, '__iter__') else int(start)
    beg_period = start[1] if (hasattr(start, '__iter__') and len(start) > 1) else 1

    def _idx_to_date(i_w):
        obs_0 = t_offset + i_w
        offset = beg_period - 1 + obs_0
        yr  = beg_year + offset // freq
        per = offset % freq + 1
        if freq == 12:
            return f"{per:02d}/{yr}"
        elif freq == 4:
            return f"Q{per}/{yr}"
        else:
            return str(yr)

    outliers = [(int(i), float(w_std[i]), _idx_to_date(i)) for i in extreme_idx]

    # ── Figure ────────────────────────────────────────────────────────────────
    label = transform_label(lam, d, D, freq)
    fig, ax = plt.subplots(figsize=(13, 3.5))
    n_w  = len(w_std)
    xs   = np.arange(n_w)

    ax.axhline(0,        color="black",  lw=0.7)
    ax.axhline(+2,       color="#888888", lw=0.8, ls="--")
    ax.axhline(-2,       color="#888888", lw=0.8, ls="--")
    ax.axhline(+threshold, color="#cc3333", lw=0.9, ls=":")
    ax.axhline(-threshold, color="#cc3333", lw=0.9, ls=":")

    ax.plot(xs, w_std, color="#1f77b4", lw=1.0)

    for i, z_i, date in outliers:
        ax.plot(i, z_i, "o", color="#cc3333", ms=7, zorder=5)
        va = "bottom" if z_i >= 0 else "top"
        ax.annotate(date, (i, z_i), fontsize=7.5, color="#cc3333",
                    xytext=(0, 6 if z_i >= 0 else -6),
                    textcoords="offset points", ha="center", va=va)

    ax.fill_between(xs, -2, 2, alpha=0.06, color="#1f77b4")
    ax.set_ylabel("z-score", fontsize=9)
    ax.set_title(f"{name} — {label}  (tipificada, umbral ±{threshold}σ)",
                 fontsize=10, fontweight="bold")
    ax.tick_params(axis="both", labelsize=8)
    fig.tight_layout()

    b64 = _fig_b64(fig)
    plt.close(fig)

    # ── Summary text ──────────────────────────────────────────────────────────
    lines = [
        f"## Escaneo pre-identificación — {name}  ({label})",
        f"- Serie tipificada: n={len(w_std)}, μ̂={mu:.4f}, σ̂={sigma:.4f}",
        f"- Umbral: |z| > {threshold}",
    ]

    if not outliers:
        lines.append("- **Sin observaciones extremas.** Las ACF/PACF reflejan fielmente la estructura ARMA.")
        rec = (
            "No hay outliers que distorsionen la identificación. "
            "Procede directamente a elegir (p, q) a partir de las ACF/PACF."
        )
    else:
        lines.append(f"- **{len(outliers)} observación(es) extrema(s)** detectada(s):")
        for _, z_i, date in sorted(outliers, key=lambda x: -abs(x[1])):
            sign = "positivo" if z_i > 0 else "negativo"
            form_hint = "pulse" if abs(z_i) > 5 else "pulse o step"
            lines.append(f"  - **{date}**: z={z_i:+.2f} ({sign}) → forma tentativa: {form_hint}")

        # Variance fraction from biggest outlier
        var_max = max(z_i**2 for _, z_i, _ in outliers) / np.sum(w_std**2) * 100
        lines += [
            "",
            f"⚠ El outlier mayor explica aprox. **{var_max:.1f}%** de la varianza tipificada.",
            "Esto distorsiona la ACF/PACF: los coeficientes de autocorrelación están",
            "subestimados y la estructura ARMA real puede quedar enmascarada.",
            "",
            "**Principio 'lo más obvio primero'**: añade las intervenciones sobre estos",
            "puntos en el fichero .inp ANTES de identificar los órdenes ARMA.",
        ]

        dates = [date for _, _, date in outliers]
        rec = (
            f"Hay {len(outliers)} outlier(s) en {', '.join(dates)} que distorsionan "
            f"la ACF/PACF. Antes de identificar (p, q), añade una intervención "
            f"(pulse o step) para cada fecha en el .inp y estima un modelo "
            f"con solo armónicos + intervenciones. Luego examina la ACF/PACF de "
            f"los residuos de ESE modelo para identificar la estructura ARMA."
        )

    return Description(
        summary="\n".join(lines),
        figure_b64=b64,
        recommendation=rec,
        data={
            "n_outliers": len(outliers),
            "threshold": threshold,
            "outliers": [{"obs_w": i, "z": z_i, "date": date}
                         for i, z_i, date in outliers],
            "has_distortion": len(outliers) > 0,
        },
    )


# ---------------------------------------------------------------------------
# Seasonal parameters (Bloque G)
# ---------------------------------------------------------------------------

def describe_seasonal_params(model) -> Description:
    """
    Visualise estimated cos/sin harmonic coefficients with ±2 SE error bars.

    Two-panel bar chart (cos_k | sin_k) by harmonic index k=1..freq//2.
    Significant bars (|t| > 2) are coloured; non-significant are grey.
    Text table summarises t-ratios and amplitude A_k = sqrt(cos_k²+sin_k²).
    Recommendation flags harmonics that could be dropped.
    """
    import numpy as np

    if model._result is None:
        raise RuntimeError("Model has not been fitted — call model.fit() first.")

    freq = model.series.freq

    # ── extract harmonic parameters in model.params order ──────────────────
    params = list(model.params)
    ses    = list(model.std_errors)
    pi_idx = 0
    harmonic_data: dict[int, dict] = {}   # k → {component: (v, se)}

    for itv in (model.interventions or []):
        t    = itv.type
        om   = list(itv.omega)     if itv.omega     else []
        om_f = (list(itv.omega_free)
                if (hasattr(itv, "omega_free") and itv.omega_free)
                else [True] * len(om))
        h    = int(round(getattr(itv, "harmonic", 1)))

        if t in ("cos", "sin", "alter"):
            if om_f[0]:
                v, se = params[pi_idx], ses[pi_idx]
                pi_idx += 1
            else:
                v, se = (om[0] if om else 0.0), 0.0
            k         = (freq // 2) if t == "alter" else h
            component = "cos" if t in ("cos", "alter") else "sin"
            harmonic_data.setdefault(k, {})[component] = (v, se)

        elif t in ("step", "pulse", "impulse", "ramp", "compimp"):
            for free in om_f:
                if free:
                    pi_idx += 1

    if not harmonic_data:
        return Description(
            summary="No hay parámetros estacionales (cos/sin) en este modelo.",
            figure_b64=None,
            recommendation="El modelo no contiene armónicos estacionales.",
            data={},
        )

    # ── frequency label helper ──────────────────────────────────────────────
    def _freq_label(k: int) -> str:
        from math import gcd as _gcd
        half = freq // 2
        g    = _gcd(k, half)
        num, den = k // g, half // g
        if den == 1:
            frac = "π" if num == 1 else f"{num}π"
        else:
            frac = f"π/{den}" if num == 1 else f"{num}π/{den}"
        return f"k={k}\n({frac})"

    k_all = sorted(harmonic_data.keys())

    # ── figure ──────────────────────────────────────────────────────────────
    k_cos = [k for k in k_all if "cos" in harmonic_data[k]]
    k_sin = [k for k in k_all if "sin" in harmonic_data[k]]

    has_cos = bool(k_cos)
    has_sin = bool(k_sin)
    n_panels = (1 if has_cos else 0) + (1 if has_sin else 0)
    fig, axes = plt.subplots(1, n_panels, figsize=(5 * n_panels, 4.5), squeeze=False)
    ax_iter = iter(axes[0])

    def _bar_panel(ax, k_list, component, title):
        vals  = [harmonic_data[k][component][0] for k in k_list]
        svals = [harmonic_data[k][component][1] for k in k_list]
        t_abs = [abs(v) / (s + 1e-12) for v, s in zip(vals, svals)]
        cols  = ["steelblue" if t > 2 else "lightgrey" for t in t_abs]
        xerrs = [2 * s for s in svals]
        xs    = list(range(len(k_list)))
        ax.bar(xs, vals, yerr=xerrs, capsize=5, color=cols,
               edgecolor="dimgrey", linewidth=0.6, error_kw={"elinewidth": 1.2})
        ax.axhline(0, color="crimson", linestyle="--", linewidth=0.8)
        ax.set_title(title, fontsize=11)
        ax.set_xticks(xs)
        ax.set_xticklabels([_freq_label(k) for k in k_list], fontsize=8)
        ax.set_xlabel("Frecuencia k", fontsize=9)
        ax.set_ylabel("Coeficiente", fontsize=9)
        ax.tick_params(axis="y", labelsize=8)

    if has_cos:
        _bar_panel(next(ax_iter), k_cos, "cos", "Coeficientes cos(ωₖt)")
    if has_sin:
        _bar_panel(next(ax_iter), k_sin, "sin", "Coeficientes sin(ωₖt)")

    series_name = getattr(model.series, "name", "") or "modelo"
    fig.suptitle(f"Parámetros estacionales — {series_name}  (freq={freq})",
                 fontsize=12, y=1.01)
    fig.tight_layout()
    b64 = _fig_b64(fig)
    plt.close(fig)

    # ── text table ──────────────────────────────────────────────────────────
    def _fv(v: float) -> str:
        a = abs(v)
        if a == 0:
            return "  0"
        if a >= 0.001:
            return f"{v:+.4f}"   # "+0.1234"  7 chars
        return f"{v:+.2e}"       # "+1.23e-05"  9 chars — use wider col for these

    def _fse(se: float) -> str:
        if se <= 0:
            return "(—)"
        if se >= 0.001:
            return f"({se:.4f})"  # "(0.0456)"  8 chars
        return f"({se:.2e})"      # "(1.23e-05)" 10 chars

    # Use dynamic column widths to accommodate scientific notation for tiny values
    VW = 9   # value column width
    SW = 10  # SE column width

    NA_V  = " " * (VW - 1) + "—"
    NA_SE = " " * (SW - 1) + "—"
    NA_T  = "     —"

    header = (f"{'k':>3}  {'freq':>6}  "
              f"{'cos_k':>{VW}}  {'SE_cos':>{SW}}  {'t_cos':>6}  "
              f"{'sin_k':>{VW}}  {'SE_sin':>{SW}}  {'t_sin':>6}  "
              f"{'A_k':>7}")
    sep = "-" * len(header)
    rows = [header, sep]

    sig_k: list[int] = []
    drop_k: list[int] = []
    table_data = []

    for k in k_all:
        grp = harmonic_data[k]
        cos_v, cos_se = grp.get("cos", (None, None))
        sin_v, sin_se = grp.get("sin", (None, None))

        t_cos = (abs(cos_v) / (cos_se + 1e-12) if cos_v is not None else 0.0)
        t_sin = (abs(sin_v) / (sin_se + 1e-12) if sin_v is not None else 0.0)
        A_k   = math.sqrt(
            (cos_v ** 2 if cos_v is not None else 0.0)
            + (sin_v ** 2 if sin_v is not None else 0.0)
        )

        cos_str = f"{_fv(cos_v):>{VW}}"   if cos_v is not None else NA_V
        cse_str = f"{_fse(cos_se):>{SW}}" if cos_v is not None else NA_SE
        tc_str  = f"{t_cos:>6.2f}"        if cos_v is not None else NA_T
        sin_str = f"{_fv(sin_v):>{VW}}"   if sin_v is not None else NA_V
        sse_str = f"{_fse(sin_se):>{SW}}" if sin_v is not None else NA_SE
        ts_str  = f"{t_sin:>6.2f}"        if sin_v is not None else NA_T

        from math import gcd as _gcd
        half = freq // 2
        g    = _gcd(k, half)
        num, den = k // g, half // g
        frac = (f"π/{den}" if num == 1 else f"{num}π/{den}") if den > 1 else ("π" if num == 1 else f"{num}π")

        rows.append(f"{k:>3}  {frac:>6}  "
                    f"{cos_str}  {cse_str}  {tc_str}  "
                    f"{sin_str}  {sse_str}  {ts_str}  "
                    f"{A_k:>7.4f}")

        sig_cos = cos_v is not None and t_cos > 2
        sig_sin = sin_v is not None and t_sin > 2
        if sig_cos or sig_sin:
            sig_k.append(k)
        else:
            drop_k.append(k)

        table_data.append({
            "k": k, "freq": frac,
            "cos_v": cos_v, "cos_se": cos_se, "t_cos": t_cos if cos_v is not None else None,
            "sin_v": sin_v, "sin_se": sin_se, "t_sin": t_sin if sin_v is not None else None,
            "A_k": A_k,
        })

    name = getattr(model.series, "name", "") or "modelo"
    summary_lines = [
        f"## Parámetros estacionales — {name}  (freq={freq})\n",
        "```",
        *rows,
        "```",
        "",
    ]
    if sig_k:
        summary_lines.append(
            f"**Frecuencias significativas (|t| > 2):** "
            + ", ".join(f"k={k}" for k in sig_k)
        )
    if drop_k:
        summary_lines.append(
            f"**Frecuencias no significativas (|t| ≤ 2 en ambos componentes):** "
            + ", ".join(f"k={k}" for k in drop_k)
        )

    if drop_k:
        rec = (
            f"Los armónicos {', '.join(f'k={k}' for k in drop_k)} tienen |t| ≤ 2 "
            f"en ambos componentes. Considera eliminarlos con un test RV conjunto "
            f"(Bloque H) antes de simplificar."
        )
    else:
        rec = "Todos los armónicos son significativos (|t| > 2). No se recomienda simplificación."

    return Description(
        summary="\n".join(summary_lines),
        figure_b64=b64,
        recommendation=rec,
        data={"freq": freq, "harmonics": table_data,
              "significant_k": sig_k, "droppable_k": drop_k},
    )


# ---------------------------------------------------------------------------
# Seasonal simplification test (Bloque H)
# ---------------------------------------------------------------------------

def describe_seasonal_simplification(model, freq_list=None,
                                      alpha: float = 0.05) -> Description:
    """
    Joint LR test for eliminating seasonal harmonics from a fitted model.

    H₀: cos_k = sin_k = 0 for all k in freq_list.
    LR ~ χ²(df), df = number of constrained parameters.

    Parameters
    ----------
    model     : fue.Model, already fitted
    freq_list : list[int] | None
        Harmonic indices k to test (None = all free harmonics in model).
    alpha     : significance level (default 0.05)
    """
    from .formal_tests import seasonal_simplification_test
    import scipy.stats as sp_stats

    if model._result is None:
        raise RuntimeError("Model has not been fitted — call model.fit() first.")

    result = seasonal_simplification_test(model, freq_list=freq_list, alpha=alpha)

    freq     = model.series.freq
    name     = getattr(model.series, "name", "") or "modelo"
    ks_str   = ", ".join(f"k={k}" for k in result.harmonics_tested)
    crit_90  = sp_stats.chi2.ppf(0.90, df=result.df)
    crit_95  = sp_stats.chi2.ppf(0.95, df=result.df)
    crit_99  = sp_stats.chi2.ppf(0.99, df=result.df)
    verdict  = ("**RECHAZA H₀** — los armónicos son conjuntamente significativos ✗"
                if result.rejects
                else "**No rechaza H₀** — los armónicos pueden eliminarse ✓")
    stars    = ("***" if result.pvalue < 0.01
                else "** " if result.pvalue < 0.05
                else "*  " if result.pvalue < 0.10
                else "   ")

    lines = [
        f"## Test de simplificación estacional — {name}  (freq={freq})\n",
        f"**H₀:** cos_k = sin_k = 0  para  {ks_str}",
        f"**df** = {result.df}  "
        f"({'2 por armónico regular, 1 para Nyquist' if result.df > 1 else '1 param'})\n",
        "| Estadístico | Valor |",
        "|-------------|-------|",
        f"| logL(libre)       | {result.loglik_free:.4f} |",
        f"| logL(restringido) | {result.loglik_constrained:.4f} |",
        f"| **LR**            | **{result.lr:.4f}** {stars} |",
        f"| p-value           | {result.pvalue:.4f} |",
        "",
        f"Valores críticos χ²({result.df}): "
        f"10%={crit_90:.2f}  5%={crit_95:.2f}  1%={crit_99:.2f}\n",
        f"→ {verdict}",
    ]

    if result.rejects:
        rec = (
            f"Los armónicos {ks_str} son conjuntamente significativos "
            f"(LR={result.lr:.3f} > χ²({result.df}, 5%)={crit_95:.2f}). "
            f"No se pueden eliminar del modelo sin pérdida de ajuste."
        )
    else:
        rec = (
            f"Los armónicos {ks_str} pueden eliminarse: "
            f"LR={result.lr:.3f} < χ²({result.df}, 5%)={crit_95:.2f}, "
            f"p={result.pvalue:.4f}. "
            f"Reformula el modelo sin esos armónicos y reestima."
        )

    return Description(
        summary="\n".join(lines),
        figure_b64=None,
        recommendation=rec,
        data={
            "harmonics_tested": result.harmonics_tested,
            "df": result.df,
            "lr": result.lr,
            "pvalue": result.pvalue,
            "rejects": result.rejects,
            "loglik_free": result.loglik_free,
            "loglik_constrained": result.loglik_constrained,
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fig_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()
