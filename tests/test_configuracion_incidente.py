"""Qué configuraciones del incidente admite el dato — y cuándo NO elegir.

La prueba que importa es que la herramienta **se niegue a elegir** cuando hay
varias configuraciones empatadas. Publicar una y su error típico cuando hay
tres indistinguibles fabrica una precisión que no existe, y la que el AIC saca
tiende a ser la de ventana corta: la lectura equivocada con la etiqueta más
convincente.
"""
import numpy as np
import pytest

from art.configuracion import (arranques_candidatos, evalua_configuraciones,
                               describe_configuraciones, InfoExtramuestral,
                               Candidato, ConjuntoCandidatos, UMBRAL_ACTIVO)

fue = pytest.importorskip("fue")


# ─────────────── el conjunto candidato, acotado por el mecanismo ───────────────

def test_anda_hacia_atras_mientras_el_residuo_siga_ACTIVO():
    """1σ es de EXTENSIÓN, no de detección: dice hasta dónde llega hacia atrás
    un suceso ya detectado por sus extremos."""
    z = np.array([0.1, 0.2, 0.3, 1.27, 1.35, -2.91, -2.82, 0.06, 0.1])
    #             0    1    2     3     4      5      6     7    8
    c = arranques_candidatos(z, [5, 6], d=1, umbral_activo=1.0)
    assert [a for a, _ in c] == [3, 4, 5], "para en el índice 2 (|z|=0.3 < 1σ)"


def test_un_candidato_por_arranque_no_una_rejilla():
    """Fijado el arranque, la longitud queda determinada por el último extremo.
    Es lo que impide sobre-elaborar."""
    z = np.array([0.1, 1.27, 1.35, -2.91, -2.82, 0.06])
    c = arranques_candidatos(z, [3, 4], d=1, umbral_activo=1.0)
    assert len(c) == len({a for a, _ in c}), "un candidato por arranque"
    for a, n in c:
        assert n == (4 - a + 1) - 1 + 1


def test_sin_vecinos_activos_solo_hay_un_candidato():
    z = np.array([0.1, 0.2, -3.5, 0.1, 0.2])
    assert arranques_candidatos(z, [2], d=0, umbral_activo=1.0) == [(2, 2)]


def test_el_tope_limita_la_extension():
    z = np.concatenate([np.full(20, 1.5), [-3.0]])
    c = arranques_candidatos(z, [20], d=0, umbral_activo=1.0, tope_atras=3)
    assert len(c) == 4, "el primer extremo más tres hacia atrás"


def test_sin_extremos_no_hay_candidatos():
    assert arranques_candidatos(np.zeros(10), [], d=0) == []


# ─────────────── la negativa a elegir ───────────────

def _conj(*specs, dominio="generic", info=None):
    """specs: (etiqueta, aic, omega_1, se, wald_p, arranque)."""
    cs = []
    for et, aic, w1, se, p, arr in specs:
        c = Candidato(arranque_resid=arr, n_escalones=2, etiqueta=et,
                      model=object(), aic=aic, omega_1=w1, se_omega_1=se,
                      wald_p=p)
        cs.append(c)
    return ConjuntoCandidatos(candidatos=cs, dominio=dominio,
                              info=info or InfoExtramuestral())


def test_no_identifica_cuando_hay_varias_en_la_banda():
    c = _conj(("A", -147.2, -0.27, 0.27, 0.31, 18),
              ("B", -146.8, -0.42, 0.22, 0.05, 19),
              ("C", -146.1, -0.58, 0.14, 0.00, 20))
    assert not c.identificado
    assert len(c.empatados) == 3
    assert c.rango_ganancia == (-0.58, -0.27)


def test_identifica_cuando_solo_una_cae_en_la_banda():
    c = _conj(("A", -147.2, -0.27, 0.27, 0.31, 18),
              ("B", -120.0, -0.42, 0.22, 0.05, 19))
    assert c.identificado


def test_detecta_que_las_empatadas_discrepan_en_la_lectura():
    c = _conj(("A", -147.2, -0.27, 0.27, 0.31, 18),
              ("C", -146.1, -0.58, 0.14, 0.001, 20))
    assert c.discrepan_en_la_lectura


def test_avisa_de_la_trampa_de_la_ventana_corta():
    """La de arranque más tardío con el IC más estrecho y única que excluye el
    cero: su lectura «permanente» es sospechosa de artefacto del arranque."""
    c = _conj(("A", -147.2, -0.27, 0.27, 0.31, 18),
              ("B", -146.8, -0.42, 0.22, 0.05, 19),
              ("C", -146.1, -0.58, 0.14, 0.001, 20))
    assert c.el_mas_estrecho_es_el_mas_corto
    assert "más sospechosa" in describe_configuraciones(c).summary


def test_la_recomendacion_dice_QUE_NO_elijas_por_AIC():
    c = _conj(("A", -147.2, -0.27, 0.27, 0.31, 18),
              ("C", -146.1, -0.58, 0.14, 0.001, 20))
    assert "No elijas por AIC" in describe_configuraciones(c).recommendation


# ─────────────── dominio ───────────────

