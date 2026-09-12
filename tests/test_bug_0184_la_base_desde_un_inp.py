"""BUG-0184 — regresión de BUG-0175: encadenar desde un `.inp` dejaba huérfano.

BUG-0175 hizo que el padre se reconociera por la HUELLA de su `.pre`. Pero
`suggest_intervention_form` y `meg_reformulate` encadenan desde el `.inp` del
padre, y se guardaba la huella de ese `.inp`. `.inp` contra `.pre` no cuadra
nunca: `infer_parent` concluía «ninguno es el padre» y cada modelo con
intervención quedaba como RAÍZ del árbol. En run6 y run7, cuatro entradas cada
uno. Los tests de BUG-0175 sólo encadenaban desde `.pre`.
"""
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as M
from art.guion import (Guion, GuionEntry, linaje_dudoso, load_guion,
                       pre_de_la_base, sha_del_fichero)
from art.pipeline import _write_bare_inp


def _fn(n):
    f = getattr(M, n)
    return getattr(f, "fn", f)


@pytest.fixture(scope="module")
def cadena(tmp_path_factory):
    """El recorrido real: modelo base, y una intervención sobre su `.inp`."""
    d = tmp_path_factory.mktemp("cadena")
    r = np.random.default_rng(21)
    n = 120
    ly = np.log(100.0) + np.cumsum(0.002 + 0.003 * r.standard_normal(n))
    ly[60:] += 0.03                                     # un escalón que intervenir
    ts = fue.TimeSeries(np.exp(ly).tolist(), freq=12, start=(2010, 1), name="S")
    base = str(d / "S.inp")
    gp = str(d / "S_guion.json")
    warnings.simplefilter("ignore")
    _write_bare_inp(ts, base)
    _fn("confirm_and_estimate")(inp_path=base, output_path=str(d / "m0.inp"),
                                lam=0.0, d=1, D=0, p=1, q=0, n_harmonics=0,
                                estimate_mu=True, guion_path=gp)
    _fn("suggest_intervention_form")(str(d / "m0.inp"), str(d / "m1.inp"),
                                     date="01/2015", form="step", guion_path=gp)
    return d, gp


def test_la_intervencion_cuelga_de_su_modelo_base(cadena):
    """EL DEFECTO: el modelo con intervención salía con parent=None."""
    d, gp = cadena
    g = load_guion(gp)
    m0 = [e for e in g.entries if e.inp_path.endswith("m0.inp")][0]
    m1 = [e for e in g.entries if e.inp_path.endswith("m1.inp")][0]
    assert m1.base_pre_path.endswith(".inp"), "el caso que se prueba: base = .inp"
    assert m1.parent == m0.version, (
        f"el modelo con intervención quedó huérfano (parent={m1.parent})")


def test_la_huella_de_la_base_es_la_de_su_pre(cadena):
    d, gp = cadena
    g = load_guion(gp)
    m0 = [e for e in g.entries if e.inp_path.endswith("m0.inp")][0]
    m1 = [e for e in g.entries if e.inp_path.endswith("m1.inp")][0]
    assert m1.base_pre_sha == m0.pre_sha


def test_sigue_detectando_un_pre_reescrito(cadena, tmp_path):
    """Lo que BUG-0175 protege no se pierde: si el `.pre` de la base cambia
    después de encadenar, se dice."""
    d, gp = cadena
    g = load_guion(gp)
    assert linaje_dudoso(g) == []
    pre = str(d / "m0.pre")
    original = open(pre, encoding="latin-1").read()
    try:
        open(pre, "a", encoding="latin-1").write("\n* retocado\n")
        assert any(m == "el fichero ha cambiado" for _, m in linaje_dudoso(load_guion(gp)))
    finally:
        open(pre, "w", encoding="latin-1").write(original)


def test_un_guion_escrito_entre_0175_y_0184_no_da_falsa_alarma(tmp_path):
    """Esos guiones guardaron la huella del `.inp`. No han cambiado nada, y no
    pueden salir como «el fichero ha cambiado» por el convenio con que se
    escribieron."""
    inp = tmp_path / "m0.inp"
    inp.write_text("especificación\n")
    (tmp_path / "m0.pre").write_text("óptimo\n")
    g = Guion(series="S", analyst="", created="2026-09-12")
    g.entries.append(GuionEntry(
        version=1, name="m1", inp_path=str(tmp_path / "m1.inp"), timestamp="t",
        spec={}, stats=None, equation="", decision="", rationale="",
        problems_found="", next_version="", parent=None,
        base_pre_path=str(inp), base_pre_sha=sha_del_fichero(str(inp))))
    assert linaje_dudoso(g) == []


def test_la_base_se_normaliza_a_su_pre():
    assert pre_de_la_base("/w/m0.inp").endswith("/w/m0.pre")
    assert pre_de_la_base("/w/m0.pre").endswith("/w/m0.pre")
