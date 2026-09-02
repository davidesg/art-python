"""F0b — la hipótesis de forma superpuesta a lo observado, en el entorno.

Los tres números separan tres preguntas distintas, y las pruebas están
organizadas por esa separación porque es lo que da valor a la herramienta:

    escala   la AMPLITUD
    R²       la FORMA
    z_resto  lo que queda sin explicar

Y una prueba del límite: la superposición NO ve la ganancia a largo plazo. Esa
la dirime el contraste, y conviene que esté escrito como afirmación y no como
suposición.
"""
import numpy as np
import pytest

from art.ltf import superpone, describe_superposicion, respuesta_flt


# ω para un camino de nivel 9 → 6 → 0:
#   ω₀ = 9;  ω₀ − ω₁ = 6 ⇒ ω₁ = 3;  ω₀ − ω₁ − ω₂ = 0 ⇒ ω₂ = 6
W_CORRECTA = [9.0, 3.0, 6.0]
W_COLA     = [9.0, 3.0, 3.0]      # ω(1) = 3: deja cola permanente
W_ESCALON  = [1.0]
W_IMPULSO  = [1.0, 1.0]


@pytest.fixture
def residuos():
    """Ruido blanco con DOS impulsos de nivel (9 y 6) vistos en ∇.

    En primeras diferencias son tres: +9, 6−9 = −3, y −6.
    """
    r = np.random.default_rng(3).standard_normal(120)
    r[59] += 9.0
    r[60] += -3.0
    r[61] += -6.0
    return r


def test_la_hipotesis_correcta_encaja(residuos):
    sp = superpone(residuos, at=60, omega=W_CORRECTA, d=1, ventana=6)
    assert sp.la_forma_explica
    assert sp.r2 > 0.85
    assert abs(sp.z_resto) < 2.0


def test_la_escala_sale_uno_cuando_la_amplitud_ya_es_la_buena(residuos):
    """ω con las magnitudes reales ⇒ no hay que estirar nada."""
    sp = superpone(residuos, at=60, omega=W_CORRECTA, d=1, ventana=6)
    assert sp.escala == pytest.approx(1.0, abs=0.15)


def test_la_escala_recoge_la_magnitud_cuando_omega_es_unitaria(residuos):
    """Misma FORMA con ω normalizada: el R² no cambia y la escala sí."""
    unit = [v / 9.0 for v in W_CORRECTA]
    a = superpone(residuos, at=60, omega=W_CORRECTA, d=1, ventana=6)
    b = superpone(residuos, at=60, omega=unit, d=1, ventana=6)
    assert b.r2 == pytest.approx(a.r2, abs=1e-12), "la forma es la misma"
    assert b.escala == pytest.approx(9.0 * a.escala, rel=1e-9)


@pytest.mark.parametrize("omega,nombre", [
    (W_ESCALON, "un solo escalón"),
    (W_IMPULSO, "un impulso de nivel"),
])
def test_una_forma_equivocada_se_delata(residuos, omega, nombre):
    """R² bajo Y escala disparada: se está estirando una forma que no da."""
    sp = superpone(residuos, at=60, omega=omega, d=1, ventana=6)
    assert not sp.la_forma_explica, nombre
    assert sp.r2 < 0.70
    assert abs(sp.z_resto) > 3.0
    assert sp.escala > 5.0, "estira para compensar lo que la forma no recoge"


def test_la_forma_correcta_gana_a_las_equivocadas(residuos):
    r2 = lambda w: superpone(residuos, at=60, omega=w, d=1, ventana=6).r2
    assert r2(W_CORRECTA) > r2(W_IMPULSO) > r2(W_ESCALON)


# ────────── el límite, escrito como afirmación ──────────