def test_el_dominio_marca_implausibilidad_pero_no_elimina():
    c = _conj(("A", -147.2, -0.27, 0.27, 0.31, 18),
              ("C", -146.1, -0.58, 0.14, 0.001, 20), dominio="price_index")
    impl = c.implausible_por_dominio
    assert [x.etiqueta for x in impl] == ["C"], "sólo la permanente y negativa"
    assert len(c.empatados) == 2, "sigue en el conjunto: no se elimina"
    assert "no decide" in describe_configuraciones(c).summary


def test_un_dominio_sin_regla_no_marca_nada():
    c = _conj(("C", -146.1, -0.58, 0.14, 0.001, 20), dominio="generic")
    assert c.implausible_por_dominio == []


# ─────────────── información extramuestral ───────────────

def test_naturaleza_sin_fuente_se_rechaza():
    """No se puede afirmar que un suceso fue permanente sin decir por qué."""
    with pytest.raises(ValueError, match="por qué se sabe"):
        InfoExtramuestral(naturaleza="permanente")


def test_naturaleza_desconocida_se_rechaza():
    with pytest.raises(ValueError, match="permanente"):
        InfoExtramuestral(naturaleza="quizá", fuente="x")


def test_la_fecha_declarada_fija_la_configuracion():
    info = InfoExtramuestral(desde="Q3/2008", fuente="registro", aportada_por="analista")
    c = _conj(("Q3/2008×4", -147.2, -0.27, 0.27, 0.31, 18),
              ("Q1/2009×2", -146.1, -0.58, 0.14, 0.001, 20), info=info)
    assert c.fijado_por_lo_extramuestral.etiqueta == "Q3/2008×4"
    d = describe_configuraciones(c)
    assert "fija la configuración" in d.summary
    assert "Q3/2008×4" in d.recommendation


def test_avisa_si_la_fecha_declarada_no_es_ningun_candidato():
    info = InfoExtramuestral(desde="Q1/1999", fuente="registro")
    c = _conj(("Q3/2008×4", -147.2, -0.27, 0.27, 0.31, 18), info=info)
    assert c.fijado_por_lo_extramuestral is None
    assert "no coincide con ningún arranque" in describe_configuraciones(c).summary


def test_la_explicacion_tiene_que_explicar_la_FORMA():
    """Declarar «permanente» cuando la ganancia dice transitorio no vale."""
    info = InfoExtramuestral(desde="Q3/2008", naturaleza="permanente",
                             fuente="bajada de impuestos")
    c = _conj(("Q3/2008×4", -147.2, -0.27, 0.27, 0.31, 18), info=info)
    assert c.concuerda_con_lo_extramuestral is False
    assert "no concuerda" in describe_configuraciones(c).summary


def test_cuando_concuerdan_lo_dice():
    info = InfoExtramuestral(desde="Q3/2008", naturaleza="transitorio",
                             fuente="pico de materias primas")
    c = _conj(("Q3/2008×4", -147.2, -0.27, 0.27, 0.31, 18), info=info)
    assert c.concuerda_con_lo_extramuestral is True
    assert "concuerda" in describe_configuraciones(c).summary


def test_queda_constancia_de_QUIEN_la_aporto():
    """La herramienta no puede impedir que un LLM invente, pero sí que invente
    en silencio."""
    info = InfoExtramuestral(desde="Q3/2008", fuente="crisis de 2008",
                             aportada_por="LLM")
    c = _conj(("Q3/2008×4", -147.2, -0.27, 0.27, 0.31, 18), info=info)
    d = describe_configuraciones(c)
    assert "LLM" in d.summary
    assert d.data["info"]["aportada_por"] == "LLM"


def test_sin_informacion_la_pide_y_dice_que_no_la_supone():
    c = _conj(("A", -147.2, -0.27, 0.27, 0.31, 18),
              ("C", -146.1, -0.58, 0.14, 0.001, 20))
    d = describe_configuraciones(c)
    assert "No aportada" in d.summary
    assert "no debe suponerlo" in d.summary


# ─────────────── de punta a punta ───────────────

def test_sobre_datos_sinteticos_con_la_subida_por_debajo_del_umbral():
    """El caso de P5: el suceso empieza con movimientos que no son extremos."""
    rng = np.random.default_rng(4)
    y = np.cumsum(rng.standard_normal(120)) * 0.3
    y[60] += 1.2; y[61] += 1.3          # subida, no extrema en ∇
    y[62] -= 2.9; y[63] -= 2.8          # bajada, sí extrema
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2004, 1), name="S")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False); m.fit()
    r = np.asarray(m._result.residuals, float); z = (r - r.mean())/r.std(ddof=0)
    ext = [i for i in range(len(z)) if abs(z[i]) > 2.5]
    if not ext:
        pytest.skip("el sorteo no produjo extremos")
    cands = arranques_candidatos(z, ext, d=1)
    assert len(cands) >= 1
    conj = evalua_configuraciones(m, cands, d=1)
    assert conj.vivos
    d = describe_configuraciones(conj)
    assert "configuración" in d.summary.lower()


def test_la_herramienta_mcp_esta_registrada():
    import art.mcp_server as srv
    assert hasattr(srv, "incident_configurations")
