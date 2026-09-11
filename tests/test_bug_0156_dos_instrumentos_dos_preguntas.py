"""BUG-0156 — la llamada 2 con escalera daba DOS recomendaciones sin jerarquía.

    escalera   recomienda `1a` — escalón en Q4/2008, UN parámetro
    Veredicto  recomienda `Q2/2008×3` — TRES parámetros, OTRA fecha

Dos recomendaciones incompatibles en la misma respuesta, sin decir cuál gobierna
ni por qué difieren. El analista tenía que arbitrar entre dos partes de la misma
salida — y sobre ITCER se quedó con la del veredicto, anotando que la escalera
«no concuerda».

Son DOS DEFECTOS, y el segundo hace imposible arreglar el primero hablando:

1. **La asimetría.** La escalera caminaba desde el primer extremo del episodio y
   las configuraciones exploran arranques HACIA ATRÁS por el mecanismo. Sus
   ganadoras estaban en fechas distintas: compararlas no era comparar. Y en el
   carril del instrumento era peor — el peldaño que se EVALUABA no era el que se
   CONSTRUÍA, porque el código ya tomaba la longitud del árbitro.
2. **La falta de jerarquía.** Que discrepen no es un error: es información. El
   MECANISMO acota la FORMA —qué arranque y cuántos escalones cabe que tenga el
   suceso— y la NAVAJA acota la SOFISTICACIÓN —cuánta de esa forma sostiene el
   dato—. Lo que faltaba era decirlo.
"""
import os
import tempfile

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art import policy
from art.configuracion import arranques_candidatos, evalua_configuraciones
from art.diagnosis import diagnose
from art.escalera import escalera_de_ockham
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar


def _caso(seed, a1, a2, T=60, n=120, tmp=None):
    """Serie con una caída en DOS tramos: el segundo decide si el mecanismo
    admite uno o dos escalones."""
    rng = np.random.default_rng(seed)
    y = 100.0 + np.cumsum(rng.standard_normal(n) * 0.5)
    y[T:] += a1
    y[T + 1:] += a2
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1995, 1), name="X")
    d = tmp or tempfile.mkdtemp()
    f = os.path.join(d, "X.inp")
    _write_inp(ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                             refactor=_RESCALE_FACTOR, ar=[[0.0]],
                             ar_free=[[True]]), f)
    _, m = estimar(f)
    return f, ts, m


def _fecha(obs_resid, d=1, freq=4, start=(1995, 1)):
    """La etiqueta de una observación de RESIDUOS, con su desfase."""
    o = obs_resid - 1 + d
    a = start[0] + (start[1] - 1 + o) // freq
    q = (start[1] - 1 + o) % freq + 1
    return f"Q{q}/{a}"


def _piezas(m, ts):
    dg = diagnose(m, z_threshold=3.0)
    eps = policy.decide_episodios(dg.extreme, d=1)
    assert eps, "el testigo dejó de valer: no hay episodio"
    ep = eps[0]
    r = np.asarray(m._result.residuals, dtype=float)
    z = (r - r.mean()) / (r.std(ddof=0) or 1.0)
    cands = arranques_candidatos(z, [o - 1 for o, _ in ep.extremos], d=1)
    conj = evalua_configuraciones(m, cands, d=1, dominio="generic", freq=4,
                                  start_year=1995, start_per=1)
    return ep, conj


# ── 1 · la asimetría ────────────────────────────────────────────────────────

