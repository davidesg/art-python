"""El convenio de signo de la FLT, cableado en el punto de uso.

fue guarda los operadores con el convenio de Box-Jenkins, el mismo para TODOS
—AR, MA, δ y ω—: los coeficientes de retardo entran **restando**.

    ω(B) = ω₀ − ω₁B − ω₂B² − ⋯ − ω_sB^s

La convención es consistente y no se toca. El problema no es la convención: es
que obliga a una resta mental cada vez que se lee o se escribe un ω, y esa resta
se falla. Está escrita en tres docstrings y se falló igual dos veces seguidas en
la sesión de la réplica; el `.inp` necesitó que un −0.7236 entrara como +0.7236.

El remedio no es escribirla una cuarta vez: es **calcularla**. Donde aparece un
ω aparece al lado el CAMINO DEL NIVEL, que es lo que el analista quiere decir.
Nadie tiene que hacer la resta, y un signo cambiado se ve antes de estimar nada.
"""
import os

import pytest

os.environ.setdefault("ART_NO_VIEWER", "1")

from art.ltf import operador_en_palabras


def _txt(res):
    return "\n".join(getattr(c, "text", "") for c in res)


# ───────────── el traductor ─────────────

def test_el_camino_del_nivel_es_la_respuesta_al_escalon():
    """ω = (0.7968, 0.3447): el nivel sube 0.797 y se queda en 0.452."""
    t = operador_en_palabras([0.7968, 0.3447])
    assert "+0.797, +0.452" in t
    assert "+0.4521" in t                       # la ganancia


def test_el_operador_se_escribe_con_los_signos_del_convenio():
    t = operador_en_palabras([0.7968, 0.3447])
    assert "ω(B) = +0.7968 − 0.3447·B" in t


def test_un_omega_negativo_se_escribe_sumando():
    """Porque el convenio ya lleva el menos: −(−0.3447)B = +0.3447B."""
    t = operador_en_palabras([0.7968, -0.3447])
    assert "+ 0.3447·B" in t


def test_avisa_de_que_la_suma_no_es_la_ganancia():
    """El error concreto que se comete: sumar los coeficientes."""
    t = operador_en_palabras([0.5700, 0.7236])
    assert "no** es la ganancia" in t
    assert "+1.2936" in t                       # la suma
    assert "-0.1536" in t                       # la ganancia de verdad


def test_la_trampa_de_la_replica():
    """ω = (0.5700, +0.7236): coeficientes que uno «sumaría» a +1.29 y una
    ganancia de −0.15. Es el caso real que costó dos errores."""
    t = operador_en_palabras([0.5700, 0.7236])
    assert "+0.570, -0.154" in t


def test_ganancia_nula_se_lee_como_transitorio():
    t = operador_en_palabras([3.0, 3.0])
    assert "TRANSITORIO" in t
    assert "+0.0000" in t


def test_con_un_solo_omega_no_hay_nota_de_suma():
    """Con un ω no hay resta que fallar."""
    t = operador_en_palabras([2.0])
    assert "Ojo con la suma" not in t
    assert "+2.000" in t


def test_el_denominador_entra_en_la_ganancia():
    """ν(1) = ω(1)/δ(1), y δ tiene el mismo convenio."""
    t = operador_en_palabras([1.0], [0.5])
    assert "+2.0000" in t                       # 1 / (1 − 0.5)


# ───────────── cableado: la ENTRADA ─────────────

def test_intervention_plot_devuelve_el_camino_del_nivel():
    """Donde el analista ESCRIBE los ω. Si el camino no es el que tenía en la
    cabeza, el signo estaba mal — y lo ve antes de estimar nada."""
    import art.mcp_server as srv
    fn = getattr(srv.intervention_plot, "fn", srv.intervention_plot)
    t = _txt(fn(omega=[0.5700, 0.7236]))
    assert "camino del NIVEL" in t
    assert "+0.570, -0.154" in t


def test_intervention_plot_con_un_omega_no_añade_ruido():
    import art.mcp_server as srv
    fn = getattr(srv.intervention_plot, "fn", srv.intervention_plot)
    assert "camino del NIVEL" not in _txt(fn(omega=[1.0]))


def test_el_docstring_avisa_y_dice_que_no_hace_falta_la_resta():
    import inspect

    import art.mcp_server as srv
    d = inspect.getdoc(getattr(srv.intervention_plot, "fn",
                               srv.intervention_plot)) or ""
    assert "restando" in d
    assert "No hace falta que hagas la resta" in d


# ───────────── cableado: la SALIDA ─────────────

def test_test_interventions_lee_los_omega_en_el_nivel(tmp_path):
    import numpy as np
    fue = pytest.importorskip("fue")
    import art.mcp_server as srv
    from art.pipeline import _RESCALE_FACTOR, _write_inp

    rng = np.random.default_rng(9)
    y = np.cumsum(rng.standard_normal(100) * 0.3) + 100.0
    y[50:] += 5.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="C")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
    base = str(tmp_path / "b.inp")
    _write_inp(ts, m, base)

    sif = getattr(srv.suggest_intervention_form, "fn",
                  srv.suggest_intervention_form)
    out = str(tmp_path / "c.inp")
    sif(base, out, date="Q3/2012", form="step", n_omega=2)

    ti = getattr(srv.test_interventions, "fn", srv.test_interventions)
    t = _txt(ti(out))
    assert "Los ω, leídos en el nivel" in t
    assert "camino del NIVEL" in t


def test_suggest_intervention_form_lo_dice_al_construir(tmp_path):
    """Es la primera vez que una FLT de varios ω aparece en la sesión."""
    import numpy as np
    fue = pytest.importorskip("fue")
    import art.mcp_server as srv
    from art.pipeline import _RESCALE_FACTOR, _write_inp

    rng = np.random.default_rng(9)
    y = np.cumsum(rng.standard_normal(100) * 0.3) + 100.0
    y[50:] += 5.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="C")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
    base = str(tmp_path / "b.inp")
    _write_inp(ts, m, base)
    sif = getattr(srv.suggest_intervention_form, "fn",
                  srv.suggest_intervention_form)
    t = _txt(sif(base, str(tmp_path / "c.inp"), date="Q3/2012", form="step",
                 n_omega=2))
    assert "camino del NIVEL" in t
