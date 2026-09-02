"""F3 — la escalera de Ockham.

La prueba que importa no es que la escalera encuentre el episodio: es que **NO
suba cuando lo simple se sostiene**. Una escalera que se quedase con el mejor
AIC subiría siempre —el modelo más sofisticado casi siempre ajusta mejor porque
tiene más parámetros— y eso es exactamente lo contrario de la navaja.
"""
import numpy as np
import pytest

fue = pytest.importorskip("fue")
from art.episodes import agrupa_episodios
from art.escalera import escalera_de_ockham, describe_escalera

T = 60
N = 200


def _base(nivel, semilla=11, permanente=False):
    """Modelo AJUSTADO sin la intervención, y el episodio que sale de él.

    El caso PERMANENTE se construye con `d=1` y no por capricho: con `d=0` un
    escalón sostenido **no aparece como atípico**. Sube la media y la varianza
    de los residuos y ningún |z| pasa de 3 — el escaneo de anómalos busca
    espigas, no cambios de nivel. En ∇, en cambio, un escalón de nivel es UN
    impulso, que es justo el diccionario de §2.1 del diseño; y así es como se ve
    en la práctica, porque estas series se trabajan diferenciadas.
    """
    rng = np.random.default_rng(semilla)
    if permanente:
        y = np.cumsum(rng.standard_normal(N))
        y[T:] += nivel[0]
        d = 1
    else:
        y = rng.standard_normal(N)
        for k, v in enumerate(nivel):
            y[T + k] += v
        d = 0
    ts = fue.TimeSeries(y.tolist(), freq=1, start=(1, 1), name="sint")
    m = fue.Model(ts, d=d, mu=0.0, estimate_mu=False)
    m.fit()
    r = np.asarray(m._result.residuals, dtype=float)
    z = (r - r.mean()) / r.std(ddof=0)
    ext = [(i + 1, float(z[i])) for i in range(len(z)) if abs(z[i]) > 3]
    eps = agrupa_episodios(ext, ventana=2, d=d)
    return m, max(eps, key=lambda e: e.z_max)


# ────────── LA prueba: no subir sin razón ──────────

def test_un_suceso_de_un_periodo_NO_hace_subir_la_escalera():
    """Impulso de nivel de un solo período: el peldaño 1 se sostiene.

    Absorbe su fecha, no deja vecino y el modelo es adecuado. Subir aquí sería
    añadir parámetros a un problema resuelto.
    """
    m, ep = _base([9.0])
    esc = escalera_de_ockham(m, ep)
    assert ep.duracion_nivel == 1
    assert esc.razones_para_subir == [], "no hay nada que justifique subir"
    assert esc.recomendado in ("1a", "1b")
    assert esc.por_nivel(esc.recomendado).se_sostiene


def test_y_el_texto_lo_dice_explicitamente():
    m, ep = _base([9.0])
    txt = describe_escalera(escalera_de_ockham(m, ep)).summary
    assert "No hay razón para subir" in txt
    assert "problema resuelto" in txt


def test_el_peldano_2_gana_en_AIC_y_aun_asi_no_se_recomienda():
    """El corazón de la navaja, medido.

    Con más parámetros el peldaño 2 ajusta mejor casi siempre. Si el 1 se
    sostiene, la escalera se queda en el 1 DE TODOS MODOS.
    """
    m, ep = _base([9.0])
    esc = escalera_de_ockham(m, ep)
    p2 = esc.por_nivel("2")
    mejor = min((p for p in esc.peldanos if p.estimado), key=lambda p: p.aic)
    if p2.estimado and p2.aic < esc.por_nivel(esc.recomendado).aic:
        assert esc.recomendado != "2", (
            "el peldaño 2 ajusta mejor y aun así no debe recomendarse: "
            "no hay razón para subir")


# ────────── y sí subir cuando la hay ──────────

def test_un_episodio_de_dos_hace_subir_por_TREADWAY():
    m, ep = _base([9.0, 6.0])
    esc = escalera_de_ockham(m, ep)
    assert any("Treadway" in r for r in esc.razones_para_subir)
    assert esc.recomendado == "2"
    assert esc.por_nivel("2").se_sostiene
    assert not esc.por_nivel("1b").se_sostiene


def test_la_duracion_del_episodio_es_razon_por_si_sola():
    m, ep = _base([9.0, 6.0])
    esc = escalera_de_ockham(m, ep)
    assert any("dura 2 períodos" in r for r in esc.razones_para_subir)


