"""
Phase 5: save_full_report — integrated HTML report for a fitted fue model.

Covers post-estimation stages of the Box-Jenkins-Treadway workflow:
  Section 1 — Estimated model (orders, parameters, SE, t-stats, AIC/BIC)
  Section 2 — Diagnosis (residuals, ACF/PACF, Q-test, Jarque-Bera)
  Section 3 — Formal tests (DCD, DCD_f, RV, MEG where applicable)
  Section 4 — Intervention warnings (extreme residuals, ACF distortion)

Identification sections (box-cox, seasonal detection, listing) are handled
by their own modules and are outside scope here — the analyst has already
completed those steps before arriving at a fitted model.
"""

from __future__ import annotations

import base64
import io
import math
from dataclasses import dataclass, field

import numpy as np
import matplotlib.pyplot as plt

from .diagnosis import diagnose, plot_diagnosis, DiagnosisResult
from .formal_tests import (
    dcd, dcd_f, rv, meg,
    DCDResult, RVResult, MEGResult,
)
from .interventions import diagnose_interventions, InterventionDiagnosis


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class FullReport:
    """
    Container for save_full_report results.

    All computed sub-results are available for programmatic inspection;
    the HTML file is written to `path`.
    """
    path: str
    diagnosis: DiagnosisResult
    dcd_results: list[DCDResult]
    dcd_f_results: list[DCDResult]
    rv_results: list[RVResult]
    meg_results: list[MEGResult]
    interventions: InterventionDiagnosis


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_full_report(
    model,
    path: str,
    *,
    run_meg: bool = True,
    intervention_threshold: float = 3.5,
    z_threshold: float = 3.0,
) -> FullReport:
    """
    Generate a self-contained HTML report for a fitted fue model.

    Parameters
    ----------
    model : fue.Model, already fitted
    path : str
        Output HTML file path.
    run_meg : bool
        Run MEG test (default True).  Only executed when the model has D=0
        and at least one harmonic (cos/sin/alter) — the criterion for an
        adequate model in the iterative Treadway workflow.
    intervention_threshold : float
        |z| threshold for OutlierWarning (default 3.5).
    z_threshold : float
        |z| threshold for extreme residuals table in diagnosis (default 3.0).

    Returns
    -------
    FullReport
    """
    if model._result is None:
        raise RuntimeError("Model has not been fitted — call model.fit() first.")

    # --- Run all sub-modules ---
    diag   = diagnose(model, z_threshold=z_threshold)
    fig    = plot_diagnosis(diag, model)
    diag_b64 = _fig_to_b64(fig)
    plt.close(fig)

    dcd_res   = _try(lambda: dcd(model),   [])
    dcd_f_res = _try(lambda: dcd_f(model), [])
    rv_res    = _try(lambda: rv(model),    [])

    if run_meg and _meg_suitable(model):
        meg_res = _try(lambda: meg(model), [])
    else:
        meg_res = []

    itv_diag = diagnose_interventions(model, threshold=intervention_threshold)

    # --- Build HTML ---
    html = _build_html(
        model, diag, diag_b64, z_threshold,
        dcd_res, dcd_f_res, rv_res, meg_res,
        itv_diag, run_meg,
    )

    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(html)

    return FullReport(
        path=path,
        diagnosis=diag,
        dcd_results=dcd_res,
        dcd_f_results=dcd_f_res,
        rv_results=rv_res,
        meg_results=meg_res,
        interventions=itv_diag,
    )


# ---------------------------------------------------------------------------
# HTML construction
# ---------------------------------------------------------------------------

def _build_html(
    model, diag, diag_b64, z_threshold,
    dcd_res, dcd_f_res, rv_res, meg_res,
    itv_diag, run_meg,
) -> str:
    title  = _model_spec_str(model)
    s1     = _section_model(model)
    s2     = _section_diagnosis(diag, diag_b64, z_threshold)
    s3     = _section_formal_tests(
        model, dcd_res, dcd_f_res, rv_res, meg_res, run_meg
    )
    s4     = _section_interventions(itv_diag)
    s4_open = "open" if itv_diag.has_outliers else ""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Informe ART: {title}</title>
