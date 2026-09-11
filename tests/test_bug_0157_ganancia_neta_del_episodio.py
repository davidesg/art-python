"""BUG-0157 (segunda mitad) — la ganancia NETA de un episodio repartido.

`test_intervention` contrasta la ganancia de CADA intervención por separado.
Sobre un suceso con vuelta diferida eso rotula la caída «PERMANENTE» sin haber
mirado nunca el rebote: la caída es permanente **en su propio tramo**, y eso es
compatible con que el nivel vuelva después.

Es lo que pasó en ITCER. La caída de 2008 salió «PERMANENTE» con ω(1)=−21,16,
y el analista, calculando a mano sobre las dos intervenciones, obtuvo −13,8 con
t=−3,1: una recuperación PARCIAL, que es una tercera lectura que el catálogo no
sabía nombrar.

El contraste es una única restricción lineal sobre el vector completo de
parámetros —H₀: Σᵢ ωᵢ(1) = 0— así que sigue siendo un Wald χ²(1) exacto, con α
extendido sobre los bloques de las intervenciones elegidas.

EL TESTIGO LLEVA AR(1) A PROPÓSITO. Sin estructura ARMA el optimizador arranca
cerca y apenas itera, y la covarianza se queda en la semilla del BFGS: medido
sobre este mismo montaje, el SE de la neta saltaba entre 0,076 y 0,539 según los
datos, con el MISMO diseño y los mismos parámetros. Con el AR(1) el optimizador
da 14-16 iteraciones y el SE se queda en 0,55 en los tres escenarios, que es lo
que tiene que pasar. Es la regla del analista: *sin ARMA el optimizador puede
llevar la semilla; con ARMA es probable que las iteraciones necesarias den para
tener SE fiables.*
"""
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.diagnosis import covariance_is_degenerate
from art.interventions import GananciaNeta, net_gain
from art.interventions import test_intervention as _test_intervention

_T, _TV, _N, _PHI = 60, 66, 160, 0.55


def _modelo(caida, vuelta, dos_tramos=False, seed=5):
    """Serie con AR(1) en la diferencia, una caída en `_T` y una vuelta en `_TV`."""
    rng = np.random.default_rng(seed)
    a = rng.standard_normal(_N) * 0.5
    e = np.zeros(_N)
    for t in range(1, _N):
        e[t] = _PHI * e[t - 1] + a[t]
    y = 100.0 + np.cumsum(e)
    if dos_tramos:
        y[_T:] += caida * 0.7
        y[_T + 1:] += caida * 0.3
        om = [0.0, 0.0]
    else:
        y[_T:] += caida
        om = [0.0]
    y[_TV:] += vuelta
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1985, 1), name="EPI")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, ar=[[0.0]],
                  ar_free=[[True]],
                  interventions=[
                      fue.Intervention("step", at=_T, omega=om,
                                       omega_free=[True] * len(om)),
                      fue.Intervention("step", at=_TV, omega=[0.0],
                                       omega_free=[True])])
    m.fit()
    return m


@pytest.fixture(scope="module")
def parcial():
    return _modelo(-10.0, 6.0, dos_tramos=True)


# ── el defecto ──────────────────────────────────────────────────────────────

def test_la_caida_SOLA_dice_permanente_y_el_episodio_dice_parcial(parcial):
    """Los dos números conviven: la caída ES permanente en su tramo. Lo que no
    vale es leer eso como el veredicto del suceso."""
    sola = _test_intervention(parcial, 0)
    assert sola.wald_p < 0.05, "el testigo dejó de valer: la caída ya no sale permanente"
    assert sola.omega_1 < -8.0

    epi = net_gain(parcial, [0, 1])
    assert "PARCIAL" in epi.lectura
    assert epi.neta > sola.omega_1, "la neta no puede ser peor que la caída sola"
    assert -5.0 < epi.neta < -1.0, f"neta={epi.neta:+.4f}, se esperaba ≈ −3"


def test_la_fraccion_recuperada_es_la_que_nombra_la_lectura(parcial):
    epi = net_gain(parcial, [0, 1])
    assert 0.5 < epi.recuperado < 0.85
    assert f"{epi.recuperado*100:.0f} %" in epi.lectura


# ── las tres lecturas, y son tres ───────────────────────────────────────────

@pytest.mark.parametrize("vuelta,espera", [
    (10.0, "VUELVE"),          # devuelve todo  → transitorio
    (6.0,  "PARCIAL"),         # devuelve parte → la lectura que faltaba
    (0.0,  "NO vuelve"),       # no devuelve    → permanente
])
def test_las_tres_lecturas(vuelta, espera):
    epi = net_gain(_modelo(-10.0, vuelta), [0, 1])
    assert espera in epi.lectura, f"vuelta={vuelta:+.0f} → {epi.lectura}"


def test_la_neta_recupera_la_verdad_del_testigo():
    """Sin esto lo anterior sólo comprueba que el rótulo es consistente consigo
    mismo. La neta tiene que dar el desplazamiento que se metió."""
    for vuelta in (10.0, 6.0, 0.0):
        epi = net_gain(_modelo(-10.0, vuelta), [0, 1])
        assert abs(epi.neta - (-10.0 + vuelta)) < 1.0, (
            f"verdad={-10.0+vuelta:+.1f}, estimado={epi.neta:+.4f}")


def test_el_contraste_solo_rechaza_cuando_debe():
    assert net_gain(_modelo(-10.0, 10.0), [0, 1]).wald_p > 0.05
    assert net_gain(_modelo(-10.0, 6.0),  [0, 1]).wald_p < 0.05
    assert net_gain(_modelo(-10.0, 0.0),  [0, 1]).wald_p < 0.05


