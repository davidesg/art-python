"""La iteración existe, se cuenta y se sabe incompleta.

Hallazgo #5 de la revisión con contexto limpio: *«la iteración no existe como
entidad»*. Sobre el mismo corpus había **tres** respuestas defendibles a
«¿cuántas iteraciones tuvo este análisis?» —una por entrada (1.181), una por
modelo (565), una por nodo (616)— y el código no elegía ninguna.

La regla, que es la del método y no una convención de programación: una
iteración es UNA vuelta por las cuatro etapas —especificación, estimación,
diagnosis, reformulación—. Un MODELO estimado la cierra y se lleva el número;
los NODOS de decisión que lo preceden son su etapa 1 y llevan ese mismo número.
Por eso un nodo puede contener varias iteraciones (medido: hasta 9) y una
iteración no puede contener varios nodos.
"""
import json
import os

import pytest

from art.guion import (Guion, GuionEntry, GuionStats, iteraciones, load_guion,
                       modelos_sin_registrar, numera_iteraciones, save_guion)


def _e(v, nombre, kind="model", nodo=None, ll=-1.0, inp=""):
    st = None if kind == "node" else GuionStats(loglik=ll, aic=1.0, bic=2.0,
                                                sigma_a=0.1, q_pass=True,
                                                jb_pass=True, n_extreme=0)
    return GuionEntry(version=v, name=nombre, inp_path=inp, timestamp="t",
                      spec={}, stats=st, equation="", decision="", rationale="",
                      problems_found="", next_version="", kind=kind,
                      node={"nodo": nodo} if kind == "node" else None)


def _guion(*entries):
    g = Guion(series="S", analyst="", created="2026-01-01")
    g.entries.extend(entries)
    return g


# ── la numeración ─────────────────────────────────────────────────────

def test_un_modelo_cierra_una_iteracion():
    g = _guion(_e(1, "m00"), _e(2, "m01"), _e(3, "m02"))
    assert [i.numero for i in iteraciones(g)] == [1, 2, 3]


def test_los_nodos_que_preceden_son_la_etapa_1_del_mismo_numero():
    """No son iteraciones aparte: son la especificación de la que viene."""
    g = _guion(_e(1, "lambda", "node", "lambda"),
               _e(2, "d", "node", "d"),
               _e(3, "m00"))
    its = iteraciones(g)
    assert len(its) == 1
    assert its[0].numero == 1
    assert [e.name for e in its[0].especificacion] == ["lambda", "d"]
    assert its[0].modelo.name == "m00"


def test_un_nodo_puede_contener_varias_iteraciones():
    """Es la afirmación del analista, y el corpus la sostiene: hasta 9."""
    g = _guion(_e(1, "ordenes", "node", "ordenes"),
               _e(2, "m01"), _e(3, "m02"), _e(4, "m03"))
    its = iteraciones(g)
    assert len(its) == 3
    assert {i.nodo for i in its} == {"ordenes"}


def test_una_iteracion_no_contiene_dos_nodos():
    g = _guion(_e(1, "lambda", "node", "lambda"), _e(2, "m00"),
               _e(3, "ordenes", "node", "ordenes"), _e(4, "m01"))
    its = iteraciones(g)
    assert [i.nodo for i in its] == ["lambda", "ordenes"]


def test_una_especificacion_sin_estimar_es_una_iteracion_abierta():
    g = _guion(_e(1, "m00"), _e(2, "intervenciones", "node", "intervenciones"))
    its = iteraciones(g)
    assert len(its) == 2
    assert its[0].cerrada and not its[1].cerrada
    assert its[1].estado == "sin estimar"


def test_la_cuenta_es_UNA():
    """La prueba de fuego del encargo."""
    g = _guion(_e(1, "lambda", "node", "lambda"), _e(2, "m00"),
               _e(3, "m01"), _e(4, "ordenes", "node", "ordenes"), _e(5, "m02"))
    assert len([i for i in iteraciones(g) if i.cerrada]) == 3


# ── la semilla y la dirección ─────────────────────────────────────────

def test_la_iteracion_lleva_su_semilla():
    """«Lleva una semilla y se mueve en una dirección» — la semilla es el
    `.pre` de partida, que desde el BUG-0098 es campo de la entrada."""
    e = _e(2, "m01")
    e.base_pre_path = "/x/S_m00.pre"
    g = _guion(_e(1, "m00"), e)
    assert iteraciones(g)[1].semilla == "/x/S_m00.pre"


def test_la_decision_es_obligatoria_en_el_sentido_de_que_se_lee():
    e = _e(1, "m00")
    e.decision = "adoptar AR(1)"
    assert iteraciones(_guion(e))[0].decision == "adoptar AR(1)"


# ── persistencia y derivación ─────────────────────────────────────────

