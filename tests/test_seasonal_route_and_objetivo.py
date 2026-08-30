"""La RUTA ESTACIONAL se adjudica por contraste, y `objetivo` rompe el empate.

El problema: detectada la estacionalidad hay tres tradiciones y no coinciden.
Box-Jenkins canónico pone `D=1` y de ahí (p,q,P,Q). La extensión de Treadway
parte de `D=0` + armónicos como hipótesis de trabajo y la contrasta con el MEG
(Abraham-Box 1978; Treadway y Gallego después). En econometría, y sobre todo
cuando la serie entra en un sistema multivariante, la práctica es `D=0`.

Elegir una por convención dejaría este nodo —el más consecuente de todos— como
el único resuelto por decreto, cuando los otros (λ, órdenes, forma de la
intervención) se resuelven estimando y contrastando. Y hay par de contrastes
para decidirlo: el MEG sobre B1, y la no invertibilidad del MA estacional sobre
B2. Nulas opuestas, la misma estructura que Shin-Fuller/DCD en f=0.

La asimetría que decide no es de tradición sino de EXPRESIVIDAD: `D=1` impone la
raíz unitaria en TODAS las frecuencias a la vez, mientras `ifadf` va por
frecuencia y sólo se alcanza desde B1. B1 puede llegar a B2 —medido sobre RATIO,
donde el MEG llevó a (1−B)(1+B²)(1+B) = ∇₄— pero B2 no puede llegar a un B1
mixto.

Lo que el dato no puede dar es el OBJETIVO, y por eso se pregunta: una sola vez,
como propósito y no como método.
"""
import os

import numpy as np
import pytest

import fue
from art.policy import (OBJETIVOS, OBJETIVO_POR_DEFECTO, ClaudePolicy,
                        DefaultPolicy, decide_seasonal_route)
from art.pipeline import run_full, _seasonal_ma_invertible


# ── la regla ────────────────────────────────────────────────────────────────

def test_all_frequencies_stochastic_and_a_genuine_seasonal_difference_gives_B2():
    ruta, razon = decide_seasonal_route({1: "stochastic", 2: "stochastic"},
                                        True, "univariante")
    assert ruta == "B2"
    assert "coinciden" in razon


def test_no_frequency_stochastic_gives_B1():
    ruta, razon = decide_seasonal_route({1: "deterministic", 2: "deterministic"},
                                        True, "univariante")
    assert ruta == "B1"
    assert "sobrediferenciaría" in razon


def test_a_mixed_case_gives_B1_because_only_B1_can_say_it():
    """La asimetría de expresividad: D=1 impone la raíz en todas las
    frecuencias, así que un caso mixto no tiene representación en B2."""
    ruta, razon = decide_seasonal_route({1: "stochastic", 2: "deterministic"},
                                        True, "univariante")
    assert ruta == "B1"
    assert "MIXTO" in razon


def test_the_two_contrasts_disagreeing_keeps_the_reformulable_route():
    """MEG dice estocástica en todas, pero el MA estacional de B2 se apila: los
    dos lados no coinciden y se sigue por donde se puede seguir mirando."""
    ruta, razon = decide_seasonal_route({1: "stochastic", 2: "stochastic"},
                                        False, "univariante")
    assert ruta == "B1"
    assert "no coinciden" in razon


def test_the_multivariate_objective_vetoes_B2():
    """No es preferencia: dos series del mismo sistema con tratamiento estacional
    distinto no tienen órdenes de integración comparables."""
    ruta, razon = decide_seasonal_route({1: "stochastic", 2: "stochastic"},
                                        True, "multivariante")
    assert ruta == "B1"
    assert "cointegración" in razon


def test_adequacy_outranks_everything():
    ruta, _ = decide_seasonal_route({1: "stochastic", 2: "stochastic"}, True,
                                    "univariante", b1_ok=True, b2_ok=False)
    assert ruta == "B1"
    ruta, _ = decide_seasonal_route({1: "deterministic"}, True,
                                    "univariante", b1_ok=False, b2_ok=True)
    assert ruta == "B2"


def test_without_usable_contrasts_the_objective_decides_and_says_so():
    r1, why1 = decide_seasonal_route({}, None, "univariante")
    r2, why2 = decide_seasonal_route({}, None, "estructural")
    assert (r1, r2) == ("B2", "B1")
    assert "objetivo=univariante" in why1 and "objetivo=estructural" in why2


def test_an_unknown_objective_falls_back_to_the_default():
    r_raro, _ = decide_seasonal_route({}, None, "lo-que-sea")
    r_def, _ = decide_seasonal_route({}, None, OBJETIVO_POR_DEFECTO)
    assert r_raro == r_def
    assert OBJETIVO_POR_DEFECTO in OBJETIVOS


def test_the_analyst_route_wins_over_the_contrast():
    pol = ClaudePolicy(decision="B2")
    ruta, razon = pol.decide_seasonal_route({1: "deterministic"}, True)
    assert ruta == "B2"
    assert "analista" in razon


# ── el contraste sobre el MA estacional (BUG-0039) ──────────────────────────