def test_los_peldanos_parten_del_arranque_del_MECANISMO(tmp_path):
    """Sin alinear, los tres peldaños caen en el primer extremo del episodio y
    la configuración ganadora empieza antes."""
    _, ts, m = _caso(3, -5.0, -1.4, tmp=str(tmp_path))
    ep, conj = _piezas(m, ts)
    mj = conj.mejor
    assert mj is not None and mj.estimado
    assert mj.n_escalones > 1, "el testigo dejó de valer: el mecanismo da ×1"

    suelta = escalera_de_ockham(m, ep, dominio="generic")
    assert suelta.alineada_con_configuracion is False
    assert suelta.at_arranque == ep.at_0based(1)
    assert suelta.por_nivel("2").n_omega == ep.duracion_nivel + 1

    junta = escalera_de_ockham(m, ep, dominio="generic",
                               at=mj.arranque_resid - 1 + 1,
                               n_alto=mj.n_escalones, fecha_arranque=mj.fecha)
    assert junta.alineada_con_configuracion is True
    assert junta.at_arranque == mj.arranque_resid - 1 + 1
    assert junta.por_nivel("2").n_omega == mj.n_escalones, (
        "el peldaño alto no ES la configuración ganadora")


def test_el_MECANISMO_desplaza_el_arranque_y_la_escalera_lo_sigue(tmp_path):
    """El caso de ITCER, reproducido: un primer tramo PEQUEÑO —activo pero no
    extremo— seguido de uno grande. El detector de episodios agrupa extremos, así
    que empieza en el segundo; el mecanismo extiende hacia atrás y empieza en el
    primero. Sin alinear, los peldaños juzgan un suceso que empieza un período
    después que la configuración ganadora, y sus recomendaciones se publicaban
    juntas como si fueran rivales."""
    _, ts, m = _caso(3, -1.0, -5.0, tmp=str(tmp_path))
    ep, conj = _piezas(m, ts)
    mj = conj.mejor
    at_cfg, at_ep = mj.arranque_resid - 1 + 1, ep.at_0based(1)
    assert at_cfg != at_ep, "el testigo dejó de valer: no hay desplazamiento"

    suelta = escalera_de_ockham(m, ep, dominio="generic")
    assert suelta.at_arranque == at_ep

    junta = escalera_de_ockham(m, ep, dominio="generic", at=at_cfg,
                               n_alto=mj.n_escalones, fecha_arranque=mj.fecha)
    assert junta.at_arranque == at_cfg
    assert junta.desplazada_del_episodio is True

    from art.escalera import describe_escalera
    txt = describe_escalera(junta).summary
    assert "**no** del primer extremo" in txt
    assert mj.fecha in txt


def test_el_informe_de_la_escalera_dice_de_donde_parte(tmp_path):
    from art.escalera import describe_escalera
    _, ts, m = _caso(3, -5.0, -1.4, tmp=str(tmp_path))
    ep, conj = _piezas(m, ts)
    mj = conj.mejor
    junta = escalera_de_ockham(m, ep, dominio="generic",
                               at=mj.arranque_resid - 1 + 1,
                               n_alto=mj.n_escalones, fecha_arranque=mj.fecha)
    txt = describe_escalera(junta).summary
    assert mj.fecha in txt
    assert "MECANISMO" in txt
    # y dice la verdad sobre si difiere del primer extremo o no
    if junta.desplazada_del_episodio:
        assert "**no** del primer extremo" in txt
    else:
        assert "a la vez el primer extremo" in txt


def test_sin_alinear_el_informe_no_afirma_nada(tmp_path):
    """La nota sólo sale cuando hay algo que decir: en el carril donde la
    escalera va sola —sin configuraciones— no hay desalineación que avisar."""
    from art.escalera import describe_escalera
    _, ts, m = _caso(3, -5.0, -1.4, tmp=str(tmp_path))
    ep, _ = _piezas(m, ts)
    txt = describe_escalera(escalera_de_ockham(m, ep, dominio="generic")).summary
    assert "el arranque que el MECANISMO admite" not in txt


# ── 2 · la jerarquía, por la superficie ─────────────────────────────────────

def _llamada2(f, date):
    import art.mcp_server as srv
    fn = getattr(srv.guided_intervention, "fn", srv.guided_intervention)
    return "\n".join(getattr(x, "text", "")
                     for x in fn(inp_path=f, date=date, escalera=True))


