"""ORDEN 1.5 — el disparador va DONDE se decide, no en un párrafo previo.

Un recurso que sólo se anuncia en la cabecera se lee una vez, al abrir la
sesión, y para cuando hace falta ya salió de la ventana. Es la misma lección
que dejó el efecto de Semana Santa: **una opción que aparece cuando hace falta
vale más que cualquier párrafo que hay que haber leído antes.**

Y la otra mitad: se cita SÓLO cuando el caso lo pide. Un aviso que sale siempre
se ignora siempre.
"""
import pytest

pytest.importorskip("mcp")
fue = pytest.importorskip("fue")

import art.mcp_server as M


class _R:
    def __init__(self, npar=0, niter=None):
        self.npar, self.niter = npar, niter


class _M:
    def __init__(self, ar=None, interventions=None, npar=0, niter=None):
        self.ar = ar or []
        self.interventions = interventions or []
        self._result = _R(npar, niter)


def _citas(d=None, model=None, ruta="x.inp"):
    return [c for cond, c in M._citas_pertinentes(d or {}, model or _M(), ruta)
            if cond]


def test_un_AR_de_orden_2_dispara_la_cita_de_no_capar():
    c = _citas(model=_M(ar=[[0.5, -0.3]]))
    assert any("BUG-0103" in x for x in c), c
    assert any("Shin-Fuller" in x for x in c)


def test_con_intervenciones_dispara_la_del_cierre_del_nodo():
    c = _citas(model=_M(interventions=[object()]))
    assert any("BUG-0123" in x for x in c), c


def test_un_pre_dispara_la_de_los_errores_tipicos():
    c = _citas(model=_M(npar=6, niter=1), ruta="RATIO_m10.pre")
    assert any("BUG-0027" in x for x in c), c
    assert any("get_out_report" in x for x in c)


def test_pocas_ITERACIONES_la_disparan_aunque_sea_un_inp():
    """No es la extensión del fichero lo que decide: es que el optimizador
    apenas se moviera."""
    c = _citas(model=_M(npar=6, niter=0), ruta="m10.inp")
    assert any("BUG-0027" in x for x in c), c


# ────────── y la otra mitad: que NO salgan cuando no tocan ──────────

def test_un_modelo_limpio_y_sencillo_no_dispara_ninguna():
    """Un aviso que sale siempre se ignora siempre."""
    c = _citas(model=_M(ar=[[0.5]], npar=1, niter=40), ruta="m10.inp")
    assert not c, c


def test_las_citas_llevan_una_URI_pedible():
    """No basta con nombrar el defecto: hay que dar la forma de leerlo."""
    for m, ruta in ((_M(ar=[[0.5, -0.3]]), "x.inp"),
                    (_M(interventions=[object()]), "x.inp"),
                    (_M(npar=6, niter=1), "x.pre")):
        for c in _citas(model=m, ruta=ruta):
            assert "art://" in c or "get_out_report" in c, c
