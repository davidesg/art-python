"""BUG-0221 — guion_map afirmaba «1 especificada(s) sin estimar» con todas las
versiones estimadas.

La cuenta tomaba como iteración abierta cualquier grupo de NODOS sin modelo
detrás. Un nodo final que no especifica nada —la previsión, la conclusión, el
dominio— no es un modelo pendiente. Medido sobre el guion de la P04 (ES_CPI):
el nodo «prevision» que cierra el recorrido.
"""
import os

os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.guion import (Guion, GuionEntry, GuionStats, especificadas_sin_estimar,
                       save_guion)


def _nodo(v, nodo, parent):
    return GuionEntry(version=v, name=nodo, inp_path="", timestamp="", spec={},
                      stats=None, equation="", decision=f"{nodo} = x",
                      rationale="r", problems_found="", next_version="",
                      kind="node", node={"nodo": nodo, "decidido": "x"},
                      parent=parent)


def _modelo(v, parent):
    return GuionEntry(version=v, name=f"m{v}", inp_path="", timestamp="",
                      spec={}, stats=GuionStats(loglik=-1.0, q_pass=True,
                                                jb_pass=True),
                      equation="", decision="", rationale="",
                      problems_found="", next_version="", parent=parent,
                      instrumento="x")


def _mapa(g, tmp_path):
    gp = str(tmp_path / "g.json")
    save_guion(g, gp)
    return "\n".join(x.text for x in
                     getattr(srv.guion_map, "fn", srv.guion_map)(gp))


def _guion(*entries):
    g = Guion(series="X", analyst="", created="2026-10-06")
    g.entries = list(entries)
    return g


def test_un_nodo_final_que_no_especifica_no_es_un_modelo_pendiente(tmp_path):
    g = _guion(_nodo(1, "dominio", None), _nodo(2, "lambda", 1),
               _nodo(3, "ordenes", 2), _modelo(4, 3), _modelo(5, 4),
               _nodo(6, "prevision", 5))
    assert especificadas_sin_estimar(g) == []
    assert "sin estimar" not in _mapa(g, tmp_path)


def test_una_especificacion_pendiente_si_se_cuenta_y_se_nombra(tmp_path):
    g = _guion(_nodo(1, "lambda", None), _modelo(2, 1),
               _nodo(3, "ordenes", 2))
    abiertas = especificadas_sin_estimar(g)
    assert len(abiertas) == 1
    m = _mapa(g, tmp_path)
    assert "1 especificada(s) sin estimar" in m and "n3 ordenes" in m


def test_el_guion_de_la_P04_no_tiene_ninguna(tmp_path):
    """La forma del guion real de la clase: 5 nodos, 4 modelos, una
    reinscripción y el nodo de previsión al final."""
    g = _guion(_nodo(1, "dominio", None), _nodo(2, "lambda", 1),
               _nodo(3, "d", 2), _nodo(4, "estacionalidad", 3),
               _nodo(5, "ordenes", 4), _modelo(6, 5), _nodo(7, "ordenes", 6),
               _modelo(8, 7), _modelo(9, 8), _modelo(10, 9), _modelo(11, 8),
               _nodo(12, "prevision", 11))
    g.entries[10].re_registro_de = 8
    assert especificadas_sin_estimar(g) == []
    assert "sin estimar" not in _mapa(g, tmp_path)
