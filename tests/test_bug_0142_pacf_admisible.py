"""BUG-0142 — la PACF calibrada valía +3,394, y la PACF decide el orden AR.

El estimador anterior normalizaba cada retardo por SUS pares retenidos. Es
insesgado retardo a retardo y tiene un defecto que lo invalida: cada r(k) se
estima sobre un subconjunto distinto, así que la secuencia no es una función de
autocovarianza, la matriz de Toeplitz que forma no es definida positiva, y
Durbin-Levinson sobre ella diverge.

Un coeficiente de autocorrelación parcial vive en [−1, 1]. Fuera de ahí no hay
nada que leer — y es la función con la que se decide el orden AR, que es la
mayoría de los modelos.

El arreglo es el estimador, no el dibujo: relleno con ceros sobre las
desviaciones, que es admisible **por construcción** porque r(k) vuelve a ser la
autocorrelación de una sucesión real.
"""
import numpy as np
import pytest

fue = pytest.importorskip("fue")
from art.calibracion import _acf_pacf, _durbin_levinson, calibra_correlograma


# ────────── EL defecto ──────────

def _serie_que_reventaba(n=83, semilla=0):
    """Estacionalidad fuerte y un anómalo. Sobre ruido blanco NO se reproduce:
    hace falta una ACF cerca del círculo unidad para que la varianza de
    innovación llegue a derrumbarse, que es lo que tiene el ∇ln del RATIO."""
    rng = np.random.default_rng(semilla)
    t = np.arange(n)
    y = 3.0 * np.sin(2 * np.pi * t / 4) + 0.6 * ((-1.0) ** t) \
        + rng.standard_normal(n) * 0.4
    y = (y - y.mean()) / y.std(ddof=0)
    y[64] += 6.0
    return y


def test_la_pacf_calibrada_esta_en_el_intervalo():
    """Con el estimador viejo esto daba máx|φ| = 15,3 con UN solo omitido."""
    y = _serie_que_reventaba()
    om = {i for i in range(len(y)) if abs(y[i]) > 2.0}
    assert om, "el caso tiene que omitir algo"
    _r, p = _acf_pacf(y, 15, omitir=om)
    assert np.all(np.abs(p[~np.isnan(p)]) <= 1.0), \
        f"PACF fuera de [-1,1]: {p}"


def test_la_acf_calibrada_es_definida_positiva():
    """La propiedad de fondo, comprobada donde vive: los autovalores de la
    Toeplitz. Es lo que garantiza |φ(k)| ≤ 1 y lo que la eliminación por pares
    no podía dar."""
    from scipy.linalg import toeplitz
    y = _serie_que_reventaba()
    om = {i for i in range(len(y)) if abs(y[i]) > 2.0}
    r, _p = _acf_pacf(y, 15, omitir=om)
    ev = np.linalg.eigvalsh(toeplitz(np.concatenate(([1.0], r))))
    assert ev.min() >= -1e-10, f"la Toeplitz no es PSD: mínimo {ev.min()}"


@pytest.mark.parametrize("semilla", range(40))
def test_bateria_de_estres_ninguna_pacf_se_sale(semilla):
    """Cuarenta series distintas —frecuencia, amplitud, deriva y número de
    anómalos al azar— y ni una sola |φ| > 1."""
    g = np.random.default_rng(semilla)
    n = int(g.integers(40, 200))
    t = np.arange(n)
    frq = int(g.choice([1, 4, 12]))
    z = float(g.uniform(0, 5)) * np.sin(2 * np.pi * t / max(frq, 2)) \
        + 0.8 * ((-1.0) ** t) \
        + np.cumsum(g.standard_normal(n)) * float(g.uniform(0, 0.5)) \
        + g.standard_normal(n) * 0.5
    z = (z - z.mean()) / z.std(ddof=0)
    for i in g.choice(n, size=int(g.integers(1, 6)), replace=False):
        z[i] += float(g.choice([-1, 1])) * g.uniform(4, 12)
    z = (z - z.mean()) / z.std(ddof=0)
    om = {i for i in range(n) if abs(z[i]) > 2.0}
    if len(om) >= n - 3:
        pytest.skip("no queda serie tras omitir")
    K = min(3 * max(frq, 1) + 3, n - 2)
    _r, p = _acf_pacf(z, K, omitir=om)
    vivos = p[~np.isnan(p)]
    assert np.all(np.abs(vivos) <= 1.0), f"semilla {semilla}: {p}"


# ────────── la red, que no debería saltar nunca ──────────

def test_durbin_levinson_se_niega_a_publicar_un_imposible():
    """La ACF de la izquierda no es admisible y la recursión tiene que decirlo.

    Es una entrada construida a mano: ninguna serie la produce con el estimador
    de hoy. Es la red por si alguien vuelve a alimentar la recursión con una
    secuencia que no viene de una sucesión real.
    """
    r = np.array([0.99, 0.99, 0.99, -0.99, 0.99])
    p = _durbin_levinson(r)
    vivos = p[~np.isnan(p)]
    assert np.all(np.abs(vivos) <= 1.0), p
    assert np.isnan(p).any(), "tenía que declararse indefinida en algún retardo"


def test_la_red_no_salta_sobre_el_estimador_bueno():
    """Y la comprobación del otro lado: con el estimador de hoy no hay NaN."""
    y = _serie_que_reventaba()
    om = {i for i in range(len(y)) if abs(y[i]) > 2.0}
    _r, p = _acf_pacf(y, 15, omitir=om)
    assert not np.isnan(p).any(), f"la red saltó sin motivo: {p}"


# ────────── que la tabla también quede sana ──────────

def test_la_tabla_de_calibracion_no_publica_pacf_imposibles():
    y = _serie_que_reventaba()
    cal = calibra_correlograma(y, umbral=2.0, max_lag=15)
    malas = [d.lag for d in cal.distorsiones
             if np.isfinite(d.pacf_cal) and abs(d.pacf_cal) > 1.0]
    assert not malas, f"retardos con |PACF calibrada| > 1: {malas}"
