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

import numpy as np
import numpy as _np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import art
from .identification import (
    boxcox_selection, plot_boxcox_selection,
    identification_listing, save_identification_report,
    apply_differences, boxcox_transform, transform_label,
    _listing_figure,
    unit_root_tests, recommended_d, UnitRootResult,
)
from .seasonal_detection import detect_seasonality, plot_seasonality
from .model_detection import suggest_orders
from .diagnosis import diagnose, plot_diagnosis
from .formal_tests import (dcd, dcd_f, rv, meg, shin_fuller, dcd_overdiff_regular,
                            dcd_underdiff_regular)
from .interventions import diagnose_interventions
from .full_report import _meg_suitable, _try

# ── pyfug integration ─────────────────────────────────────────────────────────
# pyfug is the primary graphics engine for standard plots (series+ACF/PACF,
# histogram, mean-deviation). Internal ART matplotlib figures are kept only for
# specialized plots (unit-root coloured table, ACF contribution bars, etc.).
try:
    from pyfug.graphics import plot_combined as _pyfug_combined
    from pyfug.graphics import plot_histogram as _pyfug_histogram
    from pyfug.graphics import plot_mean_deviation_pair as _pyfug_mdt_pair
    from pyfug.core import Tseries as _Tseries
    _PYFUG = True
except ImportError:
    _PYFUG = False


def _pyfug_ts(data, freq: int, start: tuple, name: str = "") -> "_Tseries":
    """Wrap a numpy array (or fue TimeSeries .data) as a pyfug Tseries."""
    arr = np.asarray(data, dtype=float)
    begyear, begtime = int(start[0]), int(start[1])
    return _Tseries(name=name, freq=freq, nobs=len(arr),
                    begyear=begyear, begtime=begtime, data=arr)


def _pyfug_from_fue(ts) -> "_Tseries":
    """Convert a fue TimeSeries to pyfug Tseries."""
    return _pyfug_ts(ts.data, ts.freq, ts.start, name=ts.name or "")


