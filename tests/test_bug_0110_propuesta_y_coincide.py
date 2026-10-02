"""BUG-0110 — decided_by recorded the LANE, not who decided each node.

In the guided lane the analyst accepts some proposals and corrects others; that
difference is what the guion exists to keep, and it was lost (81 of 81 guiones
had one decider throughout). Each node now records the assistant's proposal
and whether the decision matched it; the lane goes once in the header; the map
and the HTML show the corrections.
"""
import json
import os

from art.guion import export_guion_html, load_guion


def _fn(name):
    from art import mcp_server as M
    t = getattr(M, name)
    return getattr(t, "fn", t)


def test_a_guided_guion_tells_accepted_from_corrected(tmp_path):
    gp = str(tmp_path / "S_guion.json")
    node = _fn("guion_node")
    t = node(gp, "lambda", "0", "precio: logs", decidido_por="analista+LLM",
             propuesta="1", coincide="no")
    assert "el analista la CORRIGIÓ" in t[0].text
    node(gp, "d", "1", "ADF y KPSS", decidido_por="analista+LLM", propuesta="1")
    node(gp, "ordenes", "AR(6)", "el operador entero", decidido_por="analista+LLM",
         propuesta="AR(6) capado", coincide="no")
    g = load_guion(gp)
    assert g.carril == "guiado"
    assert [e.coincide for e in g.entries] == [False, True, False]
    assert g.entries[0].propuesta == "1"
    raw = json.load(open(gp))
    assert raw["carril"] == "guiado" and raw["entries"][1]["coincide"] is True
    m = _fn("guion_map")(gp)[0].text
    assert "✎ corregido" in m and "el asistente propuso: AR(6) capado" in m
    assert "el analista corrigió 2: n1 lambda, n3 ordenes" in m
    html = export_guion_html(g)
    assert "corregida por el analista" in html


def test_coincide_is_checked_and_old_guiones_still_load(tmp_path):
    gp = str(tmp_path / "T_guion.json")
    out = _fn("guion_node")(gp, "d", "1", "x", coincide="quizá")
    assert "`coincide` es «sí» o «no»" in out[0].text
    _fn("guion_node")(gp, "d", "1", "x", decidido_por="LLM")
    g = load_guion(gp)
    assert g.carril == "autonomo" and g.entries[0].coincide is None
    raw = json.load(open(gp))
    del raw["carril"]
    for e in raw["entries"]:
        e.pop("propuesta", None)
        e.pop("coincide", None)
    json.dump(raw, open(gp, "w"))
    g = load_guion(gp)
    assert g.carril == "" and g.entries[0].coincide is None