def test_se_estampa_al_escribir(tmp_path):
    g = _guion(_e(1, "lambda", "node", "lambda"), _e(2, "m00"))
    gp = str(tmp_path / "S_guion.json")
    save_guion(g, gp)
    d = json.load(open(gp))
    assert [e["iteracion"] for e in d["entries"]] == [1, 1]
    assert d["entries"][0]["nodo"] == "lambda"


def test_un_guion_viejo_se_numera_al_leerlo_sin_reescribirlo(tmp_path):
    """Es una DERIVACIÓN: el orden ya lleva la información."""
    viejo = {"series": "S", "analyst": "", "created": "2025-01-01", "entries": [
        {"version": 1, "name": "m00", "inp_path": "", "timestamp": "t",
         "spec": {}, "stats": None, "equation": "", "decision": "",
         "rationale": "", "problems_found": "", "next_version": ""},
        {"version": 2, "name": "m01", "inp_path": "", "timestamp": "t",
         "spec": {}, "stats": None, "equation": "", "decision": "",
         "rationale": "", "problems_found": "", "next_version": ""}]}
    gp = tmp_path / "S_guion.json"
    gp.write_text(json.dumps(viejo))
    antes = gp.read_text()
    g = load_guion(str(gp))
    assert [e.iteracion for e in g.entries] == [1, 2]
    assert gp.read_text() == antes, "leer no puede reescribir el registro"


def test_un_numero_ya_escrito_manda_sobre_el_derivado():
    """Lo estampó quien estaba allí."""
    e1, e2 = _e(1, "m00"), _e(2, "m01")
    e1.iteracion = 7
    g = _guion(e1, e2)
    numera_iteraciones(g)
    assert e1.iteracion == 7


# ── el registro se sabe incompleto ────────────────────────────────────

def test_detecta_los_modelos_estimados_que_no_estan_en_el_registro(tmp_path):
    for n in ("m00", "m01", "m02_fact"):
        (tmp_path / f"S_{n}.inp").write_text("x")
        (tmp_path / f"S_{n}.out").write_text("x")
    g = _guion(_e(1, "m00", inp=str(tmp_path / "S_m00.inp")),
               _e(2, "m01", inp=str(tmp_path / "S_m01.inp")))
    gp = str(tmp_path / "S_guion.json")
    save_guion(g, gp)
    sueltos = modelos_sin_registrar(load_guion(gp), gp)
    assert [os.path.basename(s) for s in sueltos] == ["S_m02_fact.inp"]


def test_un_inp_sin_estimar_no_cuenta(tmp_path):
    """Un `.inp` sin `.out` es una especificación escrita, no una iteración."""
    (tmp_path / "S_m00.inp").write_text("x")
    (tmp_path / "S_borrador.inp").write_text("x")     # sin .out
    g = _guion(_e(1, "m00", inp=str(tmp_path / "S_m00.inp")))
    gp = str(tmp_path / "S_guion.json")
    save_guion(g, gp)
    assert modelos_sin_registrar(load_guion(gp), gp) == []


def test_el_caso_real_que_lo_destapo():
    """UEM_FOOD_SERV_DS: caso que salió bien, 13 modelos con terna en disco y 9
    en el guion. El que falta al final es el FINAL."""
    p = os.path.expanduser("~/Dropbox/SRC/DVR/cases/UEM_FOOD_SERV_DS/"
                           "food/work/FOOD_UEM_guion.json")
    if not os.path.exists(p):
        pytest.skip("el caso no está en esta máquina")
    g = load_guion(p)
    faltan = [os.path.basename(x) for x in modelos_sin_registrar(g, p)]
    assert "FOOD_UEM_m11_fact.inp" in faltan
    assert len([i for i in iteraciones(g) if i.cerrada]) == 9


# ── el sobre, donde toca ──────────────────────────────────────────────

def test_las_seis_que_cierran_iteracion_llevan_sobre():
    """El denominador no es 46: 40 de las herramientas son INSTRUMENTOS y
    ponerle una «reformulación» a un ACF sería inventarla. Cierran iteración
    las que escriben en el guion, y son seis."""
    from tests._fuente import cuerpo_de
    import art.mcp_server as srv
    for nombre in ("estimate_and_diagnose", "confirm_and_estimate",
                   "suggest_intervention_form", "build_model",
                   "meg_reformulate", "record_version"):
        t = getattr(srv, nombre)
        src = cuerpo_de(getattr(t, "fn", t))
        assert "envuelve_iteracion(" in src, f"{nombre} cierra iteración sin sobre"


def test_las_que_cierran_iteracion_son_las_que_registran():
    """Si mañana una séptima escribe en el guion, esta prueba lo dice."""
    import pathlib
    src = pathlib.Path("src/art/mcp_server.py").read_text()
    n_reg = src.count("_record_to_guion(")      # 1 def + llamadas
    n_sobre = src.count("envuelve_iteracion(")  # 1 def + llamadas
    assert n_sobre - 1 == 6
    assert n_reg - 1 == 7, "build_model registra en dos ramas"
