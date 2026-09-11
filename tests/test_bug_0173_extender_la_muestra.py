"""BUG-0173 — extender la muestra de un modelo.

El diseño del run 3 era el del método: estimar sobre 2002-2019 y después
**extender** hasta 2026 incorporando los episodios nuevos por el nodo de
intervención, encadenando por el `.pre`. No había herramienta: hubo que editar a
mano el número de observaciones y el bloque de datos del `.inp`.

Los dos costes: equivocarse, y que **lo editado a mano no queda en el guion**, así
que el recorrido pierde el punto donde la muestra cambió — justo lo que hace
falta para leer después por qué el modelo se movió.

Es el tercer hueco de la misma familia. BUG-0162 (modificar una intervención) y
BUG-0170 (añadir un determinista) son el mismo hueso: el sistema sabe CONSTRUIR y
sabe ENCADENAR estructura, pero no sabía MODIFICAR lo que ya hay.
"""
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.pipeline import (ErrorDeExtension, _RESCALE_FACTOR, _write_inp,
                          estimar, extiende_muestra)


@pytest.fixture(scope="module")
def caso(tmp_path_factory):
    """Un modelo sobre las primeras 150 obs de una serie de 200, con de todo:
    armónicos, una intervención, AR(1) y media."""
    d = tmp_path_factory.mktemp("ext")
    rng = np.random.default_rng(11)
    n = 200
    y = 100.0 + np.cumsum(rng.standard_normal(n) * 0.4 + 0.12)
    y[80:] += -3.0
    completa = y.tolist()

    ts = fue.TimeSeries(completa[:150], freq=12, start=(2002, 1), name="EXT")
    itvs = [fue.Intervention("cos", at=0, omega=[0.0], omega_free=[True],
                             harmonic=1.0),
            fue.Intervention("sin", at=0, omega=[0.0], omega_free=[True],
                             harmonic=1.0),
            fue.Intervention("step", at=80, omega=[0.0], omega_free=[True])]
    f = str(d / "EXT_m00.inp")
    _write_inp(ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=True,
                             refactor=_RESCALE_FACTOR, ar=[[0.0]],
                             ar_free=[[True]], interventions=itvs), f)
    _, fit = estimar(f)
    fit.write_pre(f[:-4] + ".pre")
    return str(d), f[:-4] + ".pre", completa


def _firma(m):
    return (len(m.interventions or []), [i.type for i in (m.interventions or [])],
            [int(i.at) for i in (m.interventions or [])],
            list(m.ifadf or []), m.d, m.D, m.boxlam, bool(m.estimate_mu),
            [len(f) for f in (m.ar or [])], [len(f) for f in (m.ma or [])])


# ── lo que tiene que hacer ─────────────────────────────────────────────────

def test_extiende_y_conserva_la_especificacion_ENTERA(caso):
    d, pre, completa = caso
    out = os.path.join(d, "ext.inp")
    ts, m, n_add = extiende_muestra(pre, completa, out)
    assert n_add == 50 and ts.nobs == 200

    _, m0 = fue.load(pre)
    _, m1 = fue.load(out)
    assert _firma(m0) == _firma(m1), "la especificación cambió al extender"


def test_las_POSICIONES_de_las_intervenciones_no_se_mueven(caso):
    """Extender por el final no puede desplazar un suceso — que es BUG-0172 por
    otra vía."""
    d, pre, completa = caso
    out = os.path.join(d, "pos.inp")
    extiende_muestra(pre, completa, out)
    _, m1 = fue.load(out)
    step = [i for i in m1.interventions if i.type == "step"][0]
    assert int(step.at) == 80


def test_los_valores_quedan_como_SEMILLAS_y_no_se_reestima(caso):
    """Extender y reestimar son dos decisiones, y la segunda es del analista."""
    d, pre, completa = caso
    out = os.path.join(d, "sem.inp")
    extiende_muestra(pre, completa, out)
    _, m0 = fue.load(pre)
    _, m1 = fue.load(out)
    assert m1._result is None, "lo ha reestimado por su cuenta"
    assert abs(float(m1.ar[0][0]) - float(m0.ar[0][0])) < 1e-12
    assert abs(float(m1.mu0) - float(m0.mu0)) < 1e-12


