"""BUG-0144 — la calibración decía «retardo 4, +0,067» y no decía QUÉ fechas.

Observación del analista mirando el panel de la ACF:

> *«Pero no dice a qué retardo distorsiona. Mira las calibraciones en los .out
> y no sé si tiene sentido, o estamos discutiendo otra cosa.»*

Y era otra cosa. `art` repartía la distorsión **por observación** —cuánto pone
cada anómalo—, y para que esa cuenta cerrara hacían falta dos términos de
corrección (BUG-0143). `fue` reparte **por PAR (t, t+k)**, que es la unidad
natural del estimador de Bartlett:

    r(k) = Σₜ (xₜ−μ̂)(xₜ₊ₖ−μ̂) / (n·σ̂²)

Los sumandos son los pares y **suman r(k) sin residuo**: ni canal de varianza
que separar ni pares de anómalos que sobren. Está en cada `.out` desde siempre,
bajo «Calibration of distortions of the ACF», y `art` no lo referenciaba: cero
apariciones en `src/`.

Las dos hacen falta y contestan cosas distintas — decisión del analista, que se
quedó con las dos:

    r_obs(k) − r_cal(k)   ¿cuánto se movería si intervengo?   ← decide
    pares dominantes      ¿qué fechas hacen este retardo?     ← explica

y la segunda es **la más específica**, en palabras del analista.
"""
import os
import re

import numpy as np
import pytest

fue = pytest.importorskip("fue")
from art.calibracion import (calibra_correlograma, describe_calibracion,
                             _pares_dominantes)

CASO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "bugs", "BUG-0126-repro", "caso", "RATIO_m10")


# ────────── la propiedad de fondo: suman r(k) sin residuo ──────────

def test_los_pares_suman_r_de_k_EXACTO():
    """Lo que la atribución por observación no puede dar. Sin residuo, sin
    canal de varianza, sin canal de media: el estimador es una suma sobre pares
    y ésta es esa suma."""
    for semilla in range(6):
        g = np.random.default_rng(semilla)
        n = int(g.integers(40, 160))
        x = np.cumsum(g.standard_normal(n)) + g.standard_normal(n)
        for i in g.choice(n, size=3, replace=False):
            x[i] += 8.0
        K = 12
        mu, var = float(x.mean()), float(x.var())
        z = x - mu
        todos = [float(z[:n - k] @ z[k:]) / (n * var) for k in range(1, K + 1)]
        r = fue.acf(x, lags=K)
        assert np.max(np.abs(np.array(todos) - r)) < 1e-12, \
            f"semilla {semilla}: los pares no suman la ACF"


def test_el_criterio_es_el_de_fue_no_el_valor_absoluto():
    """Se listan los pares que HACEN el retardo, no los mayores en |·|.

    Un par que compensa no explica el retardo, lo disimula, y mezclarlos deja
    una lista que no suma hacia el número que la encabeza.
    """
    n = 60
    x = np.zeros(n)
    x[10], x[14] = 6.0, 6.0          # par positivo grande en el retardo 4
    x[30], x[34] = 6.0, -6.0         # par negativo grande en el mismo retardo
    x = x - x.mean()
    pares = _pares_dominantes(x, 4, top=2)[3]
    r4 = float(fue.acf(x, lags=4)[3])
    # el signo de todo lo listado tiene que ser el de r(4)
    assert all((c > 0) == (r4 > 0) for _i, _j, c in pares), (r4, pares)


# ────────── homologación: el mismo objeto que el `.out` ──────────

def _bloque_del_out(ruta):
    """Los pares del `.out`, parseados: {lag: [(fecha1, fecha2, contrib)]}."""
    txt = open(ruta, encoding="latin-1").read()
    if "Calibration of distortions" not in txt:
        return {}
    blq = txt[txt.index("Calibration of distortions"):]
    fuera, lag = {}, None
    for ln in blq.splitlines():
        m1 = re.match(r"\s*\|\s*r\((\d+)\)\s*=\s*[-0-9.]+\s+"
                      r"(\d+)/(\d+)\s*-\s*(\d+)/(\d+)\s+([-0-9.]+)", ln)
        m2 = re.match(r"\s*\|\s+(\d+)/(\d+)\s*-\s*(\d+)/(\d+)\s+"
                      r"([-0-9.]+)\s*\|", ln)
        if m1:
            lag = int(m1.group(1))
            fuera[lag] = [(f"Q{m1.group(2)}/{m1.group(3)}",
                           f"Q{m1.group(4)}/{m1.group(5)}",
                           float(m1.group(6)))]
        elif m2 and lag is not None:
            fuera[lag].append((f"Q{m2.group(1)}/{m2.group(2)}",
                               f"Q{m2.group(3)}/{m2.group(4)}",
                               float(m2.group(5))))
    return fuera


@pytest.mark.skipif(not os.path.exists(CASO + ".out"),
                    reason="el caso del repro no está")
