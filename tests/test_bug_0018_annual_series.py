"""BUG-0018 — las series anuales (freq=1) no llegaban al final del flujo.

La ficha nombraba tres defectos. Al medirlos el 12-ago-2026, **los tres estaban
ya arreglados** —el `alter` espurio por el guardia `freq >= 2` de BUG-0005, la
cabecera de `_write_inp`, y el `x_pad` de pyfug— y el que bloqueaba de verdad era
un cuarto que la ficha no menciona: `detect_seasonality` dividía por
`num_harmonics = s - 1`, que en anual es CERO, así que el `ZeroDivisionError`
mataba `run_full` antes de estimar nada.

Más lo que sí seguía vivo de la ficha: `_write_bare_inp` conservaba la cabecera
antigua (el año repetido en el campo del periodo) mientras `_write_inp` ya la
escribía bien. Dos escritores del mismo formato, un arreglo que no viajó.

Los tests de abajo cubren los cuatro, para que ninguno vuelva por su cuenta.
"""
import numpy as np
import pytest


def _annual(n=248, seed=11):
    """Serie anual tipo precipitación: n=248 desde 1768, como el caso original."""
    import fue
    rng = np.random.default_rng(seed)
    y = 700 + np.cumsum(rng.normal(0, 6, n)) * 0.3 + rng.normal(0, 40, n)
    return fue.TimeSeries(list(y), freq=1, start=(1768, 1), name="GE")


# ── el que bloqueaba: la detección de estacionalidad ───────────────────────

def test_seasonality_detection_does_not_divide_by_zero_on_annual():
    """s=1 ⇒ s−1 = 0 armónicos ⇒ el F-test dividía por cero y LANZABA."""
    from art.seasonal_detection import detect_seasonality

    r = detect_seasonality(_annual())
    assert r.seasonal_detected is False
    assert r.freq == 1
    assert len(r.harmonic_coeffs) == 0
    assert "anual" in r.message.lower()


def test_the_annual_verdict_reaches_the_policy_as_decision_A():
    """No basta con no lanzar: el veredicto tiene que llegar bien al otro lado."""
    from art.describe import describe_seasonality
    from art.policy import decide_seasonal_structure

    ts = _annual()
    seas = describe_seasonality(ts)
    D, decision, n_harmonics = decide_seasonal_structure(seas.data, ts.freq)
    assert (D, decision, n_harmonics) == (0, "A", 0)


# ── (1) el determinista alter, que no existe en anual ──────────────────────

def test_no_spurious_alter_in_an_annual_model():
    """`alter` = (−1)ᵗ es el armónico de Nyquist f=s/2. En anual no hay Nyquist:
    sería una oscilación bienal determinista que nadie pidió."""
    from art.pipeline import _make_model

    m = _make_model(_annual(), lam=1.0, d=1, D=0, p=1, q=0, n_harmonics=0)
    types = [i.type for i in (m.interventions or [])]
    assert "alter" not in types
    assert types == []


def test_nested_annual_fits_are_monotone_in_p():
    """El criterio que destapó el `alter`: entre modelos anidados logL no puede
    empeorar. Con el determinista espurio dentro daba AR(14) peor que AR(7),
    que es imposible salvo no convergencia."""
    from art.pipeline import ModelSpec, build_and_fit

    ts = _annual()
    lls = []
    for p in (1, 2, 3):
        fr = build_and_fit(ts, ModelSpec(lam=1.0, d=1, D=0, p=p, q=0,
                                         n_harmonics=0, seasonal=False,
                                         estimate_mu=True),
                           str(_tmp() / f"ar{p}.inp"), 3.0)
        lls.append(fr.model.loglik)
    assert lls[0] <= lls[1] <= lls[2], f"logL no monótona en p: {lls}"


# ── (2) la cabecera .inp, POR LOS DOS ESCRITORES ───────────────────────────

@pytest.mark.parametrize("writer", ["_write_inp", "_write_bare_inp"])
def test_annual_header_and_round_trip_by_both_writers(writer):
    """En anual el periodo inicial es 1, no el año repetido.

    Se parametriza por escritor a propósito: `_write_inp` ya estaba arreglado y
    `_write_bare_inp` no, que es exactamente el fallo de tener dos.
    """
    import fue
    from art import pipeline

    ts = _annual()
    path = str(_tmp() / f"annual_{writer}.inp")
    if writer == "_write_inp":
        m = pipeline._make_model(ts, lam=1.0, d=1, D=0, p=1, q=0, n_harmonics=0)
        pipeline._write_inp(ts, m, path)
    else:
        pipeline._write_bare_inp(ts, path)

    header = open(path).read().splitlines()[8]
    assert header.split()[:3] == ["248", "1", "1768"], header

    ts2, _m2 = fue.inp.load(path)
    assert ts2.start == ts.start and ts2.nobs == ts.nobs


# ── (3) y el flujo entero, que es lo que el usuario ve ─────────────────────

def test_the_autonomous_pipeline_completes_on_an_annual_series():
    from art.pipeline import run_full

    r = run_full(_annual(), str(_tmp() / "annual_run.inp"), max_rounds=1)
    assert r.D == 0 and r.n_harmonics == 0 and r.decision == "A"
    assert [i.type for i in (r.final_model.interventions or [])] == []


def test_the_annual_diagnosis_plot_does_not_crash():
    """`x_pad` sólo se definía en la rama `f > 1` de pyfug, así que el gráfico
    reventaba justo DESPUÉS de estimar — con el modelo ya ajustado delante."""
    from art.describe import describe_diagnosis
    from art.pipeline import run_full

    r = run_full(_annual(), str(_tmp() / "annual_diag.inp"), max_rounds=1)
    d = describe_diagnosis(r.final_model)
    assert d.figure_b64


def test_formal_tests_run_on_an_annual_model():
    """MEG no aplica en anual (no hay armónicos), pero no debe romper nada."""
    from art.describe import describe_formal_tests
    from art.pipeline import run_full

    r = run_full(_annual(), str(_tmp() / "annual_ft.inp"), max_rounds=1)
    d = describe_formal_tests(r.final_model, run_meg=True)
    assert d.recommendation
    assert d.data["meg"] == []
    assert d.data["meg_error"] is None      # no aplicable ≠ falló (BUG-0010)


# ── utilidad ───────────────────────────────────────────────────────────────

_TMP = None


def _tmp():
    global _TMP
    if _TMP is None:
        import pathlib
        import tempfile
        _TMP = pathlib.Path(tempfile.mkdtemp(prefix="bug0018_"))
    return _TMP
