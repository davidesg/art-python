"""Los NODOS DE DECISIÓN del guion, y el contraste entre dos recorridos.

Un guion que registra sólo MODELOS empieza a contar la historia tarde. Cuando
existe el primer modelo estimado ya se decidió λ, se decidió d, se decidió si
hay estacionalidad y de qué tipo, y se eligieron los órdenes — y nada de eso
dejaba rastro. Sobre PGAS de la réplica del TFM la divergencia ENTERA entre los
dos carriles está en λ, que se decide antes del primer modelo: el guion no podía
enseñarla.

Nodos y modelos van en la MISMA cadena porque el orden en que ocurrieron es
información: un nodo después de un modelo es una reformulación.

Y `decided_by` es lo que hace comparables dos guiones. El protocolo es el mismo
en los dos carriles y los nodos son los mismos; lo único que cambia es quién
decidió cada uno.
"""
import json
import os

import pytest

from art import mcp_server as M
from art.guion import (Guion, GuionEntry, load_guion, diff_nodes,
                       nodes as g_nodes, models as g_models)


def _txt(res):
    return res[0].text


# ── el registro ─────────────────────────────────────────────────────────────

def test_a_node_is_recorded_without_a_model(tmp_path):
    gp = str(tmp_path / "S_guion.json")
    out = _txt(M.guion_node(gp, nodo="lambda", decidido="0",
                            razon="es un índice de precios; la base es una convención",
                            evidencia="gap=+0.161", decidido_por="LLM"))
    assert "lambda" in out and "0" in out

    g = load_guion(gp)
    assert len(g_nodes(g)) == 1
    assert len(g_models(g)) == 0
    n = g_nodes(g)[0]
    assert n.is_node and n.stats is None
    assert n.node["evidencia"] == "gap=+0.161"
    assert n.decided_by == "LLM"


def test_the_reason_is_required(tmp_path):
    """Misma exigencia que `why` en guion_abandon: una decisión sin su razón es
    un número, y un número no se puede discutir después."""
    gp = str(tmp_path / "S_guion.json")
    out = _txt(M.guion_node(gp, nodo="d", decidido="1", razon="   "))
    assert "obligatoria" in out.lower() or "error" in out.lower()
    assert not os.path.exists(gp) or not g_nodes(load_guion(gp))


def test_nodes_chain_like_versions(tmp_path):
    gp = str(tmp_path / "S_guion.json")
    for nodo, val in (("lambda", "0"), ("d", "1"), ("ordenes", "ARMA(1,0)")):
        M.guion_node(gp, nodo=nodo, decidido=val, razon="porque sí, en el test")
    g = load_guion(gp)
    vs = [e.version for e in g.entries]
    assert vs == [1, 2, 3]
    assert [e.parent for e in g.entries] == [None, 1, 2]


def test_old_guiones_without_nodes_still_load(tmp_path):
    """Compatibilidad: un guion escrito antes de que existieran los nodos se
    lee como una cadena de modelos, sin campos que no tenía."""
    viejo = {"series": "S", "analyst": "", "created": "2026-01-01", "entries": [{
        "version": 1, "name": "m00", "inp_path": "/x/m00.inp", "timestamp": "t",
        "spec": {}, "stats": {"loglik": -1.0, "aic": 4.0, "bic": 5.0,
                              "sigma_a": 1.0, "q_pass": True, "jb_pass": True,
                              "n_extreme": 0, "extreme": []},
        "equation": "", "decision": "", "rationale": "", "problems_found": "",
        "next_version": "", "figure_b64": None, "parent": None,
        "status": "exploring", "why_abandoned": ""}]}
    gp = tmp_path / "S_guion.json"
    gp.write_text(json.dumps(viejo))
    g = load_guion(str(gp))
    assert len(g_models(g)) == 1 and len(g_nodes(g)) == 0
    assert g.entries[0].kind == "model"


# ── el mapa ─────────────────────────────────────────────────────────────────

def test_the_map_draws_nodes_and_models_in_one_chain(tmp_path):
    gp = str(tmp_path / "S_guion.json")
    M.guion_node(gp, nodo="lambda", decidido="0", razon="índice de precios",
                 evidencia="gap=+0.16", decidido_por="LLM")
    M.guion_node(gp, nodo="d", decidido="1", razon="paseo aleatorio claro",
                 decidido_por="LLM")
    mapa = _txt(M.guion_map(gp))
    assert "◆ n1 lambda = 0" in mapa
    assert "◆ n2 d = 1" in mapa
    assert "gap=+0.16" in mapa
    assert "índice de precios" in mapa
    assert "nodo de decisión" in mapa


# ── el contraste ────────────────────────────────────────────────────────────

