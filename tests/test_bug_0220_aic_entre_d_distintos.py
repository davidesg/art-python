"""BUG-0220 — el AIC de un modelo en d=2 junto a los de d=1, sin aviso.

`compare_versions` ya suprimía los Δ entre operadores distintos (BUG-0051); el
mapa del guion no: apilaba logL de ∇ y de ∇² en la misma columna, y su aviso de
muestra (BUG-0177) mira la n de la SERIE, que no cambia con d. Ahora el mapa
agrupa las versiones por operador y lo dice.
"""
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.pipeline import _RESCALE_FACTOR, _write_inp


def _T(r):
    return r if isinstance(r, str) else "\n".join(
        t for c in r if isinstance(t := getattr(c, "text", None), str))


def _fn(tool):
    return getattr(tool, "fn", tool)


@pytest.fixture(scope="module")
def recorrido(tmp_path_factory):
    d = tmp_path_factory.mktemp("b220")
    rng = np.random.default_rng(220)
    z = np.cumsum(0.002 + 0.003 * rng.standard_normal(216))
    ts = fue.TimeSeries(np.exp(4.5 + z).tolist(), freq=12, start=(2002, 1), name="ES")
    f = str(d / "ES.inp")
    _write_inp(ts, fue.Model(ts, d=1, boxlam=0.0, refactor=_RESCALE_FACTOR), f)
    g = str(d / "ES_guion.json")
    kw = dict(lam=0, D=0, n_harmonics=0, seasonal=False, domain="price_index",
              modo="autonomo", guion_path=g)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _fn(srv.confirm_and_estimate)(f, str(d / "m1.inp"), d=1, p=1, q=1,
                                      estimate_mu=True, **kw)
        _fn(srv.confirm_and_estimate)(f, str(d / "m2.inp"), d=2, p=1, q=1,
                                      estimate_mu=False, **kw)
    return d, g


def test_el_mapa_avisa_y_agrupa(recorrido):
    _, g = recorrido
    t = _T(_fn(srv.guion_map)(g))
    assert "mezcla operadores de diferenciación" in t
    assert "d=1, D=0: v1" in t and "d=2, D=0: v2" in t


def test_compare_versions_sigue_suprimiendo_el_delta(recorrido):
    d, _ = recorrido
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = _T(_fn(srv.compare_versions)(str(d / "m1.pre"), str(d / "m2.pre")))
    assert "NO son comparables" in t and "— no comp." in t


def test_un_solo_operador_no_avisa(tmp_path):
    from types import SimpleNamespace as NS
    e = [NS(version=v, spec={"lam": 0.0, "d": 1, "D": 0}, stats=object())
         for v in (1, 2)]
    assert len(srv._grupos_de_operador(e)) == 1
    e.append(NS(version=3, spec={"lam": 0.0, "d": 1, "D": 0, "ifadf": [0, 1]},
                stats=object()))
    assert len(srv._grupos_de_operador(e)) == 2


def test_el_html_avisa_y_marca_el_grupo_de_cada_cifra(recorrido):
    """La tabla de `export_guion` apilaba los AIC de d=1 y d=2 sin decirlo."""
    from art.guion import export_guion_html, load_guion
    _, g = recorrido
    h = export_guion_html(load_guion(g))
    assert "mezcla operadores de diferenciación" in h
    assert "<b>A</b> — λ=0, d=1, D=0: v1" in h and "<b>B</b> — λ=0, d=2, D=0: v2" in h
    assert h.count("<sup>A</sup>") == 2 and h.count("<sup>B</sup>") == 2


def test_el_html_de_un_solo_operador_no_avisa(tmp_path):
    from art.guion import Guion, export_guion_html
    assert "mezcla operadores" not in export_guion_html(
        Guion(series="X", analyst="", created="2026-10-07"))