def test_el_inp_extendido_SE_PUEDE_ESTIMAR(caso):
    """Si no, no sirve de nada."""
    d, pre, completa = caso
    out = os.path.join(d, "est.inp")
    extiende_muestra(pre, completa, out)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ts2, m2 = estimar(out)
    assert ts2.nobs == 200 and m2._result is not None


# ── y las dos NEGATIVAS, que son las que dan valor ────────────────────────

def test_se_NIEGA_si_la_serie_nueva_empieza_antes(caso):
    """Extender por el principio desplaza el `at` de todas las intervenciones:
    cada suceso quedaría en otra fecha."""
    d, pre, completa = caso
    otra = fue.TimeSeries(completa, freq=12, start=(2001, 1), name="EXT")
    with pytest.raises(ErrorDeExtension, match="empieza"):
        extiende_muestra(pre, otra, os.path.join(d, "no1.inp"))


def test_se_NIEGA_si_el_tramo_COMUN_no_coincide(caso):
    """No es esta serie extendida: es otra. Heredar una especificación ajustada
    sobre otros datos no significa nada."""
    d, pre, completa = caso
    cambiada = list(completa)
    cambiada[40] += 5.0
    with pytest.raises(ErrorDeExtension, match="tramo común"):
        extiende_muestra(pre, cambiada, os.path.join(d, "no2.inp"))


def test_se_NIEGA_si_es_mas_CORTA(caso):
    d, pre, completa = caso
    with pytest.raises(ErrorDeExtension, match="recortar"):
        extiende_muestra(pre, completa[:120], os.path.join(d, "no3.inp"))


def test_extender_con_la_MISMA_longitud_no_es_error(caso):
    """Cero observaciones nuevas es una extensión vacía, no un fallo: puede ser
    el resultado legítimo de refrescar un fichero que aún no trae datos nuevos."""
    d, pre, completa = caso
    _, _, n = extiende_muestra(pre, completa[:150], os.path.join(d, "cero.inp"))
    assert n == 0


# ── por la superficie ─────────────────────────────────────────────────────

def test_la_herramienta_MCP_existe_y_dice_que_NO_reestima(caso, tmp_path):
    import asyncio

    import art.mcp_server as srv
    from tests._texto import dice
    ts = asyncio.run(srv.mcp.list_tools())
    t = next((x for x in ts if x.name == "extend_sample"), None)
    assert t is not None, "la herramienta no está publicada"
    assert dice(t.description or "", "NO reestima")

    d, pre, completa = caso
    import csv
    csvf = tmp_path / "s.csv"
    with open(csvf, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["value"])
        for v in completa:
            w.writerow([v])
    fn = getattr(srv.extend_sample, "fn", srv.extend_sample)
    txt = "\n".join(getattr(x, "text", "")
                    for x in fn(pre, str(csvf), str(tmp_path / "o.inp")))
    assert "+50 observaciones" in txt and "No se ha reestimado" in txt


def test_la_negativa_llega_como_REGLA_y_no_como_averia(caso, tmp_path):
    """Un traceback se lee como «el programa está roto», no como «eso no se
    hace así» — la lección de BUG-0159."""
    import csv

    import art.mcp_server as srv
    d, pre, completa = caso
    mala = list(completa); mala[40] += 5.0
    csvf = tmp_path / "mala.csv"
    with open(csvf, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["value"])
        for v in mala:
            w.writerow([v])
    fn = getattr(srv.extend_sample, "fn", srv.extend_sample)
    txt = "\n".join(getattr(x, "text", "")
                    for x in fn(pre, str(csvf), str(tmp_path / "x.inp")))
    assert "Traceback" not in txt
    assert "no es extender esta serie" in txt.lower()
    assert "tramo común" in txt
