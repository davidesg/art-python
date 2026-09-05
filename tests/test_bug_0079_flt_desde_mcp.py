"""BUG-0079 — la FLT que el diagnóstico identifica no se podía construir.

`incident_configurations` identifica el incidente y lo devuelve nombrado como
función de transferencia —«N escalones consecutivos en el nivel a partir de tal
fecha»— y no había ninguna herramienta que la construyera:
`suggest_intervention_form` sólo aceptaba `form ∈ {pulse, step, ramp, auto}`,
ninguna con orden.

La capa de abajo estaba entera —`_make_model` acepta `(at, form, n_omega)`,
`_write_inp` escribe el orden, `fue` lo estima— así que era **cableado que
faltaba, no capacidad**. Y con la cadena cortada, el contraste de ganancia nula
de BUG-0071/0072 era inalcanzable desde el carril guiado: sólo se emite con más
de un ω libre.
"""
import os
import tempfile

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")
import art.mcp_server as srv
from art.pipeline import _load_ts_model, _write_inp


@pytest.fixture(scope="module")
def base():
    """Un modelo estimado con un episodio de tres períodos en el nivel."""
    d = tempfile.mkdtemp()
    rng = np.random.default_rng(11)
    y = np.cumsum(rng.standard_normal(120)) + 100
    y[60] += 4.0
    y[61] += 6.0
    y[62] += 3.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="EP")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=100.0)
    f = os.path.join(d, "base.inp")
    _write_inp(ts, m, f)
    return f, d


# ───────────────── la puerta que faltaba ─────────────────

def test_se_puede_construir_una_FLT_de_varios_omega(base):
    f, d = base
    out = os.path.join(d, "flt.inp")
    srv.suggest_intervention_form(f, out, date="Q1/2015", form="step",
                                  n_omega=4, guion_path=os.path.join(d, "g.json"),
                                  guion_decision="prueba")
    _, m = _load_ts_model(out)
    itv = [i for i in m.interventions
           if i.type in ("step", "impulse", "pulse")][0]
    assert len(itv.omega) == 4
    assert sum(1 for x in (itv.omega_free or []) if x) == 4


def test_n_omega_explicito_manda_sobre_la_escalera(base):
    """Es una declaración del analista, no una sugerencia."""
    f, d = base
    out = os.path.join(d, "flt_auto.inp")
    srv.suggest_intervention_form(f, out, date="Q1/2015", form="step",
                                  n_omega=3, guion_path=os.path.join(d, "g2.json"),
                                  guion_decision="prueba")
    _, m = _load_ts_model(out)
    itv = [i for i in m.interventions if i.type == "step"][0]
    assert len(itv.omega) == 3


def test_sin_n_omega_el_comportamiento_no_cambia(base):
    """Compatibilidad: una forma explícita sin `n_omega` sigue dando un solo ω."""
    f, d = base
    out = os.path.join(d, "uno.inp")
    srv.suggest_intervention_form(f, out, date="Q1/2015", form="pulse",
                                  guion_path=os.path.join(d, "g3.json"),
                                  guion_decision="prueba")
    _, m = _load_ts_model(out)
    itv = [i for i in m.interventions
           if i.type in ("pulse", "impulse")][0]
    assert len(itv.omega) == 1


# ───────── el contraste que la cadena cortada hacía inalcanzable ─────────

def test_el_Wald_de_ganancia_nula_ya_se_emite_desde_el_carril_guiado(base):
    """Sólo se emite con k>1 ω libres. Sin poder construirlos, el contraste que
    separa transitorio de permanente no existía en el carril guiado."""
    f, d = base
    out = os.path.join(d, "gan.inp")
    srv.suggest_intervention_form(f, out, date="Q1/2015", form="step",
                                  n_omega=4, guion_path=os.path.join(d, "g4.json"),
                                  guion_decision="prueba")
    txt = "\n".join(getattr(c, "text", "")
                    for c in srv.test_interventions(out))
    assert "ω(1)" in txt
    assert "Wald" in txt
    assert "TRANSITORIO" in txt or "permanente" in txt


def test_la_forma_construida_llega_a_la_ecuacion(base):
    f, d = base
    out = os.path.join(d, "eq.inp")
    srv.suggest_intervention_form(f, out, date="Q1/2015", form="step",
                                  n_omega=3, guion_path=os.path.join(d, "g5.json"),
                                  guion_decision="prueba")
    txt = "\n".join(getattr(c, "text", "")
                    for c in srv.model_equation_display(out))
    assert "·B²" in txt, "el numerador de orden 2 tiene que verse en la ecuación"


# ───────── el árbitro entre los dos criterios de forma ─────────

def test_la_ruta_auto_toma_la_forma_del_MECANISMO_no_solo_de_los_extremos(base):
    """Arquitectura §4.2. `residual_episodes` agrupa sólo extremos y trunca los
    sucesos asimétricos; `incident_configurations` extiende por el mecanismo.
    Eran dos respuestas a la misma pregunta sin árbitro — sobre ITCER daban 3
    escalones desde Q4/2008 y 5 desde Q2/2008, con 6,15 puntos de AIC entre
    ellas."""
    from _fuente import fuente_de
    src = fuente_de(srv.suggest_intervention_form)
    assert "arranques_candidatos" in src
    assert "evalua_configuraciones" in src


def test_la_ruta_auto_avisa_cuando_el_dato_no_identifica(base):
    from _fuente import fuente_de
    src = fuente_de(srv.suggest_intervention_form)
    assert "no identifica la " in src and "configuración" in src
    assert "incident_configurations" in src


def test_el_repro_del_bug_ya_no_señala_a_esta_herramienta():
    """El repro comprueba las tres herramientas que crean o modifican
    intervenciones. `confirm_and_estimate` y `build_model` no crean ninguna
    desde la superficie —la primera las hereda del `.pre`, la segunda las decide
    dentro— así que la puerta que faltaba era ésta."""
    import inspect
    fn = getattr(srv.suggest_intervention_form, "fn", srv.suggest_intervention_form)
    assert "n_omega" in inspect.signature(fn).parameters
