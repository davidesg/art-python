"""Guion de análisis BJ-T — traza completa de versiones del modelo."""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class GuionStats:
    loglik: float
    aic: float | None
    bic: float | None
    sigma_a: float
    q_pass: bool | None
    jb_pass: bool | None
    n_extreme: int
    extreme: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class GuionEntry:
    version: int
    name: str
    inp_path: str
    timestamp: str
    spec: dict[str, Any]
    stats: GuionStats
    equation: str
    decision: str
    rationale: str
    problems_found: str
    next_version: str
    figure_b64: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GuionEntry":
        d = dict(d)
        stats_d = d.pop("stats")
        stats = GuionStats(**stats_d)
        return cls(stats=stats, **d)


@dataclass
class Guion:
    series: str
    analyst: str
    created: str
    entries: list[GuionEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "series": self.series,
            "analyst": self.analyst,
            "created": self.created,
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Guion":
        entries = [GuionEntry.from_dict(e) for e in d.get("entries", [])]
        return cls(
            series=d.get("series", ""),
            analyst=d.get("analyst", ""),
            created=d.get("created", ""),
            entries=entries,
        )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def load_guion(path: str) -> Guion:
    with open(path, encoding="utf-8") as f:
        return Guion.from_dict(json.load(f))


def save_guion(guion: Guion, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(guion.to_dict(), f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Spec / stats extraction
# ---------------------------------------------------------------------------

def _at_to_date(at: int, start_year: int, start_per: int, freq: int) -> str:
    """Convert 0-based observation index to a date string (MM/YYYY or QN/YYYY or YYYY)."""
    if freq == 12:
        total = (start_per - 1) + at
        month = total % 12 + 1
        year  = start_year + total // 12
        return f"{month:02d}/{year}"
    elif freq == 4:
        total = (start_per - 1) + at
        q    = total % 4 + 1
        year = start_year + total // 4
        return f"Q{q}/{year}"
    else:
        return str(start_year + at)


def _extract_spec(model, lam: float) -> dict[str, Any]:
    """Build spec dict from a fue.Model instance."""
    p = len(model.ar[0]) if model.ar else 0
    q = len(model.ma[0]) if model.ma else 0
    P = len(model.ar_s[0]) if model.ar_s else 0
    Q = len(model.ma_s[0]) if model.ma_s else 0

    itv = model.interventions or []
    n_harmonics = sum(1 for i in itv if i.type == "cos")

    freq = model.series.freq if model.series else 12
    sy, sp = (model.series.start if model.series else (2000, 1))

    other_itvs = [
        {"type": i.type, "date": _at_to_date(i.at, sy, sp, freq)}
        for i in itv
        if i.type not in ("cos", "sin", "alter")
    ]

    return {
        "lam": lam,
        "d": model.d,
        "D": model.D,
        "p": p,
        "q": q,
        "P": P,
        "Q": Q,
        "n_harmonics": n_harmonics,
        "interventions": other_itvs,
    }


def _extract_stats(model, diag_result) -> GuionStats:
    """Build GuionStats from a fitted fue.Model and its DiagnosisResult."""
    r = model._result
    sigma_a = math.sqrt(r.sigma2) if r.sigma2 and r.sigma2 > 0 else 0.0

    # extreme: list of (obs_1based, z) from DiagnosisResult
    n_orig = len(model.series.data)
    n_res  = len(r.residuals)
    offset = n_orig - n_res   # observations removed by differencing / AR init
    s = model.series.freq

    extreme_list = []
    for obs1, z in diag_result.extreme:
        t0 = offset + obs1 - 1    # 0-based in original series
        try:
            yr, per = model.series._obs_to_date(t0 + 1)
            if s == 12:
                date_str = f"{per:02d}/{yr}"
            elif s == 4:
                date_str = f"Q{per}/{yr}"
            else:
                date_str = str(yr)
        except Exception:
            date_str = str(obs1)
        extreme_list.append({"obs": int(obs1), "date": date_str, "z": float(z)})

    return GuionStats(
        loglik=float(r.loglik),
        aic=float(r.aic) if r.aic is not None else None,
        bic=float(r.bic) if r.bic is not None else None,
        sigma_a=sigma_a,
        q_pass=diag_result.white_noise,
        jb_pass=diag_result.normal,
        n_extreme=len(extreme_list),
        extreme=extreme_list,
    )


# ---------------------------------------------------------------------------
# Equation builder
# ---------------------------------------------------------------------------

def _build_equation(spec: dict[str, Any], freq: int) -> str:
    """
    Build a human-readable BL-O equation string from spec.

    Example: ∇²[ln y_t] = D_t(6 arm.) + (1-θ₁B) a_t
    """
    lam = spec.get("lam", 0.0)
    d   = spec.get("d", 0)
    D   = spec.get("D", 0)
    p   = spec.get("p", 0)
    q   = spec.get("q", 0)
    P   = spec.get("P", 0)
    Q   = spec.get("Q", 0)
    n_h = spec.get("n_harmonics", 0)
    itvs = spec.get("interventions", [])

    # Transformed series symbol
    if abs(lam) < 1e-6:
        yt = "ln y_t"
    elif abs(lam - 0.5) < 1e-6:
        yt = "√y_t"
    elif abs(lam - 1.0) < 1e-6:
        yt = "y_t"
    else:
        yt = f"y_t^{{{lam:.2f}}}"

    # Differencing
    diff = ""
    if d == 1:
        diff = "∇"
    elif d > 1:
        diff = f"∇^{d}"
    if D == 1:
        diff += f"∇_{freq}"
    elif D > 1:
        diff += f"∇_{freq}^{D}"

    lhs = f"{diff}[{yt}]" if diff else yt

    # Deterministic RHS components
    rhs_parts = []
    if n_h > 0:
        rhs_parts.append(f"D_t({n_h} arm.)")
    if itvs:
        rhs_parts.append(f"I_t({len(itvs)} itvs)")

    # Stochastic noise N_t
    ar_str  = f"φ(B)"  if p > 0 else ""
    ar_s_str = f"Φ(B^{freq})" if P > 0 else ""
    ma_str  = f"θ(B)"  if q > 0 else ""
    ma_s_str = f"Θ(B^{freq})" if Q > 0 else ""

    ar_full  = "·".join(filter(None, [ar_s_str, ar_str]))
    ma_full  = "·".join(filter(None, [ma_s_str, ma_str]))

    if not ar_full and not ma_full:
        noise = "a_t"
    elif not ar_full:
        noise = f"[1-{ma_full}]·a_t"
    elif not ma_full:
        noise = f"[1-{ar_full}]⁻¹·a_t"
    else:
        noise = f"[1-{ar_full}]⁻¹·[1-{ma_full}]·a_t"

    if rhs_parts:
        rhs = " + ".join(rhs_parts) + " + " + noise
    else:
        rhs = noise

    return lhs + " = " + rhs


# ---------------------------------------------------------------------------
# HTML export
# ---------------------------------------------------------------------------

_CSS = """
body { font-family: "Segoe UI", Arial, sans-serif; max-width: 1100px; margin: 40px auto;
       padding: 0 20px; background:#f7f7f7; color:#222; }
h1 { color:#1a237e; border-bottom:3px solid #1a237e; padding-bottom:8px; }
h2 { color:#283593; margin-top:32px; }
table { border-collapse:collapse; width:100%; margin:16px 0; background:#fff; }
th { background:#283593; color:#fff; padding:8px 12px; text-align:left; font-size:13px; }
td { padding:7px 12px; border-bottom:1px solid #e0e0e0; font-size:13px; }
tr:hover td { background:#e8eaf6; }
.ok  { color:#2e7d32; font-weight:bold; }
.bad { color:#c62828; font-weight:bold; }
details { background:#fff; border:1px solid #c5cae9; border-radius:6px;
          margin:14px 0; padding:12px 18px; }
summary { font-size:16px; font-weight:bold; color:#283593; cursor:pointer; }
summary:hover { color:#1a237e; }
.eq { font-family:monospace; background:#f0f4ff; border-left:4px solid #5c6bc0;
      padding:8px 14px; margin:10px 0; font-size:14px; }
.decision { background:#fff9c4; border-left:4px solid #f9a825;
            padding:8px 14px; margin:6px 0; }
.problems { background:#fce4ec; border-left:4px solid #e91e63;
            padding:8px 14px; margin:6px 0; }
.next     { background:#e8f5e9; border-left:4px solid #43a047;
            padding:8px 14px; margin:6px 0; }
img { max-width:100%; border:1px solid #c5cae9; border-radius:4px; margin:10px 0; }
.meta { color:#555; font-size:12px; margin:2px 0; }
"""


def _pass_cell(val: bool | None) -> str:
    if val is None:
        return "<td>—</td>"
    if val:
        return '<td class="ok">✓</td>'
    return '<td class="bad">✗</td>'


def export_guion_html(guion: Guion) -> str:
    """Render a Guion to a self-contained HTML string."""
    lines = [
        "<!DOCTYPE html><html lang='es'><meta charset='utf-8'>",
        f"<title>Guion — {guion.series}</title>",
        f"<style>{_CSS}</style>",
        "<body>",
        f"<h1>Guion de análisis — {guion.series}</h1>",
        f"<p class='meta'>Analista: {guion.analyst} &nbsp;·&nbsp; Creado: {guion.created}</p>",
    ]

    if not guion.entries:
        lines.append("<p><em>Sin versiones registradas.</em></p>")
    else:
        # Summary table
        lines += [
            "<h2>Resumen de versiones</h2>",
            "<table>",
            "<tr><th>#</th><th>Nombre</th><th>Ecuación</th>"
            "<th>loglik</th><th>AIC</th><th>BIC</th>"
            "<th>σ_a</th><th>Q</th><th>JB</th><th>Anomalías</th><th>Decisión (resumen)</th></tr>",
        ]
        for e in guion.entries:
            s = e.stats
            aic_str = f"{s.aic:.1f}" if s.aic is not None else "—"
            bic_str = f"{s.bic:.1f}" if s.bic is not None else "—"
            dec_short = e.decision[:60] + "…" if len(e.decision) > 60 else e.decision
            lines.append(
                f"<tr>"
                f"<td>{e.version}</td><td><a href='#v{e.version}'>{e.name}</a></td>"
                f"<td><code>{e.equation}</code></td>"
                f"<td>{s.loglik:.2f}</td><td>{aic_str}</td><td>{bic_str}</td>"
                f"<td>{s.sigma_a:.5f}</td>"
                + _pass_cell(s.q_pass) + _pass_cell(s.jb_pass) +
                f"<td>{s.n_extreme}</td>"
                f"<td>{dec_short}</td>"
                f"</tr>"
            )
        lines.append("</table>")

        # Per-entry collapsible sections
        lines.append("<h2>Detalle por versión</h2>")
        for e in guion.entries:
            s = e.stats
            open_attr = " open" if e == guion.entries[-1] else ""
            aic_hdr = f"{s.aic:.1f}" if s.aic is not None else "—"
            q_hdr   = "✓" if s.q_pass else ("✗" if s.q_pass is False else "—")
            jb_hdr  = "✓" if s.jb_pass else ("✗" if s.jb_pass is False else "—")
            lines += [
                f"<details id='v{e.version}'{open_attr}>",
                f"<summary>v{e.version} — {e.name}"
                f"  <span style='font-weight:normal;font-size:13px;color:#555'>"
                f"  AIC={aic_hdr}  Q={q_hdr}  JB={jb_hdr}"
                f"  </span></summary>",
                f"<p class='meta'>Archivo: <code>{e.inp_path}</code> &nbsp;·&nbsp; {e.timestamp}</p>",
                f"<div class='eq'>{e.equation}</div>",
            ]

            # Spec table
            sp = e.spec
            lines += [
                "<table style='width:auto;margin:8px 0'>",
                "<tr><th>λ</th><th>d</th><th>D</th><th>p</th><th>q</th>"
                "<th>P</th><th>Q</th><th>arm.</th><th>itvs</th></tr>",
                f"<tr>"
                f"<td>{sp.get('lam',0):.1f}</td><td>{sp.get('d',0)}</td>"
                f"<td>{sp.get('D',0)}</td><td>{sp.get('p',0)}</td><td>{sp.get('q',0)}</td>"
                f"<td>{sp.get('P',0)}</td><td>{sp.get('Q',0)}</td>"
                f"<td>{sp.get('n_harmonics',0)}</td>"
                f"<td>{len(sp.get('interventions',[]))}</td>"
                f"</tr></table>",
            ]

            # Stats
            aic_s = f"{s.aic:.2f}" if s.aic is not None else "—"
            bic_s = f"{s.bic:.2f}" if s.bic is not None else "—"
            lines += [
                "<table style='width:auto;margin:8px 0'>",
                "<tr><th>loglik</th><th>AIC</th><th>BIC</th><th>σ_a</th><th>Q</th><th>JB</th><th>Anomalías</th></tr>",
                f"<tr><td>{s.loglik:.3f}</td><td>{aic_s}</td><td>{bic_s}</td>"
                f"<td>{s.sigma_a:.6f}</td>"
                + _pass_cell(s.q_pass) + _pass_cell(s.jb_pass) +
                f"<td>{s.n_extreme}</td></tr>",
                "</table>",
            ]

            if s.extreme:
                lines.append("<p><b>Residuos extremos:</b> "
                             + ", ".join(f"{x['date']} (z={x['z']:+.2f})" for x in s.extreme)
                             + "</p>")

            if e.decision:
                lines.append(f"<div class='decision'><b>Decisión:</b> {e.decision}</div>")
            if e.rationale:
                lines.append(f"<div class='decision'><b>Justificación:</b> {e.rationale}</div>")
            if e.problems_found:
                lines.append(f"<div class='problems'><b>Problemas detectados:</b> {e.problems_found}</div>")
            if e.next_version:
                lines.append(f"<div class='next'><b>Próxima versión:</b> {e.next_version}</div>")

            if e.figure_b64:
                lines.append(f"<img src='data:image/png;base64,{e.figure_b64}' alt='diagnosis'>")

            lines.append("</details>")

    lines.append("</body></html>")
    return "\n".join(lines)
