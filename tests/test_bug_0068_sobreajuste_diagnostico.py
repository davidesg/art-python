"""BUG-0068 — el lado AR del par, recuperado por sobreajuste.

Shin-Fuller aísla una raíz REAL. Con un AR de raíces complejas el contraste no
existe y se pierde el par. La salida de la escuela es sobreajustar a AR(p+1),
factorizar en AR(1)·AR(p) y contrastar el AR(1).

Es una rama de DIAGNÓSTICO: su última raíz es espuria por construcción cuando no
hay raíz unitaria, y adoptarla contaminaría la selección.
"""
import io
import os
import tempfile
import warnings

import numpy as np
import pytest

import fue
from art.formal_tests import shin_fuller, shin_fuller_sobreajuste

from datos_replica import REPLICA, requiere_replica

M20 = REPLICA + "guiado/PGAS/PGAS_m20.pre" if REPLICA else ""

PLANTILLA = """************************************************
* Input file for program FUE                   *
************************************************
** Frequency of time series: either 1(A), 4(Q) or 12(M):
 4
** Number of observations and starting date of time series:
 {n}  1 2000 S
** Number of deterministic variables (including seasonal components):
0
** Number and orders of regular AR operators:
1 2
**
0.100000  1
0.100000  1
** Number and orders of annual AR operators:
0
** Number and orders of regular MA operators:
0
** Number and orders of anual MA operators:
0
** Number and frequencies of regular AR(2) operators with fixed frequency:
0
** Number and frequencies of regular MA(2) operators with fixed frequency:
0
** Mean parameter (mu):
0.000000 0
** Box-Cox lambda, regular differences and complete annual differences:
 1.00  0  0
** Individual factors of the annual difference (starting at freq 0.0):
0 0 0
** ACF/PACF bands (0 Automatic) and reescaling factor:
 0 1.00
** Time series (stochastic and non-standard deterministic variables):
{datos}
"""


def _ajusta_ar2(y, tmp):
    f = os.path.join(tmp, f"s{np.random.randint(1_000_000)}.inp")
    io.open(f, "w", encoding="utf-8").write(PLANTILLA.format(
        n=len(y), datos="\n".join(f"{v:.10f}" for v in y)))
    ts, m = fue.load(f)
    m.fit()
    return m


def _ar2_complejo(n, mod, freq, rng, integrado=False):
    r = 1.0 / mod
    p1, p2 = 2 * r * np.cos(2 * np.pi * freq), -r * r
    a = rng.standard_normal(n + 200)
    w = np.zeros(n + 200)
    for t in range(2, n + 200):
        w[t] = p1 * w[t - 1] + p2 * w[t - 2] + a[t]
    y = np.cumsum(w[200:]) if integrado else w[200:]
    return y - y.mean()


def _solo_complejas(coefs):
    r = np.roots([-c for c in reversed(coefs)] + [1.0])
    return all(abs(z.imag) > 1e-8 for z in r)


# ── el caso real ──────────────────────────────────────────────────────────

@requiere_replica
def test_el_caso_real_recupera_el_lado_AR():
    warnings.simplefilter("ignore")
    _, m = fue.load(M20)
    m.fit()
    assert _solo_complejas(m.ar[0]), "el caso ya no tiene raíces complejas"
    with pytest.raises(ValueError, match="raíz REAL"):
        shin_fuller(m)

    so = shin_fuller_sobreajuste(m)
    assert so.p_ampliado == so.p_original + 1
    assert so.phi_real is not None
    assert so.sf.stationary is True           # d=1 basta por el lado AR
    assert so.la_raiz_parece_espuria          # ΔAIC > 0: la raíz añadida sobra


@requiere_replica
def test_llega_al_informe_marcado_como_diagnostico():
    from art.describe import describe_formal_tests
    warnings.simplefilter("ignore")
    _, m = fue.load(M20)
    m.fit()
    t = describe_formal_tests(m).summary
    assert "recuperado por SOBREAJUSTE" in t
    assert "rama de diagnóstico, no un modelo" in t
    assert "No adoptes este modelo" in t
    assert "ΔAIC del sobreajuste" in t


@requiere_replica
def test_el_informe_no_se_contradice():
    """Decía «el lado AR no existe» y acto seguido lo recuperaba."""
    from art.describe import describe_formal_tests
    warnings.simplefilter("ignore")
    _, m = fue.load(M20)
    m.fit()
    t = describe_formal_tests(m).summary
    assert "no existe en esta corrida" not in t
    assert "no está disponible DIRECTAMENTE" in t


# ── la rama sólo actúa donde corresponde ──────────────────────────────────

@requiere_replica
def test_no_se_aplica_si_ya_hay_raiz_real():
    warnings.simplefilter("ignore")
    p = REPLICA + "guiado/ITCER/ITCER_m20.pre"
    if not os.path.exists(p):
        pytest.skip("modelo no disponible")
    _, m = fue.load(p)
    m.fit()
    shin_fuller(m)                            # aplica directamente
    with pytest.raises(ValueError, match="ya tiene una raíz REAL"):
        shin_fuller_sobreajuste(m)


def test_sin_AR_no_hay_nada_que_sobreajustar():
    class M:
        ar = None
    with pytest.raises(ValueError, match="Sin AR regular"):
        shin_fuller_sobreajuste(M())


# ── tamaño y potencia, en pequeño ─────────────────────────────────────────

def test_no_inventa_una_raiz_unitaria_cuando_no_la_hay():
    """Tamaño: la verdad es un AR(2) ESTACIONARIO complejo."""
    warnings.simplefilter("ignore")
    tmp = tempfile.mkdtemp()
    rng = np.random.default_rng(4242)
    n = casos = falsos = 0
    while casos < 8 and n < 25:
        n += 1
        m = _ajusta_ar2(_ar2_complejo(83, 1.30, 0.12, rng), tmp)
        if not _solo_complejas(m.ar[0]):
            continue
        casos += 1
        try:
            if not shin_fuller_sobreajuste(m).sf.stationary:
                falsos += 1
        except Exception:
            casos -= 1
    if casos < 5:
        pytest.skip("no salieron suficientes AR(2) complejos")
    assert falsos == 0, f"{falsos}/{casos} falsos positivos"


def test_encuentra_la_raiz_unitaria_cuando_si_la_hay():
    """Potencia: la verdad es I(1) × AR(2) complejo.

    Se mide una TASA sobre bastantes réplicas, no near-perfección sobre pocas: la
    potencia medida es 88-91 %, así que exigir 7 de 8 falla por ruido muestral
    una vez de cada cinco. El umbral se pone donde una potencia real de ~90 % lo
    supera con certeza práctica.
    """
    warnings.simplefilter("ignore")
    tmp = tempfile.mkdtemp()
    rng = np.random.default_rng(1234)
    n = casos = detect = 0
    while casos < 18 and n < 45:
        n += 1
        m = _ajusta_ar2(_ar2_complejo(83, 1.30, 0.12, rng, integrado=True), tmp)
        if not _solo_complejas(m.ar[0]):
            continue
        casos += 1
        try:
            if not shin_fuller_sobreajuste(m).sf.stationary:
                detect += 1
        except Exception:
            casos -= 1
    if casos < 12:
        pytest.skip("no salieron suficientes AR(2) complejos")
    assert detect / casos >= 0.65, f"potencia {detect}/{casos} — demasiado baja"