def _guion_con(nodos, quien):
    from datetime import datetime
    g = Guion(series="S", analyst="", created="2026-01-01")
    for i, (nombre, val, razon) in enumerate(nodos, start=1):
        g.entries.append(GuionEntry(
            version=i, name=nombre, inp_path="", timestamp="t", spec={},
            stats=None, equation="", decision="", rationale=razon,
            problems_found="", next_version="",
            parent=(i - 1) or None, kind="node",
            node={"nodo": nombre, "decidido": val, "evidencia": "",
                  "alternativas": ""},
            decided_by=quien))
    return g


def test_diff_localises_the_divergence_and_carries_both_reasons():
    a = _guion_con([("lambda", "0", "índice: la base es convención"),
                    ("d", "1", "paseo aleatorio"),
                    ("ordenes", "ARMA(1,0)", "persistencia de precios")],
                   "analista+LLM")
    b = _guion_con([("lambda", "1", "el gap sale negativo"),
                    ("d", "1", "ADF no rechaza"),
                    ("ordenes", "ARMA(0,1)", "el spec en cabeza")],
                   "heurística")
    filas = diff_nodes(a, b, "guiado", "autónomo")
    por = {f["nodo"]: f for f in filas}
    assert por["lambda"]["veredicto"] == "divergen"
    assert por["d"]["veredicto"] == "coinciden"
    assert por["ordenes"]["veredicto"] == "divergen"
    # las DOS razones viajan con la divergencia
    assert "convención" in por["lambda"]["razon_a"]
    assert "gap" in por["lambda"]["razon_b"]
    assert por["lambda"]["decidio_a"] == "analista+LLM"
    assert por["lambda"]["decidio_b"] == "heurística"


def test_diff_reports_a_node_only_one_lane_visited():
    """Un nodo que sólo visita un carril no es un hueco del registro: es que un
    recorrido volvió sobre una decisión y el otro no. Eso es el método iterando."""
    a = _guion_con([("lambda", "0", "r"), ("reformulacion", "AR(1)_4", "Q rechaza en 4, 8")],
                   "LLM")
    b = _guion_con([("lambda", "0", "r")], "heurística")
    filas = diff_nodes(a, b, "A", "B")
    solos = [f for f in filas if f["veredicto"].startswith("sólo")]
    assert len(solos) == 1
    assert solos[0]["nodo"] == "reformulacion"
    assert solos[0]["veredicto"] == "sólo A"


def test_a_node_visited_twice_is_compared_in_order():
    """Volver sobre λ es una reformulación, no la misma decisión otra vez."""
    a = _guion_con([("lambda", "1", "primera lectura"),
                    ("lambda", "0", "JB rechaza: heterocedasticidad")], "LLM")
    b = _guion_con([("lambda", "1", "el gap sale negativo")], "heurística")
    filas = diff_nodes(a, b, "A", "B")
    nombres = [f["nodo"] for f in filas]
    assert any("visita 1" in n for n in nombres)
    assert any("visita 2" in n for n in nombres)


def test_diff_says_so_when_neither_side_recorded_nodes(tmp_path):
    from datetime import datetime
    for nombre in ("a", "b"):
        g = Guion(series="S", analyst="", created="2026-01-01")
        (tmp_path / f"{nombre}.json").write_text(json.dumps(g.to_dict()))
    out = _txt(M.guion_diff(str(tmp_path / "a.json"), str(tmp_path / "b.json")))
    assert "guion_node" in out


# ── el carril por lotes también registra sus nodos ──────────────────────────

def test_build_model_records_its_specification_nodes(tmp_path):
    import numpy as np
    import fue
    from art.pipeline import _make_model, _write_inp

    rng = np.random.default_rng(5)
    level = 100.0 + np.cumsum(rng.standard_normal(80))
    ts = fue.TimeSeries(level.tolist(), freq=4, start=(2004, 1), name="RW")
    src = str(tmp_path / "rw.inp")
    _write_inp(ts, _make_model(ts, 1.0, 1, 0, 0, 1, 0), src)

    out = str(tmp_path / "run" / "rw_auto.inp")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    M.build_model(src, out, run_meg=False, guion_name="auto")

    g = load_guion(str(tmp_path / "run" / "RW_guion.json"))
    nombres = [(e.node or {}).get("nodo") for e in g_nodes(g)]
    for esperado in ("lambda", "d", "estacionalidad", "ordenes", "media"):
        assert esperado in nombres, f"falta el nodo {esperado}"
    # los nodos van ANTES del primer modelo
    primer_modelo = min(e.version for e in g_models(g))
    assert all(n.version < primer_modelo for n in g_nodes(g))
    # y el carril por lotes se declara heurística
    assert all(n.decided_by == "heurística" for n in g_nodes(g))
