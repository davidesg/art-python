"""BUG-0031 — el carril autónomo no podía montar un AR/MA ESTACIONAL. Nunca.

`suggest_orders` busca sobre (p, q, P, Q) con P_max = Q_max = 1, y cada spec que
devuelve LLEVA su par estacional. `decide_orders` devolvía sólo `(p, q)` y
`run_full` construía el `ModelSpec` sin tocar `P` ni `Q`, que se quedaban en 0.

La forma del defecto es la de BUG-0013, BUG-0015 y BUG-0016 por quinta vez: una
decisión que el motor SABE ejecutar y la capa de política no tiene por dónde
pedir. `_make_model` monta desde siempre la combinación D=0 "armónicos +
AR/MA estacional estacionario"; lo que faltaba era el cable.

Y no producía un modelo peor, sino uno INALCANZABLE: sobre una serie cuya
identificación coloca un P=1 en cabeza, el autónomo estimaba ese mismo spec sin
el operador estacional y cerraba con residuos que no son ruido blanco.

Testigo real: RATIO (Gasto/PIB Bolivia, 2004:1–2024:4) de la réplica del TFM.
`suggest_orders` la encabeza con (p=0, q=2, P=1, Q=0); el autónomo estimaba
(0,1,2) sin AR estacional y cerraba con Q p-min = 0.0000, mientras el modelo
guiado con AR(1)₄ φ̂ = 0.7277 (t = 9.57) pasa la diagnosis.
"""
import numpy as np
import pytest

import fue
from art.model_detection import suggest_orders
from art.policy import (ClaudePolicy, DefaultPolicy, decide_orders,
                        decide_seasonal_orders)
from art.pipeline import run_full
from art.diagnosis import diagnose


class _Spec:
    """Lo justo de un ModelSpec de suggest_orders para las reglas puras."""

    def __init__(self, p, q, P, Q):
        self.p, self.q, self.P, self.Q = p, q, P, Q


def _seasonal_ar_series(n=120, phi_s=0.7, seed=0):
    """Trimestral I(1) cuyo ∇ es un AR(1)₄ puro — el testigo sintético."""
    rng = np.random.default_rng(seed)
    a = rng.standard_normal(n + 40)
    w = np.zeros(n + 40)
    for t in range(4, n + 40):
        w[t] = phi_s * w[t - 4] + a[t]
    w = w[40:]
    level = 100.0 * np.exp(np.cumsum(w) / 50.0)
    return fue.TimeSeries(level.tolist(), freq=4, start=(2000, 1), name="SEASAR")


# ── la regla pura ────────────────────────────────────────────────────────────

def test_decide_seasonal_orders_reads_the_pair_decide_orders_drops():
    specs = [_Spec(0, 2, 1, 0)]
    assert decide_orders(specs) == (0, 2)
    assert decide_seasonal_orders(specs) == (1, 0)


def test_the_backend_forbidden_pair_is_never_returned():
    """El backend en C aborta con AR_s y MA_s libres a la vez; suggest_orders
    puntúa por correlograma y no sabe nada de eso, así que la guardia va aquí."""
    assert decide_seasonal_orders([_Spec(0, 0, 1, 1)]) == (1, 0)


def test_no_specs_means_no_seasonal_operator():
    assert decide_seasonal_orders([]) == (0, 0)


def test_the_analyst_pair_wins_over_the_heuristic():
    specs = [_Spec(0, 0, 1, 0)]
    assert ClaudePolicy().decide_seasonal_orders(specs) == (1, 0)
    assert ClaudePolicy(P=0).decide_seasonal_orders(specs) == (0, 0)
    assert ClaudePolicy(P=0, Q=1).decide_seasonal_orders(specs) == (0, 1)


# ── el motor, extremo a extremo ──────────────────────────────────────────────

def test_the_autonomous_lane_can_now_reach_a_seasonal_ar(tmp_path):
    """Lo que el defecto hacía imposible: que el autónomo lo monte.

    λ, d y D van fijados y correctos para que el único nodo que decide la
    heurística sea el de los órdenes — así el testigo aísla ESTE nodo.
    """
    ts = _seasonal_ar_series()
    specs = suggest_orders(ts, d=1, D=0, lam=0.0, top_n=5)
    assert specs[0].P >= 1, "la identificación ya no encabeza con un P>=1"

    out = str(tmp_path / "seasar.inp")
    res = run_full(ts, out,
                   decision_policy=ClaudePolicy(lam=0.0, d=1, D=0,
                                                decision="A", n_harmonics=0))
    m = res.final_model
    n_ar_s = sum(len(b) for b in (m.ar_s or []))

    assert res.P == 1 and res.Q == 0
    assert n_ar_s == 1, "el ModelSpec volvió a perder el par estacional"
    # φ₄ = 0.7 en el proceso generador
    assert m.ar_s[0][0] == pytest.approx(0.7, abs=0.12)
    # y lo que el defecto costaba: los residuos ahora son ruido blanco
    assert min(diagnose(m).q_pvalues) > 0.05


def test_a_non_seasonal_series_still_gets_no_seasonal_operator(tmp_path):
    """La otra cara: el cable no debe inyectar un operador estacional donde la
    identificación no lo pide. Un paseo aleatorio puro no tiene nada anual."""
    rng = np.random.default_rng(7)
    level = 100.0 + np.cumsum(rng.standard_normal(120))
    ts = fue.TimeSeries(level.tolist(), freq=4, start=(2000, 1), name="RW")

    res = run_full(ts, str(tmp_path / "rw.inp"),
                   decision_policy=DefaultPolicy())
    m = res.final_model
    assert sum(len(b) for b in (m.ar_s or [])) == 0
    assert sum(len(b) for b in (m.ma_s or [])) == 0
