"""Series I(2) de la tesis: el banco que faltaba para el DCD regular y el MEG.

Los IPC mensuales de Chile y Colombia (1986-01…2001-12, n=192) son I(2) con
estacionalidad determinista y estocástica, y cierran el ciclo completo que
ninguna otra serie del banco recorre:

  * el resto de las series de contraste son I(1) (los ocho IPC de 2002-2019) o
    I(0) (las de precipitación anual);
  * éstas son I(2), así que son el único sitio donde la especificación inicial
    (d=1, un paso desde d=0) y el veredicto final (d+1) tienen que DIFERIR — y
    donde `dcd_overdiff_regular` debe decir «considera d+1» y acertar.

Es la demostración del método completa: la elección inicial de `d` es una
especificación, y el contraste sobre `d` se hace al final, sobre un modelo
adecuado. Medido el 12-ago-2026:

    país       λ   rec_d(ADF)  R²tend   d inicial   DCD final        MEG
    Chile      0        2       0.928       1       LR=18.235 → d+1  6 deterministas
    Colombia   0        0       0.983       1       LR=16.805 → d+1  f=4 estocástica

Colombia es además el primer caso REAL en que la regla de tendencia se dispara:
el ADF rechaza en el nivel de un índice que va de 6.75 a 127.87 — baja potencia
pura — y la dominancia de la tendencia (R²=0.983) lo corrige a d=1.

Los ficheros del archivo de la tesis están en **latin-1**: los escribió el
programa C original y el parser de `fue` asume utf-8, así que se convierten a un
temporal antes de leerlos. Ver TODO.
"""
import os
import tempfile

import pytest

_BASE = os.path.expanduser("~/Documents/Documentos/Tesis/Analisis")
_CHILE = os.path.join(_BASE, "Chile/ipc/mensuales/analisis/muestra_1.86_12.01/PC.inp")
_COLOMBIA = os.path.join(_BASE, "Colombia/ipc/mensuales/analisis/muestra_1.86_12.01/PO.inp")

pytestmark = pytest.mark.skipif(
    not (os.path.exists(_CHILE) and os.path.exists(_COLOMBIA)),
    reason="archivo de la tesis no presente")

_TMP = None


def _tmp():
    global _TMP
    if _TMP is None:
        _TMP = tempfile.mkdtemp(prefix="tesis_i2_")
    return _TMP


def _load(path, name):
    """Convierte de latin-1 y devuelve sólo la SERIE: el modelo del fichero es
    del analista de entonces y aquí se identifica desde cero."""
    import fue

    dst = os.path.join(_tmp(), os.path.basename(path))
    if not os.path.exists(dst):
        open(dst, "w", encoding="utf-8").write(
            open(path, encoding="latin-1").read())
    ts, _m = fue.inp.load(dst)
    return fue.TimeSeries(list(ts.data), freq=ts.freq, start=ts.start, name=name)


_SERIES = {"IPC_Chile": _CHILE, "IPC_Colombia": _COLOMBIA}


def _run(name):
    from art.pipeline import run_full

    ts = _load(_SERIES[name], name)
    return ts, run_full(ts, os.path.join(_tmp(), name + ".inp"), max_rounds=2)


# ── la especificación inicial ──────────────────────────────────────────────

@pytest.mark.parametrize("name", sorted(_SERIES))
def test_the_initial_specification_is_d_one(name):
    """Un paso desde d=0, aunque la serie sea I(2) y aunque la evidencia pida 2.

    Ese es el punto: desde el nivel la pregunta es «¿hace falta AL MENOS una
    diferencia?», y la segunda se decide después, sobre un modelo adecuado.
    """
    _ts, r = _run(name)
    assert r.d == 1
    assert r.lam == 0.0            # índice de precios: la regla de BUG-0015
    assert r.D == 0 and r.decision == "B1"


def test_colombia_is_where_the_trend_rule_earns_its_keep():
    """El ADF declara ESTACIONARIO el nivel de un índice que se multiplica por
    19 en 16 años. Es baja potencia, y el gráfico lo desmiente: R² = 0.983."""
    from art.describe import describe_unit_root
    from art import policy

    ts, r = _run("IPC_Colombia")
    u = describe_unit_root(ts, lam=r.lam).data

    assert u["recommended_d"] == 0, "precondición: el ADF rechaza en el nivel"
    assert u["trend_r2"] > policy.THRESHOLDS["trend_dominates"]
    assert policy.decide_d(u, seasonal=True) == 1
    assert r.d == 1


# ── y el contraste final, que es donde se recupera d=2 ─────────────────────

@pytest.mark.parametrize("name", sorted(_SERIES))
def test_the_final_dcd_recovers_the_second_difference(name):
    """`dcd_overdiff_regular` sobre el modelo ajustado dice «considera d+1», que
    en una serie I(2) es la respuesta correcta.

    Con el testigo invertible (θ̂ lejos de +1) la diferencia extra NO sobra: la
    raíz unitaria adicional es genuina. Es el cierre del ciclo — especificación
    inicial d=1, contraste al final, d=2.
    """
    from art.formal_tests import dcd_overdiff_regular

    _ts, r = _run(name)
    d = dcd_overdiff_regular(r.final_model)

    assert d.lr > d._crit["5%"], f"{name}: LR={d.lr:.3f} no recupera d=2"
    assert d.coef_free < 1.0
    assert d.lr > 10.0, f"{name}: la evidencia debería ser holgada, LR={d.lr:.3f}"


# ── el MEG sobre series con estacionalidad de los dos tipos ────────────────

def test_the_meg_sweep_is_complete_on_both():
    """Seis frecuencias, ninguna saltada, ningún fallo silencioso (BUG-0010)."""
    from art.describe import describe_formal_tests

    for name in sorted(_SERIES):
        _ts, r = _run(name)
        d = describe_formal_tests(r.final_model, run_meg=True)
        megs = d.data["meg"]
        assert [x["freq"] for x in megs] == [1, 2, 3, 4, 5, 6], name
        assert not [x for x in megs if x["status"] == "skipped"], name
        assert d.data["meg_error"] is None, name


def test_colombia_carries_a_stochastic_frequency():
    """El caso mixto: f=4 estocástica y el resto deterministas. Sin él, el MEG
    sólo estaría probado donde no encuentra nada."""
    from art.describe import describe_formal_tests

    _ts, r = _run("IPC_Colombia")
    megs = {x["freq"]: x for x in describe_formal_tests(r.final_model, run_meg=True).data["meg"]}
    assert megs[4]["status"] == "stochastic"
    assert [f for f, x in megs.items() if x["status"] == "stochastic"] == [4]