def test_cuando_DISCREPAN_se_dice_y_se_da_el_criterio(tmp_path):
    """El testigo: el mecanismo admite `Q1/2010×2` y la navaja se queda en `1a`
    sin ninguna razón para subir. Es la forma exacta de ITCER."""
    f, ts, m = _caso(44, -5.0, -1.4, tmp=str(tmp_path))
    _, conj = _piezas(m, ts)
    assert conj.mejor.n_escalones == 2, "el testigo dejó de valer"
    txt = _llamada2(f, _fecha(_piezas(m, ts)[0].inicio))
    assert "no dicen lo mismo" in txt, "la discrepancia se sigue callando"
    # y el criterio, que es lo que convierte la discrepancia en información
    assert "acota la FORMA" in txt and "acota la\n  SOFISTICACIÓN" in txt \
        or ("acota la FORMA" in txt and "SOFISTICACIÓN" in txt)
    assert "No lo arbitra el AIC" in txt
    # los dos números, para que se vea en qué difieren
    assert conj.mejor.etiqueta in txt


def test_cuando_COINCIDEN_se_dice_tambien(tmp_path):
    """Decir sólo las discrepancias deja al lector sin saber si el silencio
    significa acuerdo o que nadie miró."""
    f, ts, m = _caso(3, -5.0, -1.4, tmp=str(tmp_path))
    ep, conj = _piezas(m, ts)
    txt = _llamada2(f, _fecha(ep.inicio))
    assert "coinciden" in txt
    assert "no dicen lo mismo" not in txt


def test_la_discrepancia_apunta_a_la_vuelta_diferida(tmp_path):
    """Cuando ninguna forma de una sola fecha resuelve el suceso, la salida no
    puede dejar al analista buscando una forma más rica: la lectura que falta
    puede ser la de BUG-0157 — dos intervenciones y su ganancia neta."""
    f, ts, m = _caso(44, -5.0, -1.4, tmp=str(tmp_path))
    ep, conj = _piezas(m, ts)
    txt = _llamada2(f, _fecha(ep.inicio))
    assert "vuelta\n  diferida" in txt or "vuelta diferida" in txt
    assert "ganancia NETA" in txt or "ganancia\n  NETA" in txt


def test_sin_escalera_no_hay_dos_recomendaciones_que_arbitrar(tmp_path):
    """La escalera sólo sale si se pide (BUG-0138), y sin ella no hay nada que
    jerarquizar: el veredicto es uno."""
    f, ts, m = _caso(44, -5.0, -1.4, tmp=str(tmp_path))
    import art.mcp_server as srv
    fn = getattr(srv.guided_intervention, "fn", srv.guided_intervention)
    txt = "\n".join(getattr(x, "text", "")
                    for x in fn(inp_path=f, date=_fecha(_piezas(m, ts)[0].inicio)))
    assert "no dicen lo mismo" not in txt and "coinciden" not in txt


# ── 3 · el carril del instrumento: el peldaño juzgado ES el construido ──────

def test_el_peldano_que_se_juzga_es_el_que_se_construye():
    """En `suggest_intervention_form(form="auto")` la escalera corría ANTES de
    calcular el árbitro, así que evaluaba L+1 escalones desde el primer extremo
    mientras el código construía `n_esc` desde `at_esc`. El comentario del
    árbitro ya decía que la longitud la fija el mecanismo; la escalera no se
    había enterado."""
    import pathlib
    src = pathlib.Path("src/art/mcp_server.py").read_text()
    i_arb = src.find("EL ÁRBITRO (arquitectura §4.2)")
    i_esc = src.find("esc = escalera_de_ockham(m_src, ep")
    assert i_arb > 0 and i_esc > 0
    assert i_arb < i_esc, (
        "la escalera vuelve a correr antes del árbitro: juzga un peldaño y se "
        "construye otro")
    assert "**_al_esc" in src, "la escalera del instrumento dejó de alinearse"
