"""F4 — el nodo de intervención cableado en el protocolo, los dos carriles.

Carril GUIADO: `suggest_intervention_form(form="auto")` corre la escalera de
Ockham en vez de la vieja comprobación de adyacencia, y deja el NODO de
decisión en el guion con las alternativas descartadas y la razón de cada
descarte.

Carril AUTÓNOMO: `decide_interventions` devuelve `(at, forma, n_omega)` con la
duración del episodio dentro. Ahí NO se corre la escalera entera —serían tres
estimaciones por atípico y por ronda, dentro del bucle— sino su parte gratis:
cuántos ω lleva la intervención.
"""
import json
import os
import tempfile

import numpy as np
import pytest

fue = pytest.importorskip("fue")
from art.pipeline import _write_inp
from art.policy import decide_interventions, DefaultPolicy


# ───────────────── carril autónomo ─────────────────

def test_un_atipico_suelto_sigue_siendo_una_forma_escalar():
    assert decide_interventions([(40, 4.5)], [], offset=0) == [(39, "pulse", 1)]


def test_un_episodio_de_dos_es_UNA_intervencion_con_tres_escalones():
    """Antes eran dos espigas independientes; ahora es un suceso."""
    assert decide_interventions([(60, 5.0), (61, -4.2)], [], offset=0) \
        == [(59, "step", 3)]


def test_el_desfase_de_la_diferenciacion_entra_en_la_duracion_y_en_la_fecha():
    """Con d=1, tres extremos en ∇ son DOS períodos en el nivel ⇒ 3 escalones,
    y la fecha lleva el desfase (BUG-0030)."""
    r = decide_interventions([(60, 5.0), (61, -4.2), (62, 3.6)], [],
                             offset=1, d=1)
    assert r == [(60, "step", 3)]


def test_dos_sucesos_separados_no_se_mezclan():
    r = decide_interventions([(60, 5.0), (61, -4.2), (120, 4.0)], [], offset=0)
    assert r == [(59, "step", 3), (119, "pulse", 1)]


def test_un_extremo_dentro_de_un_episodio_ya_cubierto_no_se_añade_aparte():
    """La forma general del episodio ya lo representa: añadirlo suelto sería
    intervenir dos veces la misma cosa."""
    r = decide_interventions([(60, 5.0), (61, -4.2)], [], offset=0)
    assert len(r) == 1, "un suceso, una intervención"


def test_la_politica_lo_expone_igual():
    assert DefaultPolicy().decide_interventions([(60, 5.0), (61, -4.2)], [],
                                                offset=0) == [(59, "step", 3)]


def test_make_model_acepta_la_tripleta_y_tambien_el_par_antiguo():
    from art.pipeline import _make_model
    y = np.random.default_rng(0).standard_normal(120)
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="s")

    m3 = _make_model(ts, lam=1.0, d=0, D=0, p=0, q=0, n_harmonics=0,
                     extra_itvs=[(60, "step", 3)])
    itv3 = [i for i in m3.interventions if i.type == "step"][0]
    assert len(itv3.omega) == 3

    # `fue` normaliza "pulse" a "impulse", así que se busca por posición.
    m2 = _make_model(ts, lam=1.0, d=0, D=0, p=0, q=0, n_harmonics=0,
                     extra_itvs=[(60, "pulse")])
    itv2 = [i for i in m2.interventions
            if i.type in ("pulse", "impulse")][0]
    assert len(itv2.omega) == 1, "el par antiguo sigue valiendo"


# ───────────────── carril guiado ─────────────────

def _caso(nivel, semilla=11, d_mod=0):
    tmp = tempfile.mkdtemp()
    rng = np.random.default_rng(semilla)
    y = (np.cumsum(rng.standard_normal(200)) if d_mod
         else rng.standard_normal(200))
    for k, v in enumerate(nivel):
        y[60 + k] += v
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="EPI")
    m = fue.Model(ts, d=d_mod, mu=0.0, estimate_mu=False)
    f = os.path.join(tmp, "b.inp")
    _write_inp(ts, m, f)
    return f, os.path.join(tmp, "c.inp"), os.path.join(tmp, "guion.json")