def test_la_superposicion_NO_ve_la_ganancia_a_largo_plazo(residuos):
    """(9,3,6) y (9,3,3) se distinguen sólo en la cola permanente.

    El R² apenas se mueve: la diferencia está en la ganancia, que es una
    propiedad del comportamiento FUTURO y no de la forma local. Por eso el
    reparto es «el gráfico descarta lo incompatible, el contraste dirime el
    resto», y por eso esto es una prueba y no una nota al pie.
    """
    buena = superpone(residuos, at=60, omega=W_CORRECTA, d=1, ventana=6)
    cola  = superpone(residuos, at=60, omega=W_COLA,     d=1, ventana=6)
    assert abs(buena.r2 - cola.r2) < 0.06, "el gráfico casi no las separa"

    # y sin embargo son especificaciones distintas: una es transitoria y la otra no
    assert respuesta_flt(W_CORRECTA, K=8).transitorio
    assert not respuesta_flt(W_COLA, K=8).transitorio


# ────────── el entorno, que es el punto de la herramienta ──────────

def test_solo_dibuja_el_entorno_y_no_la_serie_entera(residuos):
    sp = superpone(residuos, at=60, omega=W_CORRECTA, d=1, ventana=6)
    assert len(sp.k) < 30, "un recorte, no las 120"
    assert sp.k[0] >= 60 - 6 - 1 and sp.k[-1] <= 60 + 6 + len(W_CORRECTA) + 1


def test_la_ventana_controla_el_recorte(residuos):
    corto = superpone(residuos, at=60, omega=W_CORRECTA, d=1, ventana=3)
    largo = superpone(residuos, at=60, omega=W_CORRECTA, d=1, ventana=12)
    assert len(corto.k) < len(largo.k)


def test_un_suceso_al_borde_no_se_sale(residuos):
    sp = superpone(residuos, at=2, omega=W_CORRECTA, d=1, ventana=10)
    assert sp.k[0] == 1
    assert len(sp.observado) == len(sp.simulado) == len(sp.k)


# ────────── guardas ──────────

def test_at_fuera_de_la_serie(residuos):
    with pytest.raises(ValueError, match="fuera de la serie"):
        superpone(residuos, at=500, omega=W_CORRECTA)


def test_entrada_desconocida(residuos):
    with pytest.raises(ValueError, match="escalon"):
        superpone(residuos, at=60, omega=W_CORRECTA, entrada="rampa")


def test_impulso_como_entrada_usa_la_irf(residuos):
    """Las dos entradas superponen cosas distintas — y con soportes distintos,
    así que la ventana recortada tampoco coincide. Se comparan escalares."""
    a = superpone(residuos, at=60, omega=W_CORRECTA, d=1, entrada="escalon")
    b = superpone(residuos, at=60, omega=W_CORRECTA, d=1, entrada="impulso")
    assert a.r2 != pytest.approx(b.r2, abs=1e-6)
    # la respuesta al ESCALÓN es el camino del nivel, y es la que encaja aquí
    assert a.r2 > b.r2


def test_cada_superposicion_es_internamente_coherente(residuos):
    """k, observado, simulado y resto siempre del mismo largo, sea cual sea la
    entrada — aunque entre llamadas el recorte cambie con el soporte."""
    for entrada in ("escalon", "impulso"):
        sp = superpone(residuos, at=60, omega=W_CORRECTA, d=1, entrada=entrada)
        n = len(sp.k)
        assert len(sp.observado) == len(sp.simulado) == len(sp.resto) == n
        assert np.allclose(sp.resto, sp.observado - sp.simulado)


# ────────── presentación y MCP ──────────

def test_describe_dice_cuando_la_forma_no_encaja(residuos):
    d = describe_superposicion(residuos, 60, W_ESCALON, d=1, ventana=6)
    assert "FORMA no encaja" in d.summary
    assert d.figure_b64 and len(d.figure_b64) > 1000
    assert d.data["la_forma_explica"] is False


def test_describe_dice_cuando_si(residuos):
    d = describe_superposicion(residuos, 60, W_CORRECTA, d=1, ventana=6)
    assert "cubre lo que hay" in d.summary
    assert d.data["escala"] == pytest.approx(1.0, abs=0.15)


def test_la_herramienta_mcp_esta_registrada():
    import art.mcp_server as srv
    assert hasattr(srv, "intervention_plot")