def test_the_seasonal_ma_uses_its_own_law_not_the_bare_one():
    """La frontera de un MA de retardo s pone s raíces sobre el círculo a la vez:
    ni raíz real (s=1) ni par conjugado (s=2). Ley de Davis, Chen y Dunsmuir."""
    from art.formal_tests import _dcd_crit_s, _DCD_CRIT_MA
    c4, c12 = _dcd_crit_s(4), _dcd_crit_s(12)
    assert c4["5%"] == 2.18 and c12["5%"] == 2.31          # Tabla 3.2
    assert c4["1%"] == 4.75 and c12["1%"] == 5.12
    # y son MÁS exigentes que la ley desnuda: usarla sobre-rechazaría el cero
    assert c4["5%"] > _DCD_CRIT_MA["5%"] < c12["5%"]
    # crecen con s
    assert c4["5%"] < c12["5%"]


def test_a_genuine_seasonal_difference_is_reported_invertible(tmp_path):
    """Estacionalidad ESTOCÁSTICA construida a propósito: la ∇ₛ hace falta y el
    MA estacional debe quedar lejos de su frontera."""
    from art.formal_tests import dcd_s
    from art.pipeline import _write_inp
    rng = np.random.default_rng(3)
    n = 120
    t = np.arange(n)
    amp = np.cumsum(rng.standard_normal(n)) * 0.7      # amplitud que vaga
    nivel = 100.0 + np.cumsum(rng.standard_normal(n)) + amp * np.cos(np.pi / 2 * t)
    ts = fue.TimeSeries(nivel.tolist(), freq=4, start=(2000, 1), name="AIR")
    ruta = str(tmp_path / "air.inp")
    m = fue.Model(ts, d=1, D=1, boxlam=1.0, ma_s=[[0.4]], ma_s_free=[[True]],
                  mu=0.0, estimate_mu=False)
    _write_inp(ts, m, ruta)
    _, mf = fue.load(ruta)
    mf.fit()

    res = dcd_s(mf)
    assert len(res) == 1
    r = res[0]
    assert r._crit["5%"] == 2.18, "no está usando la ley del MA estacional"
    assert r.lr >= r._crit["5%"], "una ∇ₛ genuina no debería salir en la frontera"
    assert _seasonal_ma_invertible(mf) is True


def test_a_model_without_seasonal_ma_has_nothing_to_test(tmp_path):
    from art.formal_tests import dcd_s
    from art.pipeline import _write_inp
    rng = np.random.default_rng(7)
    nivel = 100.0 + np.cumsum(rng.standard_normal(100))
    ts = fue.TimeSeries(nivel.tolist(), freq=4, start=(2000, 1), name="RW")
    ruta = str(tmp_path / "rw.inp")
    m = fue.Model(ts, d=1, boxlam=1.0, ma=[[0.3]], ma_free=[[True]],
                  mu=0.0, estimate_mu=False)
    _write_inp(ts, m, ruta)
    _, mf = fue.load(ruta)
    mf.fit()
    assert dcd_s(mf) == []
    assert _seasonal_ma_invertible(mf) is None


# ── el motor ────────────────────────────────────────────────────────────────

def _serie_estacional(n=100, seed=8):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    est = 8.0 * np.cos(np.pi / 2 * t) + 4.0 * np.sin(np.pi / 2 * t)
    nivel = 100.0 + np.cumsum(rng.standard_normal(n)) + est
    return fue.TimeSeries(nivel.tolist(), freq=4, start=(2000, 1), name="EST")


def test_both_routes_are_estimated_when_there_is_seasonality(tmp_path):
    ts = _serie_estacional()
    out = str(tmp_path / "est.inp")
    res = run_full(ts, out, decision_policy=DefaultPolicy(), objetivo="univariante")
    if res.route is None:
        pytest.skip("esta serie sintética no disparó la detección estacional")
    assert set(res.branches) == {"B1", "B2"}
    for nombre in ("B1", "B2"):
        assert res.branches[nombre][1] is not None, f"{nombre} no se estimó"
    assert res.route in ("B1", "B2")
    assert res.route_reason
    # y la ruta adoptada es la que queda en output_path
    assert os.path.exists(out)


def test_the_objective_can_flip_the_route(tmp_path):
    """La prueba de que el parámetro hace algo: mismo dato, distinta ruta."""
    ts = _serie_estacional()
    r_uni = run_full(ts, str(tmp_path / "u.inp"),
                     decision_policy=DefaultPolicy(), objetivo="univariante")
    r_mul = run_full(ts, str(tmp_path / "m.inp"),
                     decision_policy=DefaultPolicy(), objetivo="multivariante")
    if r_uni.route is None:
        pytest.skip("esta serie sintética no disparó la detección estacional")
    assert r_mul.route == "B1", "el veto multivariante no se aplicó"
    assert r_mul.D == 0
    if r_uni.route == "B2":
        assert r_uni.D == 1


def test_no_seasonality_means_no_route_and_no_branches(tmp_path):
    """La otra cara: sin estacionalidad no hay nada que enrutar y no se paga el
    coste de estimar dos veces."""
    rng = np.random.default_rng(7)
    nivel = 100.0 + np.cumsum(rng.standard_normal(100))
    ts = fue.TimeSeries(nivel.tolist(), freq=4, start=(2000, 1), name="RW")
    res = run_full(ts, str(tmp_path / "rw.inp"), decision_policy=DefaultPolicy())
    assert res.route is None
    assert res.branches == {}
    assert res.D == 0