def _texto(res):
    return "\n".join(getattr(c, "text", "") for c in res)


def test_el_guiado_elige_la_forma_de_EPISODIO_por_la_escalera():
    import art.mcp_server as srv
    f, out, g = _caso([9.0, 6.0])
    txt = _texto(srv.suggest_intervention_form(f, out, date="", form="auto",
                                               guion_path=g,
                                               guion_decision="prueba"))
    assert "Escalera de Ockham" in txt
    assert "3 escalones en el nivel" in txt
    assert "◀ elegido" in txt


def test_el_guiado_dice_POR_QUE_subio_y_no_por_AIC():
    import art.mcp_server as srv
    f, out, g = _caso([9.0, 6.0])
    txt = _texto(srv.suggest_intervention_form(f, out, date="", form="auto",
                                               guion_path=g,
                                               guion_decision="prueba"))
    assert "Se subió de peldaño por" in txt
    assert "Treadway" in txt


def test_el_guiado_pregunta_por_la_informacion_extramuestral():
    import art.mcp_server as srv
    f, out, g = _caso([9.0, 6.0])
    txt = _texto(srv.suggest_intervention_form(f, out, date="", form="auto",
                                               guion_path=g,
                                               guion_decision="prueba"))
    assert "suceso conocido" in txt


def test_el_nodo_del_guion_lleva_las_ALTERNATIVAS_con_su_razon():
    """Sin esto el guion dice qué se eligió y no qué se descartó ni por qué —
    que es justamente lo que hace falta para no volver a intentarlo."""
    import art.mcp_server as srv
    f, out, g = _caso([9.0, 6.0])
    srv.suggest_intervention_form(f, out, date="", form="auto", guion_path=g,
                                  guion_decision="prueba")
    nodos = [e for e in json.load(open(g))["entries"] if e.get("kind") == "node"]
    assert nodos, "tiene que quedar un nodo de decisión, no sólo el modelo"
    n = nodos[-1]
    assert n["node"]["nodo"] == "intervenciones"
    alt = n["node"]["alternativas"]
    assert "1a" in alt and "1b" in alt, "los dos peldaños descartados"
    assert "deja vecino" in alt, "y la razón del descarte"
    assert n["node"]["evidencia"], "con la evidencia que lo sostiene"
    assert n["rationale"], "y la razón, que es obligatoria"


def test_el_nodo_va_ANTES_del_modelo_en_el_guion():
    import art.mcp_server as srv
    f, out, g = _caso([9.0, 6.0])
    srv.suggest_intervention_form(f, out, date="", form="auto", guion_path=g,
                                  guion_decision="prueba")
    kinds = [e.get("kind") for e in json.load(open(g))["entries"]]
    assert kinds.index("node") < kinds.index("model")


def test_el_guiado_NO_sube_cuando_lo_simple_se_sostiene():
    """Un suceso de un solo período: la escalera se queda abajo."""
    import art.mcp_server as srv
    f, out, g = _caso([9.0])
    txt = _texto(srv.suggest_intervention_form(f, out, date="", form="auto",
                                               guion_path=g,
                                               guion_decision="prueba"))
    assert "No hubo razón para subir" in txt
    assert "problema resuelto" in txt
    assert "3 escalones" not in txt


def test_una_forma_explicita_no_dispara_la_escalera():
    """`form="pulse"` es una orden del analista, no una sugerencia."""
    import art.mcp_server as srv
    f, out, g = _caso([9.0, 6.0])
    txt = _texto(srv.suggest_intervention_form(f, out, date="", form="pulse",
                                               guion_path=g,
                                               guion_decision="prueba"))
    assert "Escalera de Ockham" not in txt
    assert "PULSE" in txt