def _resid_start(model) -> tuple:
    """Compute the correct calendar start for model.residuals.

    fue's TimeSeries.residuals doesn't propagate the series start, so we
    derive it: the first residual corresponds to the first observation of
    the original series that survives d regular differences and D seasonal
    differences (total n_lost = d + D*freq observations lost from the front).
    """
    s0   = model.series.start
    freq = model.series.freq if model.series.freq > 0 else 1
    n_skip = model.d + model.D * freq
    off    = (int(s0[1]) - 1) + n_skip
    return (int(s0[0]) + off // freq, off % freq + 1)


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
    result = boxcox_selection(ts)
    if _PYFUG:
        pf = _pyfug_from_fue(ts)
        fig = _pyfug_mdt_pair(pf, name=ts.name or "")
    else:
        fig = plot_boxcox_selection(ts)
    b64 = _fig_b64(fig)
    plt.close(fig)

    s = result.name or ts.name or "series"
    n = ts.nobs

    # BUG-0059. Esto devolvía `abs(...)` y el signo se perdía antes de imprimirse.
    # El MÓDULO es el criterio correcto --se elige la escala cuya dependencia
    # media-dispersión está más cerca de cero-- pero el SIGNO es el diagnóstico, y
    # dice cosas opuestas:
    #
    #   corr > 0  la dispersión CRECE con el nivel → INFRA-transformado
    #   corr < 0  la dispersión CAE con el nivel   → SOBRE-transformado
    #
    # Y lo que de verdad se perdía es el caso de signos OPUESTOS. Sobre PGAS,
    # λ=1 da +0.150 y λ=0 da −0.173: una escala se queda corta y la otra se pasa,
    # así que la λ correcta está ENTRE las dos. Impreso en valor absoluto sale
    # «0.150 frente a 0.173, diferencia 0.024, decisión ambigua, las dos son
    # razonables» — que es falso: ninguna de las dos lo es.
    def _corr(mdt):
        x, y = np.array(mdt.means_std), np.array(mdt.stds_std)
        if x.std() < 1e-10 or y.std() < 1e-10:
            return 0.0
        return float(np.corrcoef(x, y)[0, 1])

    corr_raw_s = _corr(result.mdt_raw)      # con signo, para diagnosticar
    corr_log_s = _corr(result.mdt_log)
    corr_raw = abs(corr_raw_s)              # módulo, para decidir
    corr_log = abs(corr_log_s)
    horquilla = (corr_raw_s * corr_log_s < 0
                 and min(abs(corr_raw_s), abs(corr_log_s)) > 0.05)
    gap      = corr_raw - corr_log          # >0 → log mejor
    ambiguous = abs(gap) < 0.10
    prefers_log = corr_log < corr_raw
    rec_lam = 0.0 if prefers_log else 1.0
    rec_str = "log (λ=0)" if prefers_log else "identidad (λ=1)"

    def _lectura(c):
        if c > 0.05:
            return "la dispersión CRECE con el nivel → se queda corta"
        if c < -0.05:
            return "la dispersión CAE con el nivel → se pasa"
        return "sin dependencia apreciable"

    lines = [
        f"## Box-Cox — {s}  (n={n})",
        f"- Correlación media-std con λ=1 (original): **{corr_raw_s:+.3f}** "
        f"— {_lectura(corr_raw_s)}",
        f"- Correlación media-std con λ=0 (log):      **{corr_log_s:+.3f}** "
        f"— {_lectura(corr_log_s)}",
        f"- Recomendación: **{rec_str}**",
    ]

    if horquilla:
        lines += [
            "",
            "> ⚠ **Los dos signos son OPUESTOS: la λ correcta está ENTRE las "
            f"dos.** Con λ=1 la dispersión crece con el nivel ({corr_raw_s:+.3f}) "
            f"y con λ=0 cae ({corr_log_s:+.3f}): una escala se queda corta y la "
            "otra se pasa. Eso NO es «las dos son razonables» — es que ninguna "
            "de las dos anula la dependencia, y elegir por el módulo más pequeño "
            "es arbitrario.",
            ">",
            "> La suite sólo ofrece λ∈{0, 1}, así que la decisión no la cierra "
            "este estadístico: la cierra el DOMINIO de la serie. Un índice de "
            "precios o una magnitud multiplicativa van a λ=0 aunque el módulo "
            "favorezca marginalmente a λ=1, porque un modelo en niveles no tiene "
            "escala interpretable (ver `policy.decide_lambda` y BUG-0040).",
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
            "corr_raw": corr_raw,            # módulo: es lo que decide
            "corr_log": corr_log,
            "corr_raw_signed": corr_raw_s,   # signo: es lo que diagnostica
            "corr_log_signed": corr_log_s,
            "horquilla": horquilla,          # signos opuestos → λ entre 0 y 1
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
            "- D=0, con armónicos cos/sin en **TODAS** las frecuencias, f=1..s/2.",
            "- Los armónicos absorben el patrón estacional fijo (igual cada año).",
            "- MEG (etapa 3, tras estimar) validará si alguna frecuencia es",
            "  estocástica y conviene pasar a B2.",
            "",
            "⚠ **La lista de frecuencias significativas de arriba es DESCRIPTIVA, no",
            "  una regla de selección.** No se omite el armónico de una frecuencia",
            "  porque el HAC no la marque, y menos aquí:",
            "  - el modelo nulo del MEG en la frecuencia f **es** el armónico",
            "    determinista en f. Si no se pone, esa frecuencia deja de ser una",
            "    pregunta: no se puede contrastar lo que no está;",
            "  - un estadístico bajo en f es evidencia **a favor** de estacionalidad",
            "    estocástica en f — amplitud que vaga y promedia hacia cero—, que es",
            "    justo lo que el MEG viene a decidir;",
            "  - y en este punto no hay nada estimado: el único criterio disponible",
            "    procede de un modelo sin ARMA, cuyos errores estándar están",
            "    inflados por la dinámica sin modelar.",
            "  La poda, si procede, va DESPUÉS del MEG y sobre un modelo adecuado.",
            "",
            "**Decisión B2 — estacionalidad multiplicativa (tradición Box-Jenkins).**",
            "- D=1: diferencia estacional ∇_s elimina el patrón estacional.",
            "- Sin armónicos cos/sin; usar AR_s / MA_s para la estructura seasonal.",
            "- Modelo: SARIMA(p,d,q)(P,1,Q)_s — elegir P, Q en la identificación.",
            "- Adoptar si MEG confirma estacionalidad estocástica, o directamente",
            "  si la tradición B-J original es preferida.",
        ]

    if not d_ok:
        if det:
            # BUG-0023: la estacionalidad acaba de detectarse TRES LÍNEAS más
            # arriba, en este mismo bloque. La regresión del ADF no lleva
            # términos estacionales, así que el patrón cae en su varianza
            # residual, infla el error típico del coeficiente y sesga el
            # contraste hacia NO rechazar la raíz unitaria — que se lee como
            # «vuelve a diferenciar». Emitir «Considera d=2» aquí es tomar la
            # contaminación por evidencia.
            lines += [
                "",
                "ℹ El ADF sobre ∇y no rechaza, pero **eso no es evidencia de "
                "d=2 aquí**: la estacionalidad que se acaba de detectar no entra "
                "en la regresión del ADF, cae en su varianza residual y sesga el "
                "contraste hacia no rechazar. Primero se trata la estacionalidad "
                "(D y/o armónicos); el orden de integración se decide después, y "
                "el contraste que vale sobre el modelo estimado es Shin-Fuller.",
            ]
        else:
            lines += [
                "",
                "⚠ Los tests de raíz unitaria sugieren que ∇log(y) puede no ser "
                "estacionaria. Considera d=2.",
            ]

    if decision == "B1":
        rec = (
            "Decisión B1 por defecto — estacionalidad determinista. Confirma D=0 "
            "con armónicos. MEG validará si alguna frecuencia requiere D=1 más adelante. "
            "Alternativa: pasar a B2 (estacionalidad estocástica, D=1) directamente."
        )
    elif decision == "A":
        rec = "Decisión A. Confirma D=0, sin armónicos."
    else:
        rec = f"Decisión {decision}."
    rec += " Siguiente paso: listado de identificación (p, q)."

    return Description(
        summary="\n".join(lines),
        figure_b64=b64,
        recommendation=rec,
        data={
            "seasonal_detected": det,
            "decision": decision,
            "f_stat": result.f_stat,
            "p_value": result.p_value,
            "recommended_D": 0,
            "multiplicative_available": det,
            "d_stationary": d_ok,
            "significant_frequencies": [fr.freq_idx for fr in freqs if fr.p_value < 0.05],
        },
    )


# ---------------------------------------------------------------------------
# Unit root tests (Bloque L)
# ---------------------------------------------------------------------------

def describe_unit_root(ts, lam: float = 0.0, max_d: int = 2) -> Description:
    """
    Run ADF + KPSS for d=0…max_d and return a coloured summary table.

    Returns a Description with:
      summary      — markdown table of test statistics and verdicts
      figure_b64   — matplotlib coloured table (one row per d level)
      recommendation — recommended d with reasoning
      data         — list of per-level dicts + recommended_d
    """
    results = unit_root_tests(ts, lam=lam, max_d=max_d)
    rec_d   = recommended_d(results)

    # ¿Cuánto de la serie ES la tendencia? R² de una recta sobre el nivel
    # transformado. Es evidencia, no decisión: la política la usa para dudar de
    # un `recommended_d = 0` sobre una serie que sube (BUG-0016), y la fracción
    # de varianza explicada es lo que corresponde a "observar el gráfico" —
    # una pendiente puede ser significativa y no dominar nada. Medido: las
    # series anuales de precipitación de Cycles, que son I(0), dan 0.076 y
    # 0.035 con pendiente HAC significativa; IPC_ES da 0.910.
    _yv = np.asarray(ts.data, float)
    _z = np.log(np.where(_yv > 0, _yv, np.nan)) if lam == 0.0 else _yv
    trend_r2 = 0.0
    if _z.size >= 3 and np.all(np.isfinite(_z)):
        _t = np.arange(_z.size, dtype=float)
        _fit = np.polyval(np.polyfit(_t, _z, 1), _t)
        _sst = float(((_z - _z.mean()) ** 2).sum())
        if _sst > 0:
            trend_r2 = float(1.0 - ((_z - _fit) ** 2).sum() / _sst)

    _VERDICT_ES = {
        "stationary": "estacionaria ✓",
        "unit_root":  "raíz unitaria ✗",
        "ambiguous":  "ambiguo ⚠",
    }
    _COLOR = {
        "stationary": "#c8e6c9",   # light green
        "unit_root":  "#ffcdd2",   # light red
        "ambiguous":  "#fff9c4",   # light yellow
    }

    # --- markdown summary -----------------------------------------------
    lines = [
        "## Especificación inicial de d — ADF + KPSS",
        "",
        "> Herramientas de especificación exploratorias (al nivel de gráficos y ACF).",
        "> El contraste formal sobre el modelo estimado es Shin-Fuller (1998),",
        "> que se aplica en la fase de contrastes formales tras la estimación.",
        "",
    ]
    lines.append(
        "| d | Serie | n | ADF t | ADF p | ADF | KPSS η | KPSS p | KPSS | Veredicto |"
    )
    lines.append("|---|-------|---|-------|-------|-----|--------|--------|------|-----------|")
    for r in results:
        adf_v  = "✓" if r.adf_rejects  else "✗"
        kpss_v = "✓" if not r.kpss_rejects else "✗"
        lines.append(
            f"| {r.d} | {r.label} | {r.n} |"
            f" {r.adf_stat:+.3f} | {r.adf_pvalue:.4f} | {adf_v} |"
            f" {r.kpss_stat:.3f} | {r.kpss_pvalue:.4f} | {kpss_v} |"
            f" {_VERDICT_ES[r.verdict]} |"
        )

    # BUG-0056. Esta herramienta es la CAPA DE EVIDENCIA y `recommended_d`
    # informa de lo que los contrastes encuentran, en crudo. El tope de la
    # escuela --un paso cada vez, y la estacionalidad acota d-- vive en
    # `policy.decide_d`, y así está por diseño: el `.data` sigue crudo para que
    # la política no lo tope dos veces.
    #
    # Lo que estaba mal es que el TEXTO hablaba con voz de recomendación: «d = 2»
    # y «Usa d=2», sin mencionar el tope ni que la estacionalidad todavía no se
    # ha contrastado. Un analista que llama a esta herramienta directamente
    # --los dos carriles del RUN 3 lo hicieron-- se salta la capa de política sin
    # enterarse, y vuelve a caer en el salto d=0→2 que BUG-0016 y BUG-0023
    # arreglaron aguas abajo. Sobre RATIO: d=0 con raíz unitaria, d=1 AMBIGUO,
    # d=2 estacionaria → recomendaba 2, saltándose la duda entera.
    from art.policy import decide_d as _decide_d
    _rec_pol = _decide_d({"recommended_d": rec_d, "trend_r2": trend_r2},
                         seasonal=None, current_d=0, max_step=1)

    _que_es = ("serie ya estacionaria en niveles" if rec_d == 0 else
               "primera diferencia con consenso" if rec_d == 1 else
               f"{rec_d} diferencias hasta el consenso")
    lines += [
        "",
        f"**Lo que encuentran los contrastes**: d = {rec_d} ({_que_es}).",
    ]
    if _rec_pol != rec_d:
        _salto = [r.verdict for r in results if 0 < r.d < rec_d]
        lines += [
            "",
            f"> ⚠ **Punto de partida recomendado: d = {_rec_pol}, no {rec_d}.** "
            f"Un paso cada vez. Desde d=0 la pregunta que los contrastes "
            f"responden es «¿hace falta AL MENOS una diferencia?», no «cuántas»: "
            f"saltar a d={rec_d} contesta una pregunta que nadie ha hecho"
            + (f", y de paso se salta el d=1 que sale «"
               f"{_VERDICT_ES.get(_salto[0], _salto[0])}»" if _salto else "") + ".",
            ">",
            "> Y la estacionalidad **todavía no se ha contrastado**. La regresión "
            "del ADF no lleva términos estacionales, así que un patrón estacional "
            "fuerte se le va a la varianza residual y sesga el contraste hacia NO "
            "rechazar la raíz unitaria — que se lee como «diferencia otra vez».",
            ">",
            "> No se pierde nada empezando bajo: esto es especificación INICIAL. "
            "El contraste de verdad sobre el orden de integración llega al final, "
            "sobre un modelo adecuado, con `formal_tests` (Shin-Fuller y el DCD "
            "de sobrediferenciación).",
        ]
    lines += [
        "",
        "ADF H₀: raíz unitaria — rechazar (✓) indica estacionariedad.",
        "KPSS H₀: estacionariedad — no rechazar (✓) indica estacionariedad.",
    ]

    # --- figure: coloured matplotlib table --------------------------------
    if results:
        col_labels = ["d", "Serie", "n",
                      "ADF t", "ADF p", "ADF",
                      "KPSS η", "KPSS p", "KPSS",
                      "Veredicto"]
        rows, colors = [], []
        for r in results:
            adf_v  = "✓" if r.adf_rejects      else "✗"
            kpss_v = "✓" if not r.kpss_rejects  else "✗"
            rows.append([
                str(r.d), r.label, str(r.n),
                f"{r.adf_stat:+.3f}", f"{r.adf_pvalue:.4f}", adf_v,
                f"{r.kpss_stat:.3f}", f"{r.kpss_pvalue:.4f}", kpss_v,
                _VERDICT_ES[r.verdict],
            ])
            bg = _COLOR[r.verdict]
            colors.append([bg] * len(col_labels))

        fig_h = max(1.8, 0.55 * len(results) + 0.8)
        fig, ax = plt.subplots(figsize=(10, fig_h))
        ax.axis("off")
        tbl = ax.table(
            cellText=rows,
            colLabels=col_labels,
            cellColours=colors,
            loc="center",
            cellLoc="center",
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(9)
        tbl.auto_set_column_width(list(range(len(col_labels))))
        # Style header row
        for j in range(len(col_labels)):
            tbl[0, j].set_facecolor("#455a64")
            tbl[0, j].set_text_props(color="white", fontweight="bold")
        fig.tight_layout()
        b64 = _fig_b64(fig)
        plt.close(fig)
    else:
        b64 = None

    # --- recommendation ---------------------------------------------------
    verdicts = {r.d: r.verdict for r in results}
    if rec_d == 0 and verdicts.get(0) == "stationary":
        rec_text = (
            "La serie en niveles (d=0) es estacionaria según ADF y KPSS. "
            "Procede con d=0."
        )
    elif verdicts.get(rec_d) == "stationary":
        if _rec_pol != rec_d:
            # BUG-0056: «Usa d=2» era una instrucción, y salteaba el tope.
            rec_text = (
                f"Los contrastes llegan a la estacionariedad en d={rec_d}, pero "
                f"el punto de partida es d={_rec_pol}: un paso cada vez, y la "
                f"estacionalidad aún no se ha contrastado (contamina el ADF hacia "
                f"NO rechazar). Empieza en d={_rec_pol} y deja el orden de "
                f"integración para `formal_tests`, sobre el modelo estimado."
            )
        else:
            rec_text = (
                f"La serie con d={rec_d} diferencia(s) es estacionaria. "
                f"Usa d={rec_d}."
            )
    elif any(r.verdict == "ambiguous" for r in results):
        rec_text = (
            f"Resultados ambiguos. La inspección visual del ACF (listado de "
            f"identificación) es necesaria para confirmar d={rec_d}."
        )
    else:
        rec_text = (
            f"No se detectó estacionariedad hasta d={max_d}. "
            "Revisa la serie: posible varianza no estacionaria o outliers."
        )

    return Description(
        summary="\n".join(lines),
        figure_b64=b64,
        recommendation=rec_text,
        data={
            "recommended_d": rec_d,          # CRUDO: la política lo topa (BUG-0056)
            "recommended_d_policy": _rec_pol,
            "trend_r2": trend_r2,
            "results": [
                {
                    "d": r.d, "label": r.label, "n": r.n,
                    "adf_stat": r.adf_stat, "adf_pvalue": r.adf_pvalue,
                    "adf_rejects": r.adf_rejects,
                    "kpss_stat": r.kpss_stat, "kpss_pvalue": r.kpss_pvalue,
                    "kpss_rejects": r.kpss_rejects,
                    "verdict": r.verdict,
                }
                for r in results
            ],
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
        # BUG-0049. Un candidato DISPERSO --AR o MA con un solo coeficiente, en
        # el retardo k, y los anteriores en cero-- se enumeraba con la misma
        # etiqueta que el completo del mismo orden. Sobre ∇ln PGAS eso imprimía
        # `ARIMA(2,1,0)(0,0,0)_4` DOS VECES, con similitudes distintas (0.755 y
        # 0.733) y siendo modelos distintos: el disperso φ₂ solo, y el completo
        # φ₁ y φ₂. Y el disperso salía ANTES, de modo que quien pidiera «el AR(2)
        # de la lista» se llevaba el que no creía estar pidiendo.
        disperso = []
        if getattr(sp, "sparse_ar_lag", 0):
            disperso.append(f"AR sólo en B^{sp.sparse_ar_lag}")
        if getattr(sp, "sparse_ma_lag", 0):
            disperso.append(f"MA sólo en B^{sp.sparse_ma_lag}")
        sufijo = f"  [{', '.join(disperso)}]" if disperso else ""
        lines.append(
            f"{marker} {i}. ARIMA({sp.p},{sp.d},{sp.q})({sp.P},{sp.D},{sp.Q})_{sp.s}"
            f"{sufijo}  sim={sp.similarity:.3f}  —  {label}"
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

    top_sp  = specs[0] if specs else None
    rec_P   = top_sp.P if top_sp else 0
    rec_Q   = top_sp.Q if top_sp else 0

    if D == 0:
        seasonal_note = "Añade armónicos cos/sin (n_harmonics=freq//2) en confirm_and_estimate."
    else:
        if rec_P > 0 or rec_Q > 0:
            seasonal_note = (
                f"D=1: sin armónicos. Usa P={rec_P}, Q={rec_Q} "
                f"(AR_s/MA_s) en confirm_and_estimate."
            )
        else:
            seasonal_note = "D=1: sin armónicos. Especifica P, Q en confirm_and_estimate."

    if ambiguous:
        sp0, sp1 = specs[0], specs[1]
        rec = (
            f"Decisión ambigua entre SARIMA({sp0.p},{d},{sp0.q})({sp0.P},{D},{sp0.Q}) y "
            f"SARIMA({sp1.p},{d},{sp1.q})({sp1.P},{D},{sp1.Q}). "
            f"Estima ambos y elige por AIC/BIC y diagnosis de residuos. "
            + seasonal_note
        )
    else:
        rec = (
            f"Confirma SARIMA({rec_p},{d},{rec_q})({rec_P},{D},{rec_Q})_{specs[0].s if specs else ''}"
            f" como punto de partida. "
            f"Revisa la figura ACF/PACF antes de estimar. "
            + seasonal_note
        )

    # ACF/PACF figure at the chosen (d, D) level via pyfug (primary) or internal fallback.
    # pyfug plot_combined operates on ser.data directly (no internal differencing), so we
    # apply the transform and differences here and pass the already-differenced series.
    b64_ident = None
    try:
        if _PYFUG:
            z     = boxcox_transform(np.array(ts.data), lam)
            w     = apply_differences(z, ts.freq, d, D)
            # Compute start of differenced series
            orig  = getattr(ts, "start", (1, 1))
            n_skip = d + D * ts.freq          # observations lost
            off    = (int(orig[1]) - 1) + n_skip
            new_start = (int(orig[0]) + off // ts.freq, off % ts.freq + 1)
            name_w = transform_label(lam, d, D, ts.freq, name=ts.name or "")
            pf     = _pyfug_ts(w, ts.freq, new_start, name=name_w)
            fig    = _pyfug_combined(pf, title=name_w)
            b64_ident = _fig_b64(fig)
            plt.close(fig)
        else:
            listing = identification_listing(ts, lam=lam, max_d=d, max_D=D)
            start   = getattr(ts, "start", (1, 1))
            if D == 0:
                panels = listing.panels
            else:
                n_per_D = d + 1
                panels  = listing.panels[n_per_D:]
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
    from fue.forecast import _reconstruct_params

    # Estimated point values and standard errors, unpacked by the SINGLE canonical
    # unpacker (fue._reconstruct_params) — once for model.params, once for
    # model.std_errors — then laid out in the exact order the display consumes them.
    # So the (value, SE) rendered under each term is aligned by construction and never
    # depends on the flat-vector packing order matching the render order (the old
    # positional cursor desynced e.g. AR_f-before-MA, or omega/delta interleaving).
    # See ART_MCP_REVIEW.md §1.
    vals = _reconstruct_params(model, list(model.params))
    sers = _reconstruct_params(model, list(model.std_errors))

    def _flags(obj, attr, n):
        fl = getattr(obj, attr, None)
        return list(fl) if fl else [True] * n

    _seq = []   # (value, se) pairs in render order (interventions → AR/AR_f → MA/MA_f → mu)
    for j, itv in enumerate(model.interventions or []):
        om = list(itv.omega) if itv.omega else []
        for pos, fr in enumerate(_flags(itv, "omega_free", len(om))):
            if fr:
                _seq.append((vals[0][j][pos], sers[0][j][pos]))
        dl = list(itv.delta) if itv.delta else []
        for pos, fr in enumerate(_flags(itv, "delta_free", len(dl))):
            if fr:
                _seq.append((vals[1][j][pos], sers[1][j][pos]))

    def _push_factors(cv, cs, factors, free_lists):
        for i, fac in enumerate(factors or []):
            fl = free_lists[i] if free_lists and i < len(free_lists) else [True] * len(fac)
            for pos in range(len(fac)):
                if fl[pos]:
                    _seq.append((cv[i][pos], cs[i][pos]))

    _push_factors(vals[2], sers[2], model.ar,   model.ar_free)
    _push_factors(vals[3], sers[3], model.ar_s, model.ar_s_free)
    for i, ff in enumerate(model.ar_f or []):
        if ff.free:
            _seq.append((vals[6][i], sers[6][i]))
    _push_factors(vals[4], sers[4], model.ma,   model.ma_free)
    _push_factors(vals[5], sers[5], model.ma_s, model.ma_s_free)
    for i, ff in enumerate(model.ma_f or []):
        if ff.free:
            _seq.append((vals[7][i], sers[7][i]))
    if model.estimate_mu:
        _seq.append((vals[8], sers[8]))

    class _PI:
        def __init__(self):
            self.i = 0
        def pop(self):
            if self.i >= len(_seq):
                return 0.0, 0.0
            vse = _seq[self.i]
            self.i += 1
            return vse

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

    # BUG-0060. Un error típico que es la semilla del BFGS se imprimía con el
    # MISMO formato que uno válido, y el aviso iba debajo del bloque. Sobre
    # ITCER_m00mu eso publicaba μ=−0.7202 (0.1552) → t=−4.64, cuando el honesto
    # (σ̂ₐ/√n = 0.2966) da t=−2.43: de abrumador a justo significativo, que es la
    # diferencia entre incluir la media y no incluirla.
    #
    # Se marcan por VALOR, no por índice: la semilla es √(2/n) y los índices de
    # `degenerate_variance_indices` van sobre el vector plano, cuyo orden no es
    # el de render (el propio módulo avisa de ese desajuste).
    try:
        from art.diagnosis import bfgs_seed_var as _seed
        _sv = _seed(getattr(model, "_result", None))
        _se_semilla = (_sv ** 0.5) if _sv else None
    except Exception:
        _se_semilla = None
    _hay_semilla = [False]

    def _es_semilla(se: float) -> bool:
        if _se_semilla is None or not se:
            return False
        return abs(abs(se) - _se_semilla) <= 1e-4 * _se_semilla

    def _fse(se: float) -> str:
        a = abs(se)
        if a == 0:
            return ""
        if _es_semilla(se):
            _hay_semilla[0] = True
            return f"(✗{se:.4f})"
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

    def _sub(n: int) -> str:
        sub_map = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
        return str(n).translate(sub_map)

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
            parts.append(f"∇{_sub(freq)}")
        elif D > 1:
            parts.append(f"∇{_sub(freq)}{_sup(D)}")
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

        def add(self, text: str, se: str = "", align_dot: bool = False):
            """
            Append text to value line.
            If se given, write it into se line. By default it starts at the
            column where this text begins; with align_dot=True the SE is shifted
            so its decimal point sits directly under the coefficient's decimal
            point (both value and se must contain a '.').
            """
            col = len(self.v)   # current position in value line
            self.v += list(text)
            # Ensure s has at least col+len(text) spaces
            while len(self.s) < col + len(text):
                self.s.append(" ")
            if se:
                se_col = col
                if align_dot and "." in text and "." in se:
                    se_col = col + text.index(".") - se.index(".")
                    if se_col < 0:
                        se_col = 0
                for i, c in enumerate(se):
                    pos = se_col + i
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
            tl.add(v_str, _fse(se), align_dot=True)  # coef + SE (dots aligned)
            tl.add(bpow)                 # B^k (no SE)
        tl.add(")")
        return tl.val(), tl.se_line()

    # ── Part 1: Deterministic component Dₜ ───────────────────────────────

    harm_rows: list[tuple[str, str]] = []   # harmonics (cos/sin/alter)
    itv_rows:  list[tuple[str, str]] = []   # interventions (step/pulse/...)

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

            dlt   = list(itv.delta) if itv.delta else []
            dlt_f = (list(itv.delta_free)
                     if (hasattr(itv, "delta_free") and itv.delta_free)
                     else [True] * len(dlt))

            if len(om) == 1:
                v, se = (pi.pop() if om_f[0] else (om[0], 0.0))
                tl = _TwoLine()
                tl.add(f"  {_sign_det(v)} ")
                tl.add(_fv(abs(v)), _fse(se) if om_f[0] else "", align_dot=True)
                if dlt:
                    # Transfer function: ω / δ(B) · ξₜ
                    # _fmt_poly advances pi past the delta params (keeping alignment)
                    den_val, den_se = _fmt_poly(dlt, dlt_f)
                    tl.add(" / ")
                    tl.add(den_val, den_se)
                tl.add(f" {xi_str}")
                itv_rows.append((tl.val(), tl.se_line()))
            else:
                tl = _TwoLine()
                tl.add("  + (")
                for i, (v0, free) in enumerate(zip(om, om_f)):
                    v, se = (pi.pop() if free else (v0, 0.0))
                    if i == 0:
                        tl.add(_fv(v), _fse(se) if free else "", align_dot=True)
                    else:
                        bpow = "·B" if i == 1 else f"·B{_sup(i)}"
                        tl.add(f"  {_sign_det(v)} ")
                        tl.add(_fv(abs(v)), _fse(se) if free else "", align_dot=True)
                        tl.add(bpow)
                if dlt:
                    den_val, den_se = _fmt_poly(dlt, dlt_f)
                    tl.add(") / ")
                    tl.add(den_val, den_se)
                    tl.add(f" {xi_str}")
                else:
                    tl.add(f") {xi_str}")
                itv_rows.append((tl.val(), tl.se_line()))

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
            tl.add(_fv(abs(v)), _fse(se) if free else "", align_dot=True)
            tl.add(f" {label}")
            first = False
        harm_rows.append((tl.val(), tl.se_line()))

    # Order: harmonics first (matching .inp order), then interventions
    det_rows = harm_rows + itv_rows

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
        """AR_f / MA_f fixed-frequency quadratic factors. A fitted model already
        stores the invertible MA_f root (normalize_ma_invertibility in fue.Model.fit),
        so the shown coef is invertible without a report-time flip."""
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

    # Los factores `ifadf` NO van a `left_blocks` (BUG-0012). Son DIFERENCIACIÓN,
    # igual que ∇ y ∇_s, así que van dentro del paréntesis de μ: μ es la media de
    # la variable COMPLETAMENTE diferenciada. Fuera del paréntesis la ecuación
    # impresa dice A_f(B)·(∇Nₜ − μ), cuya media es A_f(1)·(m − μ) ≠ 0 — es decir,
    # no es el modelo que se ajustó.
    ifadf_blocks: list[tuple[str, str]] = []
    if getattr(model, "ifadf", None):
        _add_ifadf_blocks(ifadf_blocks, model.ifadf)
    ifadf_s = "".join(f"{v} " for v, _ in ifadf_blocks)

    _add_arma_blocks(right_blocks, model.ma or [],  model.ma_free)
    if model.ma_s:
        ma_sf = model.ma_s_free if hasattr(model, "ma_s_free") else None
        _add_arma_blocks(right_blocks, model.ma_s, ma_sf, lag_mult=freq)
    _add_fixed_freq(right_blocks, model.ma_f)

    # ── mu: show value on eq line, SE below (like other params) ──────────
    mu_val_str = ""
    mu_se_str  = ""
    mu_sign    = ""
    if model.estimate_mu:
        v_mu, se_mu = pi.pop()
        mu_sign    = "−" if v_mu >= 0 else "+"
        mu_val_str = _fv(abs(v_mu))
        mu_se_str  = _fse(se_mu)

    diff_s  = _diff_str()
    has_ar  = bool(left_blocks)

    # ∇ is placed INSIDE the Nₜ term so that μ is the mean of the
    # differenced process (∇Nₜ), not of the non-stationary level Nₜ.
    # Correct form: (1−φB)(∇Nₜ − μ) = aₜ
    #
    # The `ifadf` factors go in the same place and for the same reason: they are
    # part of the differencing, so μ is the mean of what is left after ALL of it.
    # Written outside, `A_f(B)(∇Nₜ − μ)` has mean `A_f(1)(m − μ)`, which for the
    # f=4 case of BUG-0012 is 3·(0.1545 − 0.4642) = −0.93, not zero.
    #
    # Order: the ifadf factors are printed before ∇, so the seasonal operator
    # reads outermost. They all commute — they are polynomials in B — so this is
    # a presentation choice, fixed here so the regression can assert it.
    nt_core = f"{ifadf_s}{diff_s}Nₜ" if (diff_s or ifadf_s) else "Nₜ"
    if mu_val_str:
        nt_label   = f"({nt_core} {mu_sign} {mu_val_str})"
        mu_pfx_len = len(f"({nt_core} {mu_sign} ")
    elif has_ar:
        nt_label   = f"({nt_core})"
        mu_pfx_len = 0
    else:
        nt_label   = nt_core
        mu_pfx_len = 0

    # Each item is (val_str, se_str) where se_str is pre-padded relative to
    # the block's own start. Align the SE decimal point under the μ decimal point.
    if mu_se_str and mu_pfx_len:
        _dot_shift = ((mu_val_str.index(".") - mu_se_str.index("."))
                      if ("." in mu_val_str and "." in mu_se_str) else 0)
        nt_se = " " * max(0, mu_pfx_len + _dot_shift) + mu_se_str
    else:
        nt_se = ""
    lhs_items = []
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

        # fue escala los residuos por `refactor` antes de estimar. Qué SIGNIFICA
        # ese residuo escalado depende de λ, y ahí estaba BUG-0033:
        #
        #   λ=0 y refactor=100 → el residuo es ∇ln(y)·100, que ES un porcentaje.
        #   λ=1 y refactor=100 → el residuo es ∇y·100, que son las UNIDADES de la
        #                        serie multiplicadas por cien. Ni es un porcentaje
        #                        ni está en la escala de nadie.
        #
        # La regla miraba sólo `refactor` y ponía el `%` en los dos casos. En un
        # modelo en niveles eso publica un número 100× inflado con una etiqueta
        # que miente: PGAS de la réplica salía con «σ̂ₐ = 2273.6533%» cuando la
        # innovación es de 22.87 USD/t — un 7.8% de la media de la serie, casi
        # exactamente lo mismo que el modelo en logs (7.87%). El defecto hacía
        # parecer que dos modelos con la misma innovación diferían en dos órdenes
        # de magnitud, y eso invalida cualquier comparación entre carriles.
        if refactor >= 10 and lam == 0.0:
            sigma_disp = f"{sigma_raw:.4f}%"
        elif refactor >= 10:
            sigma_disp = f"{sigma_raw / refactor:.5f}"     # unidades de la serie
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

    # Title uses the MODEL name (file stem, e.g. IPC_ES_m00) so the equation and
    # its residual graph "A.<model>" share the same identifier; the equation body
    # keeps the series name as the variable (e.g. "ln IPC_ESₜ").
    mname = getattr(model, "_inp_stem", None) or ts_name

    lines = [
        sep,
        f"  MODELO ESTIMADO: {mname}   (n={ts.nobs}, {freq_lbl})",
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

    lines += ["", stat_line]

    # BUG-0062. Un operador cuyas raíces caen DENTRO del círculo unidad invalida
    # la lectura del modelo --un AR así no es estacionario, un MA así no es
    # invertible-- y se presentaba como cualquier otro resultado. `fue` declara
    # «Check for invertibility: constrained search» en la cabecera del `.out` y
    # aun así devolvió Θ₄ = −2.0989 tras 45 iteraciones. Sólo la diagnosis rota
    # lo delataba, y eso es enterarse por el síntoma equivocado.
    try:
        from art.diagnosis import admissibility_problems as _adm
        _probs = _adm(model)
    except Exception:
        _probs = []
    if _probs:
        dentro = [x for x in _probs if x[2] == "dentro"]
        frontera = [x for x in _probs if x[2] == "frontera"]
        lines.append("")
        if dentro:
            lines.append("  ⚠ OPERADOR NO ADMISIBLE — raíz DENTRO del círculo unidad:")
            for etq, mod, _ in dentro:
                que = ("no estacionario" if etq.startswith("AR") else "NO INVERTIBLE")
                lines.append(f"      {etq}: |raíz| = {mod:.4f} < 1  →  {que}")
            lines.append("      El modelo no se puede leer así: reformula el "
                         "operador. Un MA no invertible")
            lines.append("      no tiene representación AR(∞), y su previsión "
                         "depende del pasado infinito.")
        if frontera:
            lines.append("  ⚠ OPERADOR EN LA FRONTERA — raíz de módulo 1:")
            for etq, mod, _ in frontera:
                lines.append(f"      {etq}: |raíz| = {mod:.4f}")
            if any(e.startswith("MA") for e, _, _ in frontera) and d >= 1:
                lines.append("      Un MA con raíz unitaria y d≥1 CANCELA la "
                             "diferencia: es la firma de la")
                lines.append("      SOBREDIFERENCIACIÓN. Contrástalo con "
                             "`formal_tests` antes de mover `d`.")
            else:
                lines.append("      En la frontera el modelo es límite: los "
                             "errores típicos no son leíbles ahí.")

    # BUG-0060: la leyenda del marcador y, cuando es calculable, el error típico
    # HONESTO — todo dentro del cerco, que es lo que el analista lee.
    if _hay_semilla[0]:
        nota = ["", "  ✗ = error típico NO VÁLIDO: es la semilla del BFGS "
                    f"(√(2/n) = {_se_semilla:.4f}), no el hessiano. "
                    "No calcules t con él."]
        # Con μ libre y NINGÚN parámetro ARMA libre, la media es la media
        # muestral y su error típico exacto es σ̂ₐ/√n (BUG-0027).
        try:
            import numpy as _np
            from math import sqrt as _sqrt
            def _libres(fac, fl):
                if not fac:
                    return 0
                return len(fac[0]) if not fl else sum(1 for x in fl[0] if x)
            n_arma = (_libres(model.ar, getattr(model, "ar_free", None))
                      + _libres(model.ma, getattr(model, "ma_free", None))
                      + _libres(model.ar_s, getattr(model, "ar_s_free", None))
                      + _libres(model.ma_s, getattr(model, "ma_s_free", None)))
            r = getattr(model, "_result", None)
            if (getattr(model, "estimate_mu", False) and n_arma == 0
                    and r is not None and getattr(r, "sigma2", 0) > 0):
                nr = len(_np.asarray(r.residuals, dtype=float))
                se_mu = _sqrt(r.sigma2) / _sqrt(nr)
                mu_v = float(_reconstruct_params(model, list(model.params))[8])
                nota.append(
                    f"  → μ sin ARMA libre: el error típico correcto es "
                    f"σ̂ₐ/√n = {se_mu:.4f}, luego t = {mu_v/se_mu:+.2f} "
                    f"(no {mu_v/_se_semilla:+.2f}).")
        except Exception:
            pass
        lines += nota

    lines += [sep]
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

    # ── figures via pyfug (primary) or internal fallback ──────────────────
    hist_b64 = None
    if _PYFUG and model.residuals is not None:
        res  = model.residuals
        # fue convention: residuals (aₜ) are titled "A.<nombre del modelo>" so the
        # analyst associates the graph with the specific model. Use the model file
        # stem (e.g. IPC_ES_m00); fall back to the series name.
        mname = getattr(model, "_inp_stem", None) or model.series.name or ""
        rtitle = f"A.{mname}" if mname else "Residuos"
        pf   = _pyfug_ts(res.data, res.freq, _resid_start(model), name=rtitle)
        title_acf  = rtitle
        title_hist = f"Histograma {rtitle}" if mname else "Histograma residuos"
        fig_acf  = _pyfug_combined(pf, d=0, title=title_acf)
        b64      = _fig_b64(fig_acf);  plt.close(fig_acf)
        fig_hist = _pyfug_histogram(pf, d=0, title=title_hist)
        hist_b64 = _fig_b64(fig_hist); plt.close(fig_hist)
    else:
        fig = plot_diagnosis(result, model)
        b64 = _fig_b64(fig);  plt.close(fig)

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
        f"- Media residual: {'✓' if result.centred else '✗'}  "
        f"media={result.mean:+.4f}, t={result.mean_t:+.2f}",
        f"- Ruido blanco (Q): {wn}  {'OK' if result.white_noise else ', '.join(q_fails)}",
        f"- Normalidad (JB): {nm}  JB={result.jb_stat:.3f}, p={result.jb_pvalue:.4f}",
        f"- Asimetría={result.skewness:.3f}, curtosis exceso={result.excess_kurtosis:.3f}",
    ]

    if not result.centred:
        lines += [
            "",
            f"⚠ **La media residual NO es cero** (t={result.mean_t:+.2f}). El "
            "modelo no lleva la deriva de la serie y ésta se ha ido a los "
            "residuos.",
            "  NO lo arregles con intervenciones: un dummy no absorbe una "
            "deriva, y añadirlos aquí es el mismo error que reespecificar la "
            "forma de un modelo alrededor de un anómalo. Lo que falta es la "
            "MEDIA — reestima con `estimate_mu=True`.",
            "  (Criterio de adecuación de Brajín §2: la media residual pequeña "
            "en relación con su desviación típica. Es el único de su lista que "
            "art no contrastaba.)",
        ]

    if result.seasonal and result.seasonal.seasonal_detected:
        # BUG-0054. Este contraste se lee sobre los residuos, así que hereda la
        # regla de siempre: sobre residuos que NO son ruido blanco no es un
        # contraste débil, no es un contraste. Una estructura regular sin
        # modelar se hace pasar por estacional, y en trimestral el mecanismo es
        # inmediato -- el retardo 2 ES la frecuencia de Nyquist, o sea el
        # armónico semestral (-1)^t --, así que una ACF(2) positiva sin modelar
        # entra en la regresión armónica como si fuera patrón estacional.
        #
        # Caso real: PGAS_m03 (MA(1)) daba F=3.16, p=0.0293 con Q p-mín=0.0358 y
        # ACF(1)=+0.166, ACF(2)=+0.152. Corregido el orden a MA(2), la alarma
        # desaparece sola (F=2.05, p=0.1139) sin tocar nada estacional. Sin la
        # advertencia, empuja a meter armónicos en una serie que no los necesita.
        linea = (f"- ⚠ Estacionalidad residual: F={result.seasonal.f_stat:.2f}, "
                 f"p={result.seasonal.p_value:.4f}")
        if not result.white_noise:
            nyq = ""
            frq = getattr(result.seasonal, "freq", 0) or 0
            if frq >= 2:
                nyq = (f" En s={frq} el retardo {frq // 2} ES la frecuencia de "
                       f"Nyquist, así que una ACF({frq // 2}) sin modelar entra "
                       f"en la regresión armónica como patrón estacional.")
            linea += (
                "\n  ⚠ **NO LEÍBLE todavía**: los residuos no son ruido blanco "
                "(Q rechaza), y este contraste se calcula sobre ellos. Una "
                "estructura REGULAR sin modelar se hace pasar por estacional."
                + nyq +
                "\n  Corrige primero el ARMA regular y vuelve a mirar: si la "
                "alarma era de eso, desaparece sola.")
        lines.append(linea)

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
            # BUG-0043. La explicación de arriba es legítima y por eso se
            # mantiene — pero sobre un modelo en NIVELES de una magnitud positiva
            # de recorrido amplio no es la única, y mandar a añadir
            # intervenciones puede ser mandar a perseguir un síntoma. Ahí la
            # heterocedasticidad que el log elimina se manifiesta a la vez como
            # asimetría y como residuos grandes: los anómalos que uno "trata" son
            # el propio efecto de escala.
            #
            # Medido: un carril autónomo con λ=1 sobre un precio añadió
            # intervenciones ronda tras ronda con el JB bajando de 46.7 a 8.9 sin
            # llegar nunca a pasar. El consejo que recibía era éste, y era el que
            # le impedía volver al nodo correcto.
            _lam = float(getattr(model, "boxlam", 1.0) or 0.0)
            if _lam != 0.0:
                _y = _np.asarray(getattr(model.series, "data", []), dtype=float)
                if _y.size and _np.min(_y) > 0 and (_np.max(_y) / _np.min(_y)) >= 2.0:
                    parts.append(
                        f"pero OJO: este modelo está en niveles (λ={_lam:g}) sobre "
                        f"una serie positiva que recorre un factor "
                        f"{_np.max(_y) / _np.min(_y):.1f}, y ahí el efecto de "
                        "escala se manifiesta a la vez como asimetría "
                        f"({result.skewness:+.2f}) y como residuos grandes. Si el "
                        "JB sigue fallando tras tratar los anómalos, el problema "
                        "no son los anómalos: es λ"
                    )
        elif not result.normal and not result.extreme:
            # BUG-0043: aquí decía sólo "revisa la especificación", que no nombra
            # nada. Una JB que falla SIN anómalos que la expliquen es, antes que
            # ninguna otra cosa, la firma de una λ equivocada: la
            # heterocedasticidad que el log elimina reaparece como no-normalidad,
            # y ninguna intervención la arregla porque no hay un dato anómalo que
            # tratar — hay una escala mal elegida.
            #
            # Medido: un carril autónomo con λ=1 sobre un precio estimó SEIS
            # modelos consecutivos sin alcanzar la adecuación, con el JB entre
            # 46.7 y 8.9, añadiendo intervenciones que no podían servir. Nada le
            # dijo que volviera al nodo de λ.
            _lam = float(getattr(model, "boxlam", 1.0) or 0.0)
            _sesgo = abs(result.skewness)
            if _lam != 0.0:
                _y = _np.asarray(getattr(model.series, "data", []), dtype=float)
                _rango = (float(_np.max(_y) / _np.min(_y))
                          if _y.size and _np.min(_y) > 0 else None)
                _pista = (f" La serie es positiva y recorre un factor "
                          f"{_rango:.1f}." if _rango and _rango >= 2 else "")
                parts.append(
                    "los residuos no son normales y NO hay anómalos que lo "
                    f"expliquen (asimetría {result.skewness:+.2f}, curtosis "
                    f"{result.excess_kurtosis:+.2f}) — el primer sospechoso es la "
                    "TRANSFORMACIÓN, no el ARMA ni las intervenciones: este modelo "
                    f"está en niveles (λ={_lam:g}) y la heterocedasticidad que el "
                    "log elimina reaparece como no-normalidad." + _pista +
                    " Vuelve al nodo de λ antes de añadir estructura"
                )
            else:
                parts.append(
                    "los residuos no son normales y NO hay anómalos que lo "
                    f"expliquen (asimetría {result.skewness:+.2f}, curtosis "
                    f"{result.excess_kurtosis:+.2f}) — con el modelo ya en "
                    "logaritmos, mira si queda un episodio sin modelar o si la "
                    "escala pide algo distinto del log"
                )
        if not result.centred:
            # BUG-0043: la media descentrada no tenía rama, así que un modelo
            # cuyo ÚNICO fallo era ése cerraba con "Reformulación necesaria: ."
            # — la razón vacía.
            parts.append(
                f"la media residual no es cero (t={result.mean_t:+.2f}) — al "
                "modelo le falta la media, o la deriva se la está comiendo un "
                "determinista; ninguna intervención arregla esto"
            )
        if result.seasonal and result.seasonal.seasonal_detected:
            sig = [str(fr.freq_idx) for fr in (result.seasonal.freq_results or [])
                   if fr.p_value < 0.05]
            if sig:
                parts.append(
                    f"hay estacionalidad residual en freq={', '.join(sig)} — "
                    "revisa si los armónicos de esas frecuencias están incluidos o "
                    "si MEG sugiere que son estocásticas"
                )
            else:
                # BUG-0043: cuando el conjunto detecta y ninguna frecuencia es
                # significativa por separado, esto imprimía "freq=" a secas. El
                # hecho de que NINGUNA lo sea es información, no un hueco.
                parts.append(
                    f"el contraste CONJUNTO detecta estacionalidad residual "
                    f"(p={result.seasonal.p_value:.4f}) pero NINGUNA frecuencia "
                    "es significativa por separado — es un rechazo marginal "
                    "repartido, no una frecuencia concreta sin tratar; mira las "
                    "amplitudes antes de añadir nada"
                )
        if not parts:
            # Red de seguridad: `clean` es falso, así que algo falla. Decir cuál
            # sin una razón es peor que no decir nada.
            parts.append("la diagnosis no es adecuada y esta función no supo "
                         "nombrar el motivo — revisa el bloque de arriba")
        rec = "Reformulación necesaria: " + "; ".join(parts) + "."

    if overpar_pairs:
        pair_str = "; ".join(
            f"corr({lbl_i},{lbl_j})={r_val:+.3f}"
            for _, _, r_val, lbl_i, lbl_j in overpar_pairs
        )
        # BUG-0010: este consejo se anexa a la MISMA cadena que dice "procede a
        # los contrastes formales (DCD, MEG)", sin orden entre los dos. Si el par
        # es un cos/sin estacional, podarlo primero deja al MEG sin hipótesis nula
        # en esa frecuencia — y podar por t pre-juzga justo lo que el MEG contrasta.
        seasonal_pair = any(
            lbl.lower().startswith(("cos", "sin", "alter"))
            for _, _, _, lbl_i, lbl_j in overpar_pairs for lbl in (lbl_i, lbl_j)
        )
        overpar_note = (
            f" Sobreparametrización: {pair_str}. "
            f"Considera eliminar el parámetro menos significativo de cada par."
        )
        if seasonal_pair:
            overpar_note += (
                " ⚠ PERO hay armónicos estacionales (cos/sin/alter) entre esos "
                "pares: **la poda estacional va DESPUÉS del MEG**, no antes. El "
                "MEG contrasta el armónico determinista contra su forma "
                "estocástica, así que sin el armónico no hay nada que contrastar; "
                "y una t baja en un armónico es evidencia A FAVOR de que esa "
                "frecuencia sea estocástica, no de que no exista. La regla general "
                "de contrastar sobre un modelo parsimonioso no alcanza a los "
                "parámetros que SON la hipótesis."
            )
        rec = rec.rstrip(".") + "." + overpar_note

    return Description(
        summary="\n".join(lines),
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
            "hist_b64": hist_b64,   # histogram figure (pyfug); None if unavailable
        },
    )


# ---------------------------------------------------------------------------
# Formal tests
# ---------------------------------------------------------------------------

def describe_formal_tests(model, run_meg: bool = True) -> Description:
    """Run Shin-Fuller, DCD, DCD_f, RV, MEG and summarize for the LLM."""
    if model._result is None:
        raise RuntimeError("Model has not been fitted — call model.fit() first.")

    # BUG-0025: los contrastes formales son la ULTIMA etapa del ciclo y
    # presuponen un modelo adecuado — sus nulas se derivan bajo residuos que son
    # ruido blanco. La capa guiada lo dice ("B) Contrastes formales SI LOS
    # RESIDUOS ESTAN LIMPIOS", "el MEG evalua AL FINAL"), pero era prosa: aquí
    # no se miraba la diagnosis, y un modelo con la Q rota, la normalidad rota o
    # anómalos sin tratar podía cerrar en "el modelo es adecuado" — una
    # afirmación sobre el MODELO que esta función no está en condiciones de
    # hacer. Mismo principio que el comentario de BUG-0010 unas líneas abajo.
    # BUG-0036: esta guarda tenía su PROPIA lista de fallos, distinta de la que
    # usa la diagnosis para dictar su veredicto, y las dos se presentaban con la
    # misma palabra. El mismo modelo salía "APROBADO ✓" de confirm_and_estimate y
    # "todavía NO es adecuado" de aquí, sin ninguna regla que dijera cuál manda.
    #
    # Y no era que una fuese un caso particular de la otra: divergían en las DOS
    # direcciones. Esta contaba los residuos extremos y `residuals_ok` no —
    # deliberadamente, porque los extremos gobiernan el bucle de intervenciones y
    # no la adecuación—; y `residuals_ok` cuenta la estacionalidad residual, que
    # aquí no se miraba. Un modelo con estacionalidad en los residuos pasaba esta
    # guarda y fallaba la diagnosis.
    #
    # Ahora hay UN predicado: `DiagnosisResult.clean` (centrado + ruido blanco +
    # normalidad + sin estacionalidad residual), el mismo que dicta el veredicto.
    # Los extremos siguen reportándose, pero como AVISO y no como bloqueo: un
    # residuo aislado grande sobre un modelo que pasa la JB no invalida las nulas
    # de esta etapa, y tratarlo como si lo hiciera empujaba a añadir parámetros
    # no significativos sólo para cerrar la guarda.
    _dg = _try(lambda: diagnose(model), None)
    _dg_fallos: list[str] = []
    _dg_avisos: list[str] = []
    if _dg is not None:
        _q_min = min(_dg.q_pvalues) if _dg.q_pvalues else 1.0
        if not _dg.white_noise:
            _dg_fallos.append(f"ruido blanco (Q): p mínimo = {_q_min:.4f}")
        if not _dg.normal:
            _dg_fallos.append(
                f"normalidad (JB): {_dg.jb_stat:.3f}, p = {_dg.jb_pvalue:.4f}")
        if not _dg.centred:
            _dg_fallos.append(
                f"media residual distinta de cero: t = {_dg.mean_t:+.2f}")
        if _dg.seasonal is not None and getattr(_dg.seasonal, "seasonal_detected", False):
            _dg_fallos.append(
                f"estacionalidad en los residuos (p = "
                f"{getattr(_dg.seasonal, 'p_value', float('nan')):.4f})")
        if _dg.extreme:
            _peor = max(_dg.extreme, key=lambda t: abs(t[1]))
            _dg_avisos.append(
                f"{len(_dg.extreme)} residuo(s) extremo(s), el mayor obs "
                f"{_peor[0]} con z = {_peor[1]:+.2f}")

    sf_res    = _try(lambda: shin_fuller(model), None)
    dcd_res   = _try(lambda: dcd(model),   [])
    od_res    = _try(lambda: dcd_overdiff_regular(model), None)
    ud_res    = _try(lambda: dcd_underdiff_regular(model), None)
    dcd_f_res = _try(lambda: dcd_f(model), [])
    rv_res    = _try(lambda: rv(model),    [])
    # BUG-0010: this was `_try(lambda: meg(model), [])`, which made "raised" and
    # "not requested" the same empty list. The sweep no longer raises on an
    # unreformulable frequency -- it returns it as `skipped` -- so what is left
    # here is the unexpected, and an unexpected failure of the MEG must be said
    # out loud rather than read downstream as "nothing to report".
    meg_res, meg_error = [], None
    if run_meg and _meg_suitable(model):
        try:
            meg_res = meg(model)
        except Exception as exc:
            meg_error = f"{type(exc).__name__}: {exc}"

    lines = ["## Contrastes formales"]
    if not _dg_fallos and _dg_avisos:
        # Adecuado, con una salvedad que se nombra pero no bloquea.
        lines += [
            "",
            "> ℹ La diagnosis es adecuada, y queda una salvedad: "
            + "; ".join(_dg_avisos) + ".",
            ">",
            "> No invalida lo que sigue —las nulas de esta etapa suponen ruido "
            "blanco, y el modelo lo es— pero conviene saber que está ahí: un "
            "extremo aislado suele señalar un episodio cuya FORMA todavía no "
            "está bien especificada. Añadir un parámetro no significativo sólo "
            "para hacerlo desaparecer no es la respuesta.",
        ]
    if _dg_fallos:
        # BUG-0025: el aviso va ARRIBA, antes de cualquier estadístico, porque
        # lo que está en cuestión es si estos números se pueden leer.
        lines += [
            "",
            "> ⚠ **Este modelo todavía NO es adecuado.** La diagnosis falla en: "
            + "; ".join(_dg_fallos) + ".",
            ">",
            "> Los contrastes de esta etapa —MEG, Shin-Fuller, los DCD— derivan "
            "sus distribuciones nulas suponiendo residuos que son ruido blanco, "
            "así que **sus p-valores y sus veredictos no son fiables aquí**. "
            "Cierra antes el ciclo (intervenciones y/o ARMA) y vuelve. Lo que "
            "sigue es informativo, no concluyente.",
        ]

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
        lines.append("\n**DCD — no invertibilidad MA regular** (H₀: θ=1)")
        for r in dcd_res:
            c5 = r._crit['5%']
            verdict = "Invertible ✓" if r.lr >= c5 else "No invertible ✗"
            lines.append(f"- Factor {r.factor_index+1}: θ̂={r.coef_free:+.4f}, "
                         f"LR={r.lr:.3f} (crít 5%={c5:.2f}) → {verdict}")

    # DCD sobre-diferenciación regular — confirmatorio del ORDEN DE INTEGRACIÓN
    # (distinto del DCD estándar de arriba: impone ∇ extra + testigo MA(1) θ⁰=+0.85).
    if od_res is not None:
        c5 = od_res._crit['5%']
        # BUG-0055. El titular decía «→ considerar d+1 ✗» en negrita y tres
        # párrafos más abajo el mismo bloque explicaba que ese lado NO da
        # veredicto sobre d: crítico subestimado con deterministas resonantes,
        # sin par confirmatorio, y el contraste de sub-diferenciación diciendo
        # «d confirmado por abajo ✓» a continuación. El contenido correcto
        # estaba; la JERARQUÍA VISUAL trabajaba en su contra, y un titular
        # invita a leer sólo el titular. Pasó en esta réplica: se adoptó un d=2
        # sobre RATIO que hubo que retractar.
        #
        # Ahora las salvedades se calculan ANTES y el titular las lleva dentro.
        # Un veredicto no puede afirmar lo que el párrafo siguiente retira.
        _n_det   = len(model.interventions or [])
        _sin_par = sf_res is None
        _salvedades = bool(_n_det) or _sin_par

        if od_res.lr < c5:
            verdict = ("testigo NO invertible (θ→+1) → la ∇ extra sobre-diferencia "
                       "→ d confirmado ✓")
        elif _salvedades:
            _por = []
            if _n_det:
                _por.append("el crítico impreso está SUBESTIMADO (deterministas "
                            "resonantes en f=0)")
            if _sin_par:
                _por.append("falta el lado AR del par")
            verdict = ("testigo invertible → **este lado, POR SÍ SOLO, apuntaría "
                       "a d+1 — pero NO es concluyente**: " + " y ".join(_por) +
                       ". Lee los avisos de abajo ANTES de mover `d`")
        else:
            verdict = ("testigo invertible → raíz unitaria regular genuina → "
                       "este lado apunta a d+1 (⚠ un solo lado: confírmalo con "
                       "el par en f=0, más abajo)")
        lines.append("\n**DCD sobre-diferenciación regular** — confirmatorio del orden "
                     "de integración (testigo θ⁰=+0.85, H₀: θ=1, ley s=1)")
        lines.append(f"- θ̂={od_res.coef_free:+.4f}, LR={od_res.lr:.3f} "
                     f"(crít 5%={c5:.2f}) → {verdict}")

        # BUG-0038: estos dos avisos vivían DENTRO del bloque del par
        # confirmatorio, y el par sólo se forma cuando Shin-Fuller es aplicable —
        # es decir, cuando el modelo tiene AR regular libre. Un modelo SIN AR
        # regular recibía el veredicto "considerar d+1" a pelo, con el crítico de
        # la ley DESNUDA, y sin que nada dijera que ese crítico está mal calibrado
        # para él.
        #
        # Y muerde justo donde más duele: los dos avisos hablan del VEREDICTO DEL
        # DCD, no del par. El primero dice que el crítico impreso es menor que el
        # correcto cuando hay deterministas resonantes con f=0 — un escalón lo es—,
        # así que un LR apenas por encima de 1.94 puede no cruzar el umbral real.
        # El segundo dice que el LR se evalúa donde el perfil de verosimilitud de
        # fue salta. Ninguno de los dos depende de Shin-Fuller.
        #
        # Medido sobre RATIO de la réplica: modelo sin AR regular, con un escalón,
        # LR=2.576 contra un crítico impreso de 1.94. Sin aviso, se lee como
        # "hay una raíz unitaria más" y se toma d=2. Con el aviso, se lee como lo
        # que es: marginal contra un umbral que se sabe subestimado.
        n_det = len(model.interventions or [])
        if n_det:
            lines.append(
                f"  ℹ El crítico usado ({c5:.2f}) es el de la ley "
                f"DESNUDA s=1. Este modelo lleva {n_det} deterministas, y en f=0 "
                "el regresor constante es RESONANTE con la raíz unitaria — el "
                "paper mide pile-up 0.927 en esa configuración frente a 0.6575 "
                "desnudo. El crítico correcto ahí es mayor, así que un LR apenas "
                "por encima del impreso NO es evidencia de d+1.")
        if abs(abs(od_res.coef_free) - 1.0) > 1e-6:
            lines.append(
                "  ℹ θ̂ no se apila en la frontera, así que el LR usa ℓ(θ=1) "
                "calculada por fue justo donde su perfil da un salto errático "
                "(SF_MEG, apéndice de la verosimilitud de frontera). La decisión "
                "debería revisarse con la verosimilitud exacta bandeada.")
        if sf_res is None:
            lines.append(
                "  ⚠ **Sin par confirmatorio.** Este modelo no tiene AR regular "
                "libre, así que Shin-Fuller no es aplicable y el lado AR —la nula "
                "opuesta— no existe en esta corrida. El veredicto de arriba es UN "
                "SOLO lado, y los contrastes de frontera se leen en pareja. Antes "
                "de mover `d`, estima el candidato d+1 y compáralo por diagnosis y "
                "criterios de información.")

    # BUG-0045: el lado `d−1`. Shin-Fuller y el DCD de sobrediferenciación
    # miran los DOS hacia arriba —«¿basta d, o hace falta d+1?»— y ninguno
    # pregunta si con d−1 habría bastado, que es justo la duda cuando la tabla
    # ADF/KPSS recomienda una d menor que la adoptada.
    if ud_res is not None:
        c5u = ud_res._crit['5%']
        if ud_res.lr < c5u:
            ver_u = ("testigo NO invertible (θ→+1) → la ∇ está CANCELADA "
                     "→ con d−1 bastaba ✗")
        else:
            ver_u = ("testigo invertible → la ∇ es genuina → d confirmado "
                     "por abajo ✓")
        lines.append("\n**DCD sub-diferenciación regular** — ¿sobraba la ÚLTIMA "
                     "diferencia? (H₀: θ=1, ley s=1)")
        lines.append(f"- θ̂={ud_res.coef_free:+.4f}, LR={ud_res.lr:.3f} "
                     f"(crít 5%={c5u:.2f}) → {ver_u}")

    # ── EL PAR CONFIRMATORIO EN f=0 ───────────────────────────────────────
    # Shin-Fuller y el DCD de sobrediferenciación tienen nulas OPUESTAS y
    # acotan la banda de cuasi-cancelación. Su desacuerdo no es una
    # contradicción a resolver eligiendo uno: ES el diagnóstico de que se está
    # en esa banda (SF_MEG, tabla `tab:compare`). Reportarlos por separado
    # invitaba a leer «considera d+1» como una conclusión.
    quasi_cancellation = False
    if sf_res is not None and od_res is not None:
        od_says_more = od_res.lr >= od_res._crit['5%']
        sf_says_enough = sf_res.stationary
        lines.append("\n**Par confirmatorio en f=0** — dos contrastes con nulas "
                     "opuestas sobre el mismo orden de integración")
        lines.append(f"- lado AR (Shin-Fuller, H₀: ρ=1): "
                     f"{'d basta ✓' if sf_says_enough else 'raíz unitaria → d+1'}")
        lines.append(f"- lado MA (DCD sobrediferenciación, H₀: θ=1): "
                     f"{'raíz genuina → d+1' if od_says_more else 'la ∇ extra sobra → d basta ✓'}")
        if sf_says_enough != (not od_says_more):
            # BUG-0022: el testigo de sobrediferenciación sólo mide f=0 mientras
            # se mantenga en el eje POSITIVO. Si θ̂ < 0 su raíz apunta a B=−1 y
            # está midiendo NYQUIST, no la frecuencia cero — el propio
            # `dcd_overdiff_regular` lo documenta como el modo de fallo que la
            # inicialización en +0.85 pretende evitar. Cuando esa salvaguarda no
            # sujeta al testigo, el lado MA NO es una lectura de f=0 y no se
            # puede emparejar con Shin-Fuller. Antes se calculaba la distancia a
            # la frontera como abs(1-abs(θ̂)), lo que borraba el signo y
            # presentaba un testigo fugado como si estuviera en la banda de
            # cuasi-cancelación (r≈0.90–0.95).
            dist = 1.0 - od_res.coef_free          # distancia CON signo a θ=+1
            if od_res.coef_free < 0.0:
                lines += [
                    "",
                    f"  ⚠ **El testigo se salió del eje f=0.** θ̂="
                    f"{od_res.coef_free:+.4f} es NEGATIVO: su raíz apunta a B=−1, "
                    f"así que mide la frecuencia de Nyquist, no la frecuencia "
                    f"cero. Está a {dist:.4f} de la frontera θ=+1 — no es la "
                    "banda de cuasi-cancelación, es otro eje.",
                    "  **El lado MA no es interpretable como veredicto sobre d** "
                    "en esta corrida, y su LR no es un contraste de frontera "
                    "calibrado a esa distancia. Vuelve a correrlo sobre la línea "
                    "base determinista (armónicos, SIN ARMA regular compitiendo), "
                    "que es donde el testigo aísla f=0.",
                    "  Lectura directa que sí vale: si ∇^d y tiene ACF(1) "
                    "claramente POSITIVA, la diferencia no sobra.",
                ]
            else:
                quasi_cancellation = True
                lines += [
                    "",
                    f"  ⚠ **DISCREPAN, y eso es el diagnóstico.** Con θ̂="
                    f"{od_res.coef_free:+.4f} el testigo está a "
                    f"{dist:.4f} de la frontera: es la "
                    "**banda de cuasi-cancelación** (r≈0.90–0.95 en la tabla del "
                    "paper), donde el lado MA detecta que r<1 y el lado AR ve un "
                    "proceso casi estacionario. Los dos tienen razón.",
                    "  En esa banda las representaciones son **equivalentes en "
                    "previsión**, así que la decisión no se toma con estos "
                    "estadísticos: se toma por parsimonia, o comparando previsiones "
                    "fuera de muestra.",
                    "  **No leas «considerar d+1» como una conclusión.**",
                ]
        else:
            lines.append("  ✓ Los dos coinciden: el orden de integración no está "
                         "en la banda ambigua.")
            # BUG-0045: esa frase afirmaba más de lo que los dos contrastes
            # sostenían — ambos miran hacia d+1. Acotarlo por los dos lados
            # requiere el de sub-diferenciación.
            if ud_res is not None:
                if ud_res.lr >= ud_res._crit['5%']:
                    lines.append("  ✓ Y acotado por ABAJO: la última ∇ es genuina "
                                 "(sub-diferenciación LR="
                                 f"{ud_res.lr:.3f} ≥ {ud_res._crit['5%']:.2f}), "
                                 "así que d−1 no habría bastado. Las dos "
                                 "direcciones cierran sobre la misma d.")
                else:
                    lines.append("  ⚠ **Pero por ABAJO no cierra:** el testigo de "
                                 "sub-diferenciación se apila en θ=+1 (LR="
                                 f"{ud_res.lr:.3f} < {ud_res._crit['5%']:.2f}), "
                                 "o sea que la última ∇ está cancelada y con d−1 "
                                 "bastaba. El orden de integración NO está fijado: "
                                 "estima el candidato d−1 y compáralo por "
                                 "diagnosis y criterios de información.")
            else:
                lines.append("  ℹ Sólo por arriba: no se pudo contrastar si con "
                             "d−1 habría bastado, así que esta conclusión acota "
                             "el orden por un lado.")


    # DCD_f
    if dcd_f_res:
        lines.append("\n**DCD_f — no invertibilidad MA estacional** (H₀: λ₂=−1)")
        for r in dcd_f_res:
            c5 = r._crit['5%']
            verdict = "Invertible ✓" if r.lr >= c5 else "No invertible ✗"
            lines.append(f"- Factor {r.factor_index+1}: coef={r.coef_free:+.4f}, "
                         f"LR={r.lr:.3f} (crít 5%={c5:.2f}) → {verdict}")

    # RV
    if rv_res:
        lines.append("\n**RV — frecuencia de AR(2)**")
        for r in rv_res:
            verdict = "No rechaza ✓" if r.pvalue >= 0.05 else "Rechaza ✗"
            lines.append(f"- f̂={r.freq_estimated:.3f}, H₀:f={r.freq_null}: "
                         f"LR={r.lr:.3f}, p={r.pvalue:.4f} → {verdict}")

    # MEG
    stochastic_freqs = []
    if meg_res:
        lines.append("\n**MEG — estacionalidad estocástica** "
                     "(crít. DCD_f Monte Carlo, s=2 dependiente de n en frecuencias "
                     "interiores; s=1 en Nyquist)")
        for r in meg_res:
            if r.skipped:
                lines.append(f"- freq={r.freq}: ⚠ **sin contrastar** — {r.reason}")
            elif r.dcd_result is None:
                lines.append(f"- freq={r.freq}: {r.status}")
            else:
                c5 = r.dcd_result._crit['5%']
                lines.append(
                    f"- freq={r.freq}: coef={r.coef_ma_f:.4f}, "
                    f"LR={r.dcd_result.lr:.3f} (crít 5%={c5:.2f}) → **{r.status}**"
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
    elif meg_error is not None:
        lines.append(
            f"\n⚠ **El MEG falló y no hay veredictos**: {meg_error}. "
            "La ausencia de esta sección NO significa que el modelo esté bien "
            "en las frecuencias estacionales — significa que no se miraron."
        )
    elif run_meg and not _meg_suitable(model):
        lines.append(
            "\n*MEG no aplica: requiere D=0 con armónicos cos/sin en el modelo.*"
        )

    if sf_res is None and not dcd_res and not dcd_f_res and not rv_res and not meg_res:
        lines.append("*Ningún contraste aplicable a esta especificación.*")

    # Build recommendation
    issues = []
    if quasi_cancellation:
        # En la banda, el par NO da una acción sobre d: da un diagnóstico. Emitir
        # "considera d+1" aquí es justo lo que el paper dice que no se haga.
        issues.append(
            f"**Banda de cuasi-cancelación en f=0** (θ̂={od_res.coef_free:+.4f}): "
            f"Shin-Fuller dice que d basta (Φ̂₁ᵤ={sf_res.phi_1u:.3f}) y el DCD de "
            f"sobrediferenciación dice d+1 (LR={od_res.lr:.3f}). Los dos tienen "
            "razón: es la banda donde las dos representaciones son equivalentes "
            "en previsión. NO cambies d con esta evidencia — decide por "
            "parsimonia (quédate con la actual) o compara previsiones fuera de "
            "muestra. Ver SF_MEG, tabla `tab:compare`."
        )
    elif od_res is not None and od_res.coef_free < 0.0:
        # BUG-0022: testigo fugado al eje de Nyquist. No es "sin problemas".
        issues.append(
            f"**Testigo de sobrediferenciación fuera del eje f=0** "
            f"(θ̂={od_res.coef_free:+.4f} < 0): su raíz apunta a B=−1, mide "
            f"Nyquist y no la frecuencia cero, a {1.0 - od_res.coef_free:.4f} de "
            "la frontera θ=+1. El lado MA no da veredicto sobre d aquí. Repite "
            "el contraste sobre la línea base determinista (sin ARMA regular "
            "compitiendo) y, mientras tanto, decide d por el signo de la ACF(1) "
            "de ∇^d y: positiva ⇒ la diferencia no sobra."
        )
    elif sf_res is not None and not sf_res.stationary:
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
    # BUG-0010: una frecuencia sin contrastar no puede terminar en "el modelo es
    # adecuado". El veredicto que falta es justo el que nadie va a echar de menos.
    skipped_freqs = [r.freq for r in meg_res if r.skipped]
    if skipped_freqs:
        issues.append(
            f"MEG sin contrastar en freq={skipped_freqs}: el modelo no tiene el "
            "armónico determinista que el contraste necesita como hipótesis nula. "
            "Si se podaron armónicos, corre el MEG sobre la línea base pre-MEG "
            "(todas las frecuencias estacionales deterministas): una t baja en un "
            "armónico es evidencia A FAVOR de estacionalidad estocástica en esa "
            "frecuencia, no de que la frecuencia no exista."
        )
    if meg_error is not None:
        issues.append(
            f"El MEG no pudo ejecutarse ({meg_error}): las frecuencias "
            "estacionales quedan sin contrastar."
        )

    # BUG-0025: una diagnosis que falla no puede terminar en "el modelo es
    # adecuado" — igual que una frecuencia sin contrastar (BUG-0010).
    if _dg_fallos:
        issues.insert(0, (
            "**El modelo aún no es adecuado**, así que estos contrastes se están "
            "leyendo fuera de su etapa: " + "; ".join(_dg_fallos) + ". Cierra el "
            "ciclo (intervenciones y/o ARMA) y repítelos; sus nulas suponen "
            "residuos de ruido blanco."))

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
            "overdiff_regular": (
                {"lr": od_res.lr, "coef": od_res.coef_free,
                 "crit_5pct": od_res._crit['5%'],
                 "overdifferences": od_res.lr < od_res._crit['5%']}
                if od_res is not None else None
            ),
            "meg": [{"freq": r.freq, "status": r.status,
                     "lr": r.dcd_result.lr if r.dcd_result else None,
                     "reason": r.reason}
                    for r in meg_res],
            "meg_error": meg_error,
            "f0_pair": (
                {"sf_stationary": sf_res.stationary,
                 "sf_phi_1u": sf_res.phi_1u,
                 "dcd_lr": od_res.lr,
                 "dcd_theta": od_res.coef_free,
                 "dcd_crit_5pct": od_res._crit['5%'],
                 "quasi_cancellation": quasi_cancellation}
                if (sf_res is not None and od_res is not None) else None
            ),
            # BUG-0025: el estado de la adecuación, para quien lea la estructura
            # en vez del texto.
            "diagnosis_ok": not _dg_fallos,
            "diagnosis_failures": list(_dg_fallos),
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
    b64_diag = None
    try:
        if _PYFUG and model.residuals is not None:
            res  = model.residuals
            # fue convention: residuals titled "A.<nombre del modelo>".
            mname = getattr(model, "_inp_stem", None) or model.series.name or ""
            rtitle = f"A.{mname}" if mname else "Residuos"
            pf   = _pyfug_ts(res.data, res.freq, _resid_start(model), name=rtitle)
            fig_diag = _pyfug_combined(pf, d=0, title=rtitle)
            b64_diag = _fig_b64(fig_diag)
            plt.close(fig_diag)
        else:
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
# Pre-identification outlier scan — helpers
# ---------------------------------------------------------------------------

def _sample_acf_raw(w_std: "np.ndarray", lags: int) -> "np.ndarray":
    """Sample ACF r(k) for k=1..lags using the biased denominator Σẑ_j²."""
    import numpy as np
    n = len(w_std)
    denom = float(np.sum(w_std ** 2))
    acf = np.zeros(lags)
    if denom < 1e-15:
        return acf
    for k in range(1, lags + 1):
        acf[k - 1] = float(np.sum(w_std[: n - k] * w_std[k:])) / denom
    return acf


def _acf_outlier_contributions(
    w_std: "np.ndarray", outlier_idx: list[int], lags: int
) -> "np.ndarray":
    """
    Contribution of each outlier to the sample ACF at each lag.

    Returns contrib[i, k-1] where i indexes outlier_idx and k=1..lags.

    C_k(p) = [ẑ_p·ẑ_{p+k}  +  ẑ_{p-k}·ẑ_p] / Σ_j ẑ_j²
    """
    import numpy as np
    n = len(w_std)
    denom = float(np.sum(w_std ** 2))
    contrib = np.zeros((len(outlier_idx), lags))
    if denom < 1e-15 or not outlier_idx:
        return contrib
    for ii, p in enumerate(outlier_idx):
        for k in range(1, lags + 1):
            c = 0.0
            if p + k < n:
                c += w_std[p] * w_std[p + k]
            if p - k >= 0:
                c += w_std[p - k] * w_std[p]
            contrib[ii, k - 1] = c / denom
    return contrib


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

    # ── ACF contributions (computed before figure so we can use them in both) ─
    n_lags = min(len(w_std) // 3, max(12, 2 * freq))
    acf_full   = _sample_acf_raw(w_std, n_lags)
    ci_val     = 1.96 / np.sqrt(len(w_std))

    outl_idx = [i for i, _, _ in outliers]
    contribs = _acf_outlier_contributions(w_std, outl_idx, n_lags)
    total_contrib = contribs.sum(axis=0)  # (n_lags,) — summed over all outliers

    # Lags whose |contribution| is meaningful (> half CI)
    affected_lags = [
        {"lag": k + 1,
         "acf": float(acf_full[k]),
         "contribution": float(total_contrib[k]),
         "pct": float(100.0 * total_contrib[k] / acf_full[k]) if abs(acf_full[k]) > 1e-6 else None}
        for k in range(n_lags)
        if abs(total_contrib[k]) > ci_val * 0.4
    ]

    # ── Figure ────────────────────────────────────────────────────────────────
    label = transform_label(lam, d, D, freq)
    n_w   = len(w_std)
    xs    = np.arange(n_w)

    if outliers:
        fig, (ax, ax2) = plt.subplots(
            2, 1, figsize=(13, 6.5),
            gridspec_kw={"height_ratios": [2, 1.2]}
        )
    else:
        fig, ax = plt.subplots(figsize=(13, 3.5))
        ax2 = None

    # Top panel — standardised series
    ax.axhline(0,          color="black",   lw=0.7)
    ax.axhline(+2,         color="#888888", lw=0.8, ls="--")
    ax.axhline(-2,         color="#888888", lw=0.8, ls="--")
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

    # Bottom panel — ACF contributions (only when there are outliers)
    if ax2 is not None:
        lags_x = np.arange(1, n_lags + 1)
        ax2.bar(lags_x, acf_full, color="#9ecae1", alpha=0.85,
                label="ACF(k)", zorder=2)
        ax2.bar(lags_x, total_contrib, color="#e74c3c", alpha=0.75,
                label="Contribución outlier(s)", zorder=3)
        ax2.axhline(0,       color="black",   lw=0.6)
        ax2.axhline(+ci_val, color="#888888", lw=0.8, ls="--")
        ax2.axhline(-ci_val, color="#888888", lw=0.8, ls="--")
        ax2.set_xlabel("Retardo k", fontsize=9)
        ax2.set_ylabel("r(k)", fontsize=9)
        ax2.set_title(
            "Contribución de outlier(s) a la ACF  (rojo = parte debida al outlier)",
            fontsize=9, fontweight="bold"
        )
        ax2.legend(fontsize=7, loc="upper right", framealpha=0.7)
        ax2.tick_params(axis="both", labelsize=8)

    fig.tight_layout()
    b64 = _fig_b64(fig)
    plt.close(fig)

    # ── Summary text ──────────────────────────────────────────────────────────
    lines = [
        f"## Escaneo pre-identificación — {name}  ({label})",
        f"- Serie tipificada: n={len(w_std)}, μ̂={mu:.4f}, σ̂={sigma:.4f}",
        f"- Umbral: |z| > {threshold}",
    ]

    var_max = 0.0
    max_acf_pct = 0.0
    distortion_level = "none"
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

        var_max = max(z_i**2 for _, z_i, _ in outliers) / np.sum(w_std**2) * 100
        lines += [
            "",
            f"⚠ El outlier mayor explica aprox. **{var_max:.1f}%** de la varianza tipificada.",
        ]

        max_acf_pct = 0.0
        if affected_lags:
            top = sorted(affected_lags, key=lambda r: -abs(r["contribution"]))[:6]
            lag_strs = []
            n_no_informativos = 0
            for r in top:
                # Only count percentage for lags where ACF itself is significant;
                # when |acf| < CI the denominator is near zero → spuriously huge pct.
                informativo = r["pct"] is not None and abs(r["acf"]) > ci_val
                if informativo:
                    max_acf_pct = max(max_acf_pct, abs(r["pct"]))
                    lag_strs.append(f"k={r['lag']} ({r['pct']:+.0f}%)")
                else:
                    # BUG-0043: el porcentaje es contribución/ACF total, así que
                    # donde la ACF ronda cero el cociente se dispara y no
                    # significa nada — salían cifras como −1162% o −1561% junto a
                    # un ACF_max=0%. El criterio de decisión ya los excluía (ver
                    # arriba); lo que faltaba era no PUBLICARLOS como si midieran
                    # algo. Se enseña la ACF, que es el dato honesto.
                    n_no_informativos += 1
                    lag_strs.append(f"k={r['lag']} (ACF={r['acf']:+.3f}, "
                                    f"dentro de banda)")
            nota_denom = ("  El porcentaje sólo se da donde la ACF sale de la "
                          "banda: es un cociente sobre la ACF total, y donde ésta "
                          "ronda cero se dispara sin significar nada."
                          if n_no_informativos else "")
            lines += [
                "",
                f"**Retardos ACF más afectados**: {', '.join(lag_strs)}.",
                "(Porcentaje = contribución del outlier / ACF total en ese retardo.)"
                + nota_denom,
            ]

        # ── Criterion: should we intervene? ──────────────────────────────────
        intervene_strong = var_max > 15.0 or max_acf_pct > 30.0
        intervene_mild   = var_max > 5.0  or max_acf_pct > 10.0

        distortion_level = ("strong" if intervene_strong
                            else "moderate" if intervene_mild else "light")

        # Tratar los anómalos ANTES de ARMA es un PUNTO DE DECISIÓN del analista.
        # ART calibra la distorsión y SUGIERE; la decisión es del analista.
        if intervene_strong:
            verdict = (
                "**Distorsión fuerte sobre la ACF/PACF** "
                f"(var_outlier={var_max:.1f}%, ACF_max={max_acf_pct:.0f}%): los anómalos "
                "están distorsionando con fuerza la identificación, y las ACF/PACF no son "
                "robustas a outliers.\n"
                "→ **Sugerencia:** tratar los anómalos con intervenciones antes de "
                "especificar ARMA.\n"
                "→ **Punto de decisión del analista:** confirma si intervenir ahora o "
                "pasar directamente a ARMA."
            )
        elif intervene_mild:
            verdict = (
                "**Distorsión moderada sobre la ACF/PACF** "
                f"(var_outlier={var_max:.1f}%, ACF_max={max_acf_pct:.0f}%).\n"
                "→ **Sugerencia:** puede merecer la pena intervenir, pero también es "
                "razonable pasar a ARMA y revisar los residuos.\n"
                "→ **Punto de decisión del analista:** observa si las ACF/PACF muestran "
                "estructura clara y decide."
            )
        else:
            verdict = (
                "**Distorsión leve sobre la ACF/PACF** "
                f"(var_outlier={var_max:.1f}%, ACF_max={max_acf_pct:.0f}%).\n"
                "→ **Sugerencia:** no hay evidencia clara de distorsión; razonable pasar a "
                "ARMA.\n"
                "→ **Punto de decisión del analista:** la decisión de intervenir sigue "
                "siendo tuya."
            )

        lines += ["", verdict]

        dates = [date for _, _, date in outliers]
        if intervene_strong:
            rec = (
                f"PUNTO DE DECISIÓN (analista): {len(outliers)} anómalo(s) grande(s) en "
                f"{', '.join(dates)} distorsionan FUERTEMENTE la ACF/PACF "
                f"(var_outlier={var_max:.1f}%, ACF_max={max_acf_pct:.0f}%). "
                "Claude debe SUGERIR tratarlos con intervenciones (pulse/step) antes de "
                "identificar (p, q), explicando la distorsión calibrada — pero la decisión "
                "de intervenir ahora vs. pasar a ARMA la confirma el analista."
            )
        elif intervene_mild:
            rec = (
                f"PUNTO DE DECISIÓN (analista): {len(outliers)} anómalo(s) en "
                f"{', '.join(dates)} con distorsión moderada. "
                "Claude puede sugerir intervenir, pero también es válido pasar a ARMA y ver "
                "si los residuos quedan limpios. Decide el analista."
            )
        else:
            rec = (
                f"Los anómalos en {', '.join(dates)} tienen impacto leve sobre la ACF/PACF. "
                "Razonable pasar a ARMA; la decisión de intervenir es del analista."
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
            "acf_contributions": affected_lags,
            "var_outlier_pct": var_max,        # % varianza del mayor anómalo
            "acf_max_pct": max_acf_pct,         # % distorsión ACF en el retardo más afectado
            "distortion_level": distortion_level,  # none|light|moderate|strong
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
        # La poda NO está prohibida: está ORDENADA. Un |t| bajo en la frecuencia
        # f no es por sí solo evidencia de que f sobre —también es lo que produce
        # una estacionalidad estocástica, cuya amplitud vaga y promedia hacia
        # cero—, y el modelo nulo del MEG en f ES este armónico. De ahí el orden.
        #
        # Pero hay dos caminos legítimos hasta la poda, y art los ofrecía antes:
        #   * el analista renuncia al MEG y fija la estacionalidad como
        #     determinista: entonces el contraste de simplificación es
        #     exactamente lo que procede;
        #   * el MEG ya corrió y el modelo es mixto: se poda lo que NO declaró
        #     estocástico, y lo que sí se reformula con ifadf[f]=1.
        # Lo que no se hace es podar ANTES y sin decidir cuál de los dos es.
        rec = (
            f"Los armónicos {', '.join(f'k={k}' for k in drop_k)} tienen |t| ≤ 2 "
            f"en ambos componentes. Antes de eliminarlos, decide en qué camino "
            f"estás — un |t| bajo en f también es lo que produce una "
            f"estacionalidad ESTOCÁSTICA en f, y el modelo nulo del MEG en esa "
            f"frecuencia ES este armónico:\n\n"
            f"**(a) Vas a contrastar el MEG** (recomendado si la estacionalidad "
            f"puede evolucionar): **no podes todavía**. Estima un modelo "
            f"adecuado, corre el MEG sobre esas frecuencias, y después poda sólo "
            f"donde NO haya declarado estocástica; las que sí, se reformulan con "
            f"ifadf[f]=1, no se eliminan.\n\n"
            f"**(b) Fijas la estacionalidad como determinista** y renuncias al "
            f"MEG: entonces **procede simplificar ahora** — test RV conjunto del "
            f"Bloque H (`test_seasonal_simplification`) sobre "
            f"{', '.join(f'k={k}' for k in drop_k)}, sobre un modelo cuyos "
            f"residuos no tengan estructura.\n\n"
            f"En un modelo MIXTO ya resuelto, la poda de los armónicos que "
            f"quedan deterministas es el paso final y también procede."
        )
    else:
        rec = (
            "Todos los armónicos son significativos (|t| > 2): no hay "
            "simplificación que proponer por esta vía. Si la estacionalidad "
            "puede evolucionar, la pregunta que queda —si alguna frecuencia es "
            "estocástica— la responde el MEG, no los t-ratios."
        )

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
