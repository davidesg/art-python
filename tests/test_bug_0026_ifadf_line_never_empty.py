"""BUG-0026 — la línea `ifadf` salía vacía y el .inp dejaba de poder leerse.

`ifadf` especifica las diferencias POR FRECUENCIA e indexa desde f=0, así que la
línea tiene `freq//2 + 1` entradas: `0 0 0` en trimestral, `0 0 0 0 0 0 0` en
mensual. El lector cuenta esas posiciones; si faltan, consume la línea siguiente
—la del Box-Cox— y revienta con int('1.00').

La guarda comprobaba `is None` y `fue.Model` guarda `[]`.
"""
import os
import tempfile

import numpy as np
import pytest

import fue
from art.pipeline import _write_inp, _load_ts_model


def _escribe(freq, n, ifadf=None):
    y = 100.0 + np.cumsum(np.random.default_rng(1).normal(0, 1.0, n))
    ts = fue.TimeSeries(list(map(float, y)), freq=freq, start=(2004, 1), name="T")
    kw = {} if ifadf is None else {"ifadf": ifadf}
    m = fue.Model(ts, d=1, **kw)
    d = tempfile.mkdtemp(prefix="bug0026-")
    p = os.path.join(d, "T.inp")
    _write_inp(ts, m, p)
    return p, m


def _linea_ifadf(path):
    txt = open(path).read().splitlines()
    k = next(i for i, l in enumerate(txt) if "Individual factors" in l)
    return txt[k + 1]


@pytest.mark.parametrize("freq,n", [(4, 40), (12, 60)])
def test_el_modelo_sin_ifadf_lo_guarda_como_lista_vacia(freq, n):
    """El valor real que la guarda `is None` no cubría."""
    _, m = _escribe(freq, n)
    assert m.ifadf == []


@pytest.mark.parametrize("freq,n", [(4, 40), (12, 60)])
def test_la_linea_nunca_queda_vacia_y_tiene_freq_medios_mas_uno(freq, n):
    p, _ = _escribe(freq, n)
    linea = _linea_ifadf(p)
    assert linea.split()                       # no vacía
    assert len(linea.split()) == freq // 2 + 1  # el invariante del formato


@pytest.mark.parametrize("freq,n", [(4, 40), (12, 60)])
def test_el_fichero_se_relee(freq, n):
    p, _ = _escribe(freq, n)
    ts2, m2 = _load_ts_model(p)                 # antes: ValueError int('1.00')
    assert ts2 is not None and m2 is not None


def test_un_ifadf_no_trivial_sobrevive_al_round_trip():
    """El arreglo no puede aplanar un ifadf que sí lleva frecuencias activas."""
    p, _ = _escribe(4, 40, ifadf=[0, 1, 0])
    assert _linea_ifadf(p).split() == ["0", "1", "0"]
    _, m2 = _load_ts_model(p)
    assert list(m2.ifadf) == [0, 1, 0]