# ── que el número publicado sea fiable ──────────────────────────────────────

def test_el_SE_no_depende_de_los_datos_con_el_mismo_diseno():
    """La regla del analista, hecha prueba. Mismo diseño y mismos parámetros: el
    SE de la neta tiene que ser prácticamente el mismo en los tres escenarios.
    SIN el AR(1) saltaba entre 0,076 y 0,539 — la covarianza era la semilla del
    BFGS, no el hessiano (BUG-0027)."""
    ses = [net_gain(_modelo(-10.0, v), [0, 1]).se_neta for v in (10.0, 6.0, 0.0)]
    assert all(s is not None for s in ses)
    assert max(ses) / min(ses) < 1.15, f"SE inestables: {ses}"


def test_se_niega_sobre_una_covarianza_que_no_existe():
    """Un contraste sobre la semilla del BFGS no es un contraste. Es la misma
    puerta que `test_intervention` (BUG-0027)."""
    m = _modelo(-10.0, 6.0)
    assert not covariance_is_degenerate(m._result), "el testigo ya está degenerado"

    class _R:
        def __init__(self, r):
            self.__dict__.update({k: getattr(r, k) for k in
                                  ("params", "npar", "residuals")})
            self.niter = 0
            self.cov_matrix = np.eye(len(r.params)) * 1e-3
    m._result = _R(m._result)
    with pytest.raises(ValueError, match="BUG-0027"):
        net_gain(m, [0, 1])


# ── la lectura depende del TIPO de entrada ──────────────────────────────────

def test_un_impulso_no_aporta_al_nivel_y_pesa_cero():
    """BUG-0076: la entrada impulso no persiste, así que su efecto permanente es
    cero POR CONSTRUCCIÓN. Sumarlo con peso 1 contrastaría otra cosa."""
    m = _modelo(-10.0, 6.0)
    m.interventions[1].type = "impulse"
    m.fit()
    epi = net_gain(m, [0, 1])
    assert epi.entradas == ["escalon", "impulso"]
    assert abs(epi.neta - epi.omega_1[0]) < 1e-9, (
        "el impulso entró en la suma: su aportación al NIVEL es 0")


# ── contorno ────────────────────────────────────────────────────────────────

def test_con_una_sola_intervencion_manda_a_la_herramienta_que_toca(parcial):
    with pytest.raises(ValueError, match="AL MENOS DOS"):
        net_gain(parcial, [0])


def test_no_se_suma_una_intervencion_dos_veces(parcial):
    with pytest.raises(ValueError, match="repetidas"):
        net_gain(parcial, [0, 0])


def test_indice_fuera_de_rango(parcial):
    with pytest.raises(IndexError):
        net_gain(parcial, [0, 9])


# ── por la superficie MCP, que es por donde llega el aviso ──────────────────

def _mcp_texto(**kw):
    import art.mcp_server as srv
    fn = getattr(srv.test_interventions, "fn", srv.test_interventions)
    return "\n".join(getattr(x, "text", "") for x in fn(**kw))


@pytest.fixture(scope="module")
def fichero_parcial(tmp_path_factory):
    """El modelo de dos tramos, escrito a `.inp` para entrar por la herramienta.

    Con SEMILLAS A CERO, no con las estimaciones. Escribir el `.inp` desde el
    modelo ya ajustado lo convierte en un `.pre` disfrazado: el optimizador
    arranca en el óptimo, `niter` se queda en nada y la covarianza vuelve como
    la semilla del BFGS — y entonces ni este contraste ni ningún otro se puede
    hacer (BUG-0027). El `.inp` es la ESPECIFICACIÓN (BUG-0159).
    """
    from art.pipeline import _RESCALE_FACTOR, _write_inp
    d = tmp_path_factory.mktemp("neta")
    m = _modelo(-10.0, 6.0, dos_tramos=True)
    limpio = fue.Model(
        m.series, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR,
        ar=[[0.0]], ar_free=[[True]],
        interventions=[
            fue.Intervention("step", at=_T, omega=[0.0, 0.0],
                             omega_free=[True, True]),
            fue.Intervention("step", at=_TV, omega=[0.0], omega_free=[True])])
    f = str(d / "EPI.inp")
    _write_inp(m.series, limpio, f)
    return f


def test_la_puerta_que_el_aviso_ofrece_EXISTE(fichero_parcial):
    """El aviso de BUG-0157 manda a `test_interventions(..., ganancia_neta=[i, j])`.
    Ofrecer una salida que no existe es peor que no ofrecer ninguna."""
    txt = _mcp_texto(inp_path=fichero_parcial, ganancia_neta=[0, 1])
    assert "Traceback" not in txt
    assert "Ganancia NETA del episodio" in txt
    assert "PARCIAL" in txt


def test_sin_pedirla_no_sale(fichero_parcial):
    """Es un instrumento que el analista pide, no ruido por defecto."""
    txt = _mcp_texto(inp_path=fichero_parcial)
    assert "Ganancia NETA" not in txt


def test_un_indice_malo_no_tumba_la_herramienta(fichero_parcial):
    """El resto del contraste sigue valiendo: perderlo entero por un índice
    equivocado castiga al analista por un error de dedo."""
    txt = _mcp_texto(inp_path=fichero_parcial, ganancia_neta=[0, 9])
    assert "No se pudo contrastar la ganancia neta" in txt
    assert "Contraste de intervenciones" in txt
    assert "Traceback" not in txt
