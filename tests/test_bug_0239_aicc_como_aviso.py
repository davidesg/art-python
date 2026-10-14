"""BUG-0239 — el AICc del identificador, de columna a AVISO.

La lista enseñaba un ΔAICc junto a la similitud, dentro del empate, sin decir qué
significaba ni cuál de los dos criterios manda. El AICc sólo gana a la
similitud en los mixtos casi cancelados, y ahí lo que dice es que el orden de
integración puede estar abierto (Salamanca, Villaverde: ARMA(1,1) con φ ≈ 0,95).
Ahora la columna sale y, cuando el mejor por AICc es un mixto persistente, va un
aviso que remite a `formal_tests`.
"""
import os
from types import SimpleNamespace

import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.describe import (_aviso_aicc_persistente, _raiz_real_mayor,
                          describe_identification)

BUGS = os.path.join(os.path.dirname(__file__), "..", "bugs")


def _sp(p, q, aicc, phi, theta):
    return SimpleNamespace(p=p, q=q, P=0, D=0, Q=0, aicc=aicc,
                           coef=(phi, theta, [], []))


def test_raiz_real_mayor():
    assert _raiz_real_mayor([0.95]) == pytest.approx(0.95)
    assert _raiz_real_mayor([]) == 0.0
    assert _raiz_real_mayor([1.0, -0.5]) == 0.0          # complejas
    assert _raiz_real_mayor([1.05, -0.091]) == pytest.approx(0.955, abs=1e-3)


def test_mixto_persistente_avisa_sin_ordenar():
    specs = [_sp(3, 0, -10.0, [0.2, 0.1, 0.2], []),
             _sp(1, 1, -12.0, [0.97], [0.87])]
    t = _aviso_aicc_persistente(specs, d=1)
    assert "ARIMA(1,1,1)" in t and "2.º de la lista" in t
    assert "orden de integración" in t and "formal_tests" in t


def test_ma_cerca_de_uno_avisa_de_la_diferencia_que_sobra():
    specs = [_sp(1, 0, -10.0, [0.3], []), _sp(0, 1, -12.0, [], [0.95])]
    assert "sobrar" in _aviso_aicc_persistente(specs, d=1)


def test_sin_persistencia_no_hay_aviso():
    specs = [_sp(1, 0, -10.0, [0.6], []), _sp(1, 1, -12.0, [0.5], [0.2])]
    assert _aviso_aicc_persistente(specs, d=1) == ""


@pytest.mark.parametrize("inp", ["BUG-0232-repro/Salamanca.inp",
                                 "BUG-0235-repro/Villaverde.inp"])
def test_salamanca_y_villaverde(inp):
    ruta = os.path.join(BUGS, inp)
    if not os.path.exists(ruta):
        pytest.skip("falta el .inp del repro")
    ts, _ = fue.load(ruta)
    t = describe_identification(ts, d=1, D=0, lam=0.0, estacional=False).summary
    assert "ΔAICc" not in t
    assert "Aviso del AICc" in t and "ARIMA(1,1,1)" in t


def test_ar_y_ma_que_se_cancelan_entre_si_no_avisan():
    """φ ≈ θ ≈ 0,95 se anulan entre sí, no con la diferencia: no es la señal."""
    specs = [_sp(1, 0, -10.0, [0.3], []), _sp(1, 1, -12.0, [0.95], [0.97])]
    assert _aviso_aicc_persistente(specs, d=1) == ""
