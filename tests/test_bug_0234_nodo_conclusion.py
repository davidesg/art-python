"""BUG-0234 — guion_map contaba como «decisión sin modelo estimado detrás» un
nodo que CONCLUYE sobre modelos ya estimados.

Salamanca: tras el AR(4) y el IMA(1), el analista escribe `d = ambiguo: I(1)
con el AR(4), I(2) con el IMA(1)` colgado del modelo adoptado. No especifica
nada que estimar. Por su forma —nodo de especificación colgado de un modelo,
sin nada debajo— es indistinguible de una reformulación pendiente, así que
la conclusión se declara: `guion_node(..., conclusion=True)`.
"""
import os

os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.guion import (Guion, GuionEntry, GuionStats, especificadas_sin_estimar,
                       load_guion, save_guion)

_node = getattr(srv.guion_node, "fn", srv.guion_node)
_map = getattr(srv.guion_map, "fn", srv.guion_map)


def _txt(r):
    return "\n".join(getattr(c, "text", "") or "" for c in r)


def _modelo(v, parent):
    return GuionEntry(version=v, name=f"m{v}", inp_path="", timestamp="",
                      spec={}, stats=GuionStats(loglik=-1.0, q_pass=True,
                                                jb_pass=True),
                      equation="", decision="", rationale="",
                      problems_found="", next_version="", parent=parent,
                      instrumento="x")


def _guion(tmp_path):
    """Dos modelos estimados, el segundo hijo del primero."""
    g = Guion(series="Salamanca", analyst="", created="2026-10-08")
    g.entries = [_modelo(1, None), _modelo(2, 1)]
    gp = str(tmp_path / "g.json")
    save_guion(g, gp)
    return gp


def test_una_conclusion_colgada_de_un_modelo_no_es_una_decision_pendiente(tmp_path):
    gp = _guion(tmp_path)
    r = _txt(_node(gp, "d", "ambiguo: I(1) con el AR(4), I(2) con el IMA(1)",
                   razon="los dos modelos son adecuados", parent=2,
                   conclusion=True))
    assert "conclusión sobre v2" in r
    assert especificadas_sin_estimar(load_guion(gp)) == []
    m = _txt(_map(gp))
    assert "sin modelo estimado" not in m
    assert "∎ conclusión" in m


def test_sin_la_marca_sigue_contando(tmp_path):
    """BUG-0221 sigue en pie: «d = 2» colgado de un modelo es una
    reformulación que falta estimar."""
    gp = _guion(tmp_path)
    _node(gp, "d", "2", razon="probar I(2)", parent=2)
    assert len(especificadas_sin_estimar(load_guion(gp))) == 1
    assert "1 decisión sin modelo estimado detrás" in _txt(_map(gp))


def test_una_conclusion_tiene_que_colgar_de_un_modelo(tmp_path):
    gp = _guion(tmp_path)
    _node(gp, "ordenes", "AR(1)", razon="r", parent=2)          # n3, nodo
    r = _txt(_node(gp, "d", "ambiguo", razon="r", parent=3, conclusion=True))
    assert "cuelga de uno" in r and "n3" in r
    assert len(load_guion(gp).entries) == 3