<style>
  body {{
    font-family: Arial, sans-serif;
    max-width: 1000px;
    margin: 2em auto;
    color: #222;
    line-height: 1.4;
  }}
  h1 {{ font-size: 1.3em; margin-bottom: 0.3em; }}
  details {{
    margin: 0.8em 0;
    border: 1px solid #ccc;
    border-radius: 4px;
    background: #fff;
  }}
  details > summary {{
    padding: 0.55em 1em;
    background: #eef2f7;
    cursor: pointer;
    font-size: 1.05em;
    font-weight: bold;
    border-radius: 3px 3px 0 0;
    user-select: none;
  }}
  details[open] > summary {{
    background: #dce7f5;
    border-bottom: 1px solid #ccc;
  }}
  .sec-body {{ padding: 0.8em 1em 1em 1em; }}
  table {{ border-collapse: collapse; font-size: 12px; margin-top: 0.4em; }}
  th, td {{ padding: 4px 10px; border: 1px solid #ccc; }}
  th {{ background: #eee; text-align: left; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .pass {{ color: #2a7a2a; font-weight: bold; }}
  .fail {{ color: #cc3333; font-weight: bold; }}
  .warn {{ color: #b35f00; font-weight: bold; }}
  .label {{ font-family: monospace; font-size: 11px; }}
  img {{ max-width: 100%; display: block; margin-top: 0.5em; }}
  p {{ margin: 0.3em 0; }}
</style>
</head>
<body>
<h1>Informe ART &mdash; {title}</h1>
<p style="font-size:0.9em;color:#666">n = {model.series.nobs} &nbsp;|&nbsp;
   &lambda; = {model.boxlam:.1f} &nbsp;|&nbsp;
   loglik = {model._result.loglik:.3f} &nbsp;|&nbsp;
   AIC = {model._result.aic:.2f} &nbsp;|&nbsp;
   BIC = {model._result.bic:.2f}</p>

{s1}
{s2}
{s3}
<details {s4_open}>
  <summary>4. Intervenciones</summary>
  <div class="sec-body">{s4}</div>
</details>

</body>
</html>"""


# ---------------------------------------------------------------------------
# Section 1 — Estimated model
# ---------------------------------------------------------------------------

def _section_model(model) -> str:
    names  = _param_names(model)
    params = np.asarray(model.params, dtype=float)
    se     = np.asarray(model.std_errors, dtype=float)
    tstat  = params / np.where(se > 0, se, np.nan)

    rows = []
    for nm, p, s, t in zip(names, params, se, tstat):
        sig = _sig_stars(abs(t))
        tc  = "fail" if abs(t) < 2.0 else ""
        rows.append(
            f"<tr><td class='label'>{nm}</td>"
            f"<td class='num'>{p:+.6f}</td>"
            f"<td class='num'>{s:.6f}</td>"
            f"<td class='num {tc}'>{t:+.3f} {sig}</td></tr>"
        )

    table = (
        "<table>"
        "<tr><th>Parámetro</th><th>Valor</th><th>SE</th><th>t-stat</th></tr>"
        + "".join(rows)
        + "</table>"
    )

    spec = _model_spec_str(model)
    return f"""<details open>
  <summary>1. Modelo estimado</summary>
  <div class="sec-body">
    <p><b>{spec}</b></p>
    {table}
    <p style="font-size:11px;color:#888;margin-top:0.5em">
      *** |t|&ge;3.3 &nbsp; ** |t|&ge;2.6 &nbsp; * |t|&ge;2.0 &nbsp;
      (aprox. 0.1%, 1%, 5% bilateral)
    </p>
  </div>
</details>"""


# ---------------------------------------------------------------------------
# Section 2 — Diagnosis
# ---------------------------------------------------------------------------

def _section_diagnosis(diag: DiagnosisResult, diag_b64: str, z_threshold: float) -> str:
    verdict_cls  = "pass" if diag.clean else "fail"
    verdict_text = "APROBADO ✓" if diag.clean else "REVISAR ✗"

    q_rows = "\n".join(
        "<tr><td class='num'>{}</td><td class='num'>{:.2f}</td>"
        "<td class='num' style='color:{}'>{:.4f}</td></tr>".format(
            lag, q, "#cc3333" if p < 0.05 else "#2a7a2a", p
        )
        for lag, q, p in zip(diag.q_lags, diag.q_stats, diag.q_pvalues)
    )
    q_table = (
        "<table><tr><th>Lag</th><th>Q</th><th>p-valor</th></tr>"
        + q_rows + "</table>"
    )

    jb_cls  = "pass" if diag.normal else "fail"
    jb_text = "Normal ✓" if diag.normal else "No normal ✗"
    jb_line = (
        f"<p>JB = {diag.jb_stat:.3f} &nbsp; p = {diag.jb_pvalue:.4f} &nbsp;"
        f"<span class='{jb_cls}'>{jb_text}</span> &nbsp;"
        f"asimetría = {diag.skewness:.3f} &nbsp; curtosis exceso = {diag.excess_kurtosis:.3f}</p>"
    )

    if diag.seasonal:
        seas_cls  = "fail" if diag.seasonal.seasonal_detected else "pass"
        seas_txt  = (
            f"<p>Estacionalidad residual: "
            f"<span class='{seas_cls}'>"
            f"{'Sí ✗' if diag.seasonal.seasonal_detected else 'No ✓'}</span>"
            f" (F={diag.seasonal.f_stat:.2f}, p={diag.seasonal.p_value:.4f})</p>"
        )
    else:
        seas_txt = ""

    if diag.extreme:
        ext_rows = "\n".join(
            f"<tr><td>{obs}</td><td class='num'>{z:+.3f}</td></tr>"
            for obs, z in diag.extreme[:15]
        )
        ext_block = (
            f"<p style='margin-top:0.6em'><b>Residuos extremos (|z| &gt; {z_threshold:.1f})</b></p>"
            "<table><tr><th>obs</th><th>z</th></tr>"
            + ext_rows + "</table>"
        )
    else:
        ext_block = f"<p>No hay residuos con |z| &gt; {z_threshold:.1f}.</p>"

    return f"""<details open>
  <summary>2. Diagnosis &mdash; <span class="{verdict_cls}">{verdict_text}</span></summary>
  <div class="sec-body">
    <img src="data:image/png;base64,{diag_b64}">
    <p style="margin-top:0.8em"><b>Contraste de ruido blanco (Ljung-Box Q)</b></p>
    {q_table}
    <p style="margin-top:0.6em"><b>Normalidad (Jarque-Bera)</b></p>
    {jb_line}
    {seas_txt}
    {ext_block}
  </div>
</details>"""


# ---------------------------------------------------------------------------
# Section 3 — Formal tests
# ---------------------------------------------------------------------------

def _section_formal_tests(
    model, dcd_res, dcd_f_res, rv_res, meg_res, run_meg
) -> str:
    blocks = []

    # DCD (MA regular)
    if dcd_res:
        blocks.append(_dcd_block("DCD — MA regular (H₀: θ=1)", dcd_res))

    # DCD_f (MA_f)
    if dcd_f_res:
        blocks.append(_dcd_block("DCD_f — MA estacional (H₀: λ₂=−1)", dcd_f_res))

    # RV
    if rv_res:
        blocks.append(_rv_block(rv_res))

    # MEG
    if meg_res:
        blocks.append(_meg_block(meg_res))
    elif run_meg and not _meg_suitable(model):
        blocks.append(
            "<p><i>MEG no aplica: el modelo tiene D=1 o no tiene armónicos.</i></p>"
        )

    if not blocks:
        body = "<p><i>Ningún contraste formal aplicable a esta especificación.</i></p>"
    else:
        body = "\n".join(blocks)

    return f"""<details open>
  <summary>3. Contrastes formales</summary>
  <div class="sec-body">{body}</div>
</details>"""


def _dcd_block(title: str, results: list[DCDResult]) -> str:
    rows = []
    for r in results:
        decision = _dcd_decision(r.lr)
        dcls = "pass" if decision == "No invertible" else "fail"
        rows.append(
            f"<tr><td class='num'>{r.factor_index + 1}</td>"
            f"<td class='num'>{r.coef_free:+.4f}</td>"
            f"<td class='num'>{r.loglik_free:.3f}</td>"
            f"<td class='num'>{r.loglik_constrained:.3f}</td>"
            f"<td class='num'><b>{r.lr:.3f}</b></td>"
            f"<td><span class='{dcls}'>{decision}</span></td></tr>"
        )
    table = (
        "<table>"
        "<tr><th>#</th><th>θ̂</th><th>loglik libre</th>"
        "<th>loglik restr.</th><th>LR</th><th>Decisión</th></tr>"
        + "".join(rows) + "</table>"
    )
    return f"<p style='margin-top:0.7em'><b>{title}</b></p>{table}"


def _dcd_decision(lr: float) -> str:
    # Cuadro 2.2 (Treadway): 10%=1.00/1.07, 5%=1.94/2.02, 1%=4.41/4.52
    if lr >= 1.94:
        return "Invertible ✓"
    return "No invertible ✗"


def _rv_block(results: list[RVResult]) -> str:
    rows = []
    for r in results:
        cls = "pass" if r.pvalue >= 0.05 else "fail"
        txt = "No rechaza ✓" if r.pvalue >= 0.05 else "Rechaza ✗"
        rows.append(
            f"<tr><td class='num'>{r.freq_hat:.3f}</td>"
            f"<td class='num'>{r.freq_null}</td>"
            f"<td class='num'>{r.lr:.3f}</td>"
            f"<td class='num {cls}'>{r.pvalue:.4f}</td>"
            f"<td><span class='{cls}'>{txt}</span></td></tr>"
        )
    table = (
        "<table>"
        "<tr><th>f̂</th><th>H₀: f=k</th><th>LR</th><th>p-valor</th><th>Decisión</th></tr>"
        + "".join(rows) + "</table>"
    )
    return f"<p style='margin-top:0.7em'><b>RV — frecuencia de AR(2)</b></p>{table}"


def _meg_block(results: list[MEGResult]) -> str:
    rows = []
    for r in results:
        if r.dcd_result is None or r.coef_ma_f is None:
            rows.append(
                f"<tr><td class='num'>{r.freq}</td>"
                f"<td colspan='4'><i>{r.status}</i></td></tr>"
            )
            continue
        lr   = r.dcd_result.lr
        stoc = r.stochastic
        cls  = "warn" if stoc else "pass"
        txt  = "Estocástica ⚠" if stoc else "Determinista ✓"
        rows.append(
            f"<tr><td class='num'>{r.freq}</td>"
            f"<td class='num'>{r.coef_ma_f:.4f}</td>"
            f"<td class='num'>{r.dcd_result.loglik_free:.3f}</td>"
            f"<td class='num'><b>{lr:.3f}</b></td>"
            f"<td><span class='{cls}'>{txt}</span></td></tr>"
        )
    table = (
        "<table>"
        "<tr><th>freq</th><th>MA_f coef</th><th>loglik</th>"
        "<th>LR (DCD_f)</th><th>Estacionalidad</th></tr>"
        + "".join(rows) + "</table>"
    )
    note = (
        "<p style='font-size:11px;color:#666;margin-top:0.4em'>"
        "Estocástica si LR &ge; 1.94 (5%); el analista decide antes de continuar "
        "con la siguiente frecuencia.</p>"
    )
    return f"<p style='margin-top:0.7em'><b>MEG — estacionalidad estocástica</b></p>{table}{note}"


# ---------------------------------------------------------------------------
# Section 4 — Interventions
# ---------------------------------------------------------------------------

def _section_interventions(itv: InterventionDiagnosis) -> str:
    if not itv.has_outliers:
        return (
            f"<p class='pass'>No se detectan residuos con "
            f"|z| &gt; {itv.threshold:.1f}.</p>"
        )

    rows = []
    for w in itv.outliers:
        lags_str = ", ".join(str(j) for j in w.acf_lags_affected) or "—"
        rows.append(
            f"<tr><td>{w.date}</td>"
            f"<td class='num'>{w.z:+.3f}</td>"
            f"<td class='num'>{100*w.variance_fraction:.1f}%</td>"
            f"<td class='label'>{lags_str}</td></tr>"
        )
    table = (
        "<table>"
        "<tr><th>Fecha</th><th>z</th><th>var%</th><th>Lags ACF afectados</th></tr>"
        + "".join(rows) + "</table>"
    )

    warn_jb = (
        "<p class='warn'>⚠ Jarque-Bera no es robusto a anomalías aisladas — "
        "interpretar con cautela.</p>"
        if itv.jb_unreliable else ""
    )
    warn_q = (
        "<p class='warn'>⚠ Ljung-Box Q no es robusto a anomalías aisladas — "
        "interpretar con cautela.</p>"
        if itv.q_unreliable else ""
    )
    return (
        f"<p><b>{len(itv.outliers)} residuo(s) extremo(s) "
        f"(|z| &gt; {itv.threshold:.1f})</b></p>"
        + table + warn_jb + warn_q
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SUBS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def _sub(n: int) -> str:
    return str(n).translate(_SUBS)


def _itv_label(itv, idx: int) -> str:
    t = itv.type
    h = getattr(itv, "harmonic", None)
    if t in ("cos", "sin") and h is not None:
        return f"{t}({int(h)})"
    if t == "alter":
        return "alter"
    suffix = _sub(idx + 1) if idx > 0 else ""
    return f"{t}{suffix}"


def _param_names(model) -> list[str]:
    names = []
    counts: dict[str, int] = {}

    def _itv_lbl(itv):
        t = itv.type
        idx = counts.get(t, 0)
        counts[t] = idx + 1
        return _itv_label(itv, idx)

    for itv in (model.interventions or []):
        label = _itv_lbl(itv)
        for j, free in enumerate(itv.omega_free or []):
            if free:
                suf = _sub(j) if j > 0 else ""
                names.append(f"ω{suf}({label})")

    counts.clear()
    for itv in (model.interventions or []):
        label = _itv_lbl(itv)
        for j, free in enumerate(itv.delta_free or []):
            if free:
                names.append(f"δ{_sub(j+1)}({label})")

    def _add_arma(factors, free_lists, prefix):
        for i, factor in enumerate(factors or []):
            fl = (free_lists[i]
                  if free_lists and i < len(free_lists) else None)
            for j in range(len(factor)):
                if fl is None or fl[j]:
                    names.append(f"{prefix}{_sub(j+1)}")

    _add_arma(model.ar,   model.ar_free,   "φ")
    _add_arma(model.ar_s, model.ar_s_free, "Φ")
    _add_arma(model.ma,   model.ma_free,   "θ")
    _add_arma(model.ma_s, model.ma_s_free, "Θ")

    for ff in (model.ar_f or []):
        if ff.free:
            names.append(f"AR_f[{ff.freq}]")
    for ff in (model.ma_f or []):
        if ff.free:
            names.append(f"MA_f[{ff.freq}]")

    if getattr(model, "estimate_mu", False):
        names.append("μ")

    return names


def _model_spec_str(model) -> str:
    p = sum(len(f) for f in (model.ar   or []))
    q = sum(len(f) for f in (model.ma   or []))
    P = sum(len(f) for f in (model.ar_s or []))
    Q = sum(len(f) for f in (model.ma_s or []))
    s = model.series.freq
    d = model.d
    D = model.D
    return f"ARIMA({p},{d},{q})({P},{D},{Q}){_sub(s)}"


def _meg_suitable(model) -> bool:
    if getattr(model, "D", 1) != 0:
        return False
    itv_types = {itv.type for itv in (model.interventions or [])}
    return bool(itv_types & {"cos", "sin", "alter"})


def _sig_stars(absT: float) -> str:
    if absT >= 3.3:
        return "***"
    if absT >= 2.6:
        return "**"
    if absT >= 2.0:
        return "*"
    return ""


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def _try(fn, default):
    try:
        return fn()
    except Exception:
        return default
