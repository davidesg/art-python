"""BUG-0217 — guion_node: `coincide` por cadenas, sin «parcial», y parent=-1
colgando de un callejón.

- `propuesta="λ=0"`, `decidido="0 (logaritmos)"` salía «el analista la
  CORRIGIÓ»: es la misma decisión dicha de dos maneras.
- `coincide="parcial"` era un error.
- `parent=-1` colgaba el nodo de la última entrada aunque estuviera abandonada.
"""
import json
import os

import pytest

os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.guion import (Guion, GuionEntry, infer_parent, mismo_valor,
                       save_guion)


def _txt(out):
    return "\n".join(x if isinstance(x, str) else getattr(x, "text", "")
                     for x in out)


def _node(*a, **k):
    return _txt(getattr(srv.guion_node, "fn", srv.guion_node)(*a, **k))


def _ultima(gp):
    return json.load(open(gp))["entries"][-1]


@pytest.mark.parametrize("prop, dec, nodo", [
    ("λ=0", "0 (logaritmos)", "lambda"),
    ("λ=0", "log", "lambda"),
    ("lambda = 1", "1 (niveles)", "lambda"),
    ("d=1", "1", "d"),
    ("ARMA(1,1)", "arma (1, 1)", "ordenes"),
    ("0,5", "0.5", "lambda"),
])
def test_la_misma_decision_dicha_de_otra_forma_coincide(prop, dec, nodo):
    assert mismo_valor(prop, dec, nodo) is True


@pytest.mark.parametrize("prop, dec, nodo", [
    ("λ=0", "1 (niveles)", "lambda"),
    ("d=1", "d=2", "d"),
    ("ARMA(1,1)", "ARMA(1,2)", "ordenes"),
    ("B1", "B2", "estacionalidad"),
])
def test_una_correccion_de_verdad_sigue_siendo_correccion(prop, dec, nodo):
    assert mismo_valor(prop, dec, nodo) is False


def test_lo_que_no_se_puede_comparar_no_se_inventa():
    """Ni coincide ni corrige: no consta, y se pide `coincide` explícito."""
    assert mismo_valor("B2", "D=1 (diferencia estacional)", "estacionalidad") is None


def test_guion_node_no_dice_corrigio_sobre_la_misma_decision(tmp_path):
    gp = str(tmp_path / "g.json")
    _node(gp, "dominio", "price_index", razon="r", expectativas="e")
    t = _node(gp, "lambda", "0 (logaritmos)", razon="r", propuesta="λ=0")
    assert "CORRIGIÓ" not in t and "la tomó" in t
    assert _ultima(gp)["coincide"] is True


def test_guion_node_pide_coincide_cuando_no_puede_compararlo(tmp_path):
    gp = str(tmp_path / "g.json")
    t = _node(gp, "estacionalidad", "D=1 (diferencia estacional)", razon="r",
              propuesta="B2")
    assert _ultima(gp)["coincide"] is None
    assert "coincide=" in t


def test_coincide_parcial_se_admite_y_se_cuenta_aparte(tmp_path):
    gp = str(tmp_path / "g.json")
    t = _node(gp, "d", "1", razon="r", propuesta="1 y D=1", coincide="parcial")
    assert "Error" not in t and "parcial" in t.lower()
    assert _ultima(gp)["coincide"] == "parcial"
    mapa = _txt(getattr(srv.guion_map, "fn", srv.guion_map)(gp))
    assert "parcial" in mapa
    assert "corrigió 0" in mapa


def _e(v, parent, status="exploring", kind="model"):
    return GuionEntry(version=v, name=f"v{v}", inp_path="", timestamp="",
                      spec={}, stats=None, equation="", decision="",
                      rationale="", problems_found="", next_version="",
                      parent=parent, status=status, kind=kind)


def test_parent_menos_uno_no_cuelga_de_un_callejon(tmp_path):
    """Salamanca: n15 quedó bajo la v14 abandonada."""
    g = Guion(series="X", analyst="", created="2026-10-06")
    g.entries = [_e(12, None), _e(13, 12), _e(14, 13, status="dead-end")]
    assert infer_parent(g) == 13
    gp = str(tmp_path / "g.json")
    save_guion(g, gp)
    _node(gp, "reformulacion", "volver a v13", razon="v14 no blanquea")
    assert _ultima(gp)["parent"] == 13


def test_parent_menos_uno_sigue_siendo_la_ultima_si_esta_viva():
    g = Guion(series="X", analyst="", created="2026-10-06")
    g.entries = [_e(1, None), _e(2, 1, status="dead-end"), _e(3, 1)]
    assert infer_parent(g) == 3