def test_el_contraste_de_ganancia_lee_TRANSITORIO_en_el_peldano_2():
    """El DGP son dos impulsos de nivel: ganancia nula."""
    m, ep = _base([9.0, 6.0])
    p2 = escalera_de_ockham(m, ep).por_nivel("2")
    assert p2.transitorio is True
    assert abs(p2.omega_1) < 1.0


def test_un_escalon_permanente_se_lee_como_permanente():
    """1a se sostiene y 1b —el impulso— se descarta por vecino e inadecuación.

    Y ω(1) del peldaño 1a recupera la magnitud real del escalón, lo que
    confirma que la intervención se aplica EN EL NIVEL aunque el modelo lleve
    d=1: el lenguaje homogeneizado del nodo.
    """
    m, ep = _base([9.0], permanente=True)
    esc = escalera_de_ockham(m, ep)
    p1a, p1b = esc.por_nivel("1a"), esc.por_nivel("1b")
    assert p1a.se_sostiene, "el escalón permanente es la lectura que aguanta"
    assert not p1b.se_sostiene, "el impulso deja vecino"
    assert esc.recomendado == "1a"
    assert esc.razones_para_subir == []
    assert p1a.omega_1 == pytest.approx(9.0, abs=1.5)


def test_el_peldano_2_puede_sostenerse_y_aun_asi_no_se_sube():
    """Sobre un escalón permanente el peldaño 2 TAMBIÉN es adecuado y sin
    vecino —contiene al 1a como caso particular— y aun así no se recomienda,
    porque no hay razón. Es la navaja funcionando cuando más fácil sería
    saltársela."""
    m, ep = _base([9.0], permanente=True)
    esc = escalera_de_ockham(m, ep)
    assert esc.por_nivel("2").se_sostiene
    assert esc.recomendado == "1a"


def test_y_el_peldano_2_lee_PERMANENTE_el_escalon():
    m, ep = _base([9.0], permanente=True)
    p2 = escalera_de_ockham(m, ep).por_nivel("2")
    assert p2.transitorio is False, "la ganancia NO es nula"


# ────────── la lectura de dominio ──────────

def test_una_caida_permanente_en_un_indice_de_precios_pide_respaldo():
    m, ep = _base([-9.0], permanente=True)
    esc = escalera_de_ockham(m, ep, dominio="price_index")
    assert any("Dominio" in r for r in esc.razones_para_subir)
    assert any("poco usual" in r for r in esc.razones_para_subir)


def test_la_misma_caida_en_una_serie_generica_no_levanta_nada():
    m, ep = _base([-9.0], permanente=True)
    esc = escalera_de_ockham(m, ep, dominio="generic")
    assert not any("Dominio" in r for r in esc.razones_para_subir)


# ────────── lo que la presentación DEBE decir ──────────

def test_el_texto_avisa_de_que_el_AIC_no_arbitra():
    m, ep = _base([9.0, 6.0])
    txt = describe_escalera(escalera_de_ockham(m, ep)).summary
    assert "El AIC no arbitra" in txt
    assert "más parámetros" in txt


def test_el_texto_pregunta_por_la_informacion_extramuestral():
    m, ep = _base([9.0, 6.0])
    d = describe_escalera(escalera_de_ockham(m, ep))
    assert "suceso conocido" in d.summary
    assert "explicar la FORMA" in d.summary
    assert "la simple gana aunque ajuste peor" in d.recommendation


def test_lo_simple_se_presenta_ANTES_que_lo_sofisticado():
    """El orden de la presentación no es cosmético: una tabla ordenada por AIC
    invita al error que la navaja prohíbe."""
    m, ep = _base([9.0, 6.0])
    txt = describe_escalera(escalera_de_ockham(m, ep)).summary
    assert txt.index("Peldaño 1") < txt.index("¿Se sube?") < txt.index("Peldaño 2")


def test_la_figura_y_los_datos_salen():
    m, ep = _base([9.0, 6.0])
    d = describe_escalera(escalera_de_ockham(m, ep))
    assert d.figure_b64 and len(d.figure_b64) > 1000
    assert len(d.data["peldanos"]) == 3
    assert d.data["recomendado"] == "2"


def test_la_herramienta_mcp_esta_registrada():
    import art.mcp_server as srv
    assert hasattr(srv, "intervention_ladder")