def test_reproduce_EXACTO_el_bloque_del_out():
    """La prueba que importa: mismos pares, mismas fechas, mismas cifras.

    No es una comprobación de estilo. Si `art` va a publicar este objeto, tiene
    que ser EL objeto —el que el analista ya lee en el `.out`—, no una segunda
    versión parecida. La suite tendría entonces dos calibraciones de pares que
    discrepan en la tercera cifra, que es exactamente la enfermedad que
    BUG-0142 acaba de quitar del correlograma.
    """
    from art.mcp_server import _load_fitted
    ts, m = _load_fitted(CASO + ".inp")
    r = np.asarray(m._result.residuals, dtype=float)
    freq = int(ts.freq)
    cal = calibra_correlograma(
        r, umbral=2.5, max_lag=15, freq=freq, start=ts.start,
        desfase=int(getattr(m, "d", 0)) + int(getattr(m, "D", 0)) * freq)

    suyo = _bloque_del_out(CASO + ".out")
    assert suyo, "el `.out` del caso no trae el bloque de calibración"

    mio = {d.lag: [(cal.fecha(i), cal.fecha(j), round(c, 3))
                   for i, j, c in d.pares]
           for d in cal.distorsiones}

    comparados = 0
    for lag, esperado in sorted(suyo.items()):
        if lag not in mio:
            continue
        esperado = [(a, b, round(c, 3)) for a, b, c in esperado]
        assert mio[lag][:len(esperado)] == esperado, (
            f"r({lag}) discrepa del `.out`\n"
            f"  .out: {esperado}\n  art : {mio[lag][:len(esperado)]}")
        comparados += 1
    assert comparados >= 9, f"sólo se compararon {comparados} retardos"


# ────────── el calendario, y qué pasa sin él ──────────

def test_sin_calendario_los_pares_se_nombran_por_su_indice():
    """`residuals` llega como lista pelada y no siempre hay calendario. Ahí lo
    honrado es decir «obs 41», no inventar una fecha."""
    g = np.random.default_rng(1)
    x = np.cumsum(g.standard_normal(90))
    cal = calibra_correlograma(x, umbral=2.5, max_lag=8)
    assert cal.fecha(40) == "obs 41"


def test_el_desfase_de_la_diferenciacion_va_en_la_fecha():
    """Los dos espacios de índices otra vez (BUG-0067): sobre residuos de un
    modelo con d=1 la observación 1 NO es la 1 de la serie."""
    g = np.random.default_rng(2)
    x = np.cumsum(g.standard_normal(90))
    sin_d = calibra_correlograma(x, max_lag=8, freq=4, start=(2004, 1))
    con_d = calibra_correlograma(x, max_lag=8, freq=4, start=(2004, 1),
                                 desfase=1)
    assert sin_d.fecha(0) == "Q1/2004"
    assert con_d.fecha(0) == "Q2/2004"


# ────────── que llegue al analista ──────────

def test_la_tabla_publica_los_pares_con_sus_fechas():
    # Serie casi blanca con DOS anómalos a cuatro períodos: ahí el par sí se
    # lleva el retardo, que es cuando la tabla dice algo (ver el guardián).
    g = np.random.default_rng(3)
    n = 120
    x = g.standard_normal(n) * 0.4
    x[60] += 9.0
    x[64] += 9.0
    cal = calibra_correlograma(x, umbral=2.5, max_lag=12, freq=4,
                               start=(2000, 1))
    txt = describe_calibracion(cal, nombre="X", con_figura=False).summary
    assert "Qué fechas hacen cada retardo" in txt
    assert re.search(r"Q\d/\d{4} – Q\d/\d{4}", txt), \
        "la tabla no lleva pares de fechas"


# ────────── el guardián: la tabla sólo cuando unos pocos pares mandan ──────────

def test_no_se_listan_pares_cuando_el_retardo_es_estructura_repartida():
    """El guardián, y por qué tiene lectura y no es un número de gusto.

    Medido, dos regímenes que no se solapan:

        residuos de RATIO_m10, un anómalo domina   el par mayor: 46 – 116%
        ∇ln RATIO, estacionalidad repartida        el par mayor:  5 –  10%

    Si el par mayor se lleva el 5% de r(k), ese retardo lo hacen treinta pares
    parecidos: es estructura repartida por la muestra, y nombrarle dos fechas
    engaña. La tabla sólo dice algo cuando unas pocas fechas SE LLEVAN el
    retardo — y entonces dice que ese retardo es un artefacto de esas fechas.
    """
    from art.calibracion import CUOTA_PAR_DOMINANTE
    g = np.random.default_rng(3)
    n = 120
    # estacionalidad fuerte y repartida: ningún par destaca
    x = 2.0 * np.sin(2 * np.pi * np.arange(n) / 4) + g.standard_normal(n) * 0.4
    cal = calibra_correlograma(x, umbral=2.5, max_lag=12, freq=4,
                               start=(2000, 1))
    txt = describe_calibracion(cal, nombre="X", con_figura=False).summary
    assert "Qué fechas hacen cada retardo" not in txt, (
        "no debería listar pares: aquí ningún par se lleva el retardo")

    # y la cuota real de esa serie, por debajo del umbral
    peor = max(abs(d.pares[0][2] / d.acf_obs)
               for d in cal.distorsiones
               if d.pares and abs(d.acf_obs) > 0.1)
    assert peor < CUOTA_PAR_DOMINANTE, peor


@pytest.mark.skipif(not os.path.exists(CASO + ".out"),
                    reason="el caso del repro no está")
def test_y_SI_se_listan_cuando_unas_fechas_se_llevan_el_retardo():
    """El otro lado: sobre los residuos del caso real la tabla aparece, y
    nombra el retardo que cambia el orden AR."""
    from art.mcp_server import _load_fitted
    ts, m = _load_fitted(CASO + ".inp")
    r = np.asarray(m._result.residuals, dtype=float)
    freq = int(ts.freq)
    cal = calibra_correlograma(
        r, umbral=2.5, max_lag=15, freq=freq, start=ts.start,
        desfase=int(getattr(m, "d", 0)) + int(getattr(m, "D", 0)) * freq)
    txt = describe_calibracion(cal, nombre="RATIO_m10",
                               con_figura=False).summary
    assert "Qué fechas hacen cada retardo" in txt
    # el retardo 6 es el que hace saltar la PACF de banda, y lo hacen las
    # fechas del episodio 2008-09
    assert "Q4/2008" in txt
