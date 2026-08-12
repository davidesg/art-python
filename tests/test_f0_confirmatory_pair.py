"""El par confirmatorio en f=0 — su desacuerdo ES el diagnóstico.

Shin-Fuller y el DCD de sobrediferenciación tienen nulas OPUESTAS y acotan la
banda de cuasi-cancelación (SF_MEG, `tab:compare`). Se reportaban por separado,
así que sobre IPC_ES el informe emitía «considerar d+1» como si fuera una
conclusión, cuando lo que dice el par es que la serie está en la banda donde las
dos representaciones son equivalentes en previsión.

    lado AR  Shin-Fuller   Φ̂₁ᵤ = 37.536  →  d basta
    lado MA  DCD sobredif.  LR  =  4.220  →  d+1
    testigo  θ̂ = 0.9709 — a 0.03 de la frontera

El paper resuelve este mismo modelo —IPC español 2002-2019, n=216, logs, d=1,
AR(1), once deterministas— y concluye d=1: *«Φ̂₁ᵤ=37.5 confirms that a single
regular difference suffices»*. La lectura a corregir era la del DCD leído solo.

Se reportan además los dos avisos que el paper documenta y que sólo muerden aquí:

* en f=0 el regresor constante es **resonante** con la raíz unitaria, así que la
  ley desnuda s=1 (crít 1.94) no aplica a un modelo con deterministas — el paper
  mide pile-up 0.927 frente a 0.6575;
* y θ̂ < 1 significa que ℓ(θ=1) se evalúa justo donde el perfil de fue da un salto
  errático, que es lo que el apéndice del paper dice que hay que revisar con la
  verosimilitud exacta bandeada.
"""
import os

import pytest

_PRE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "bugs", "BUG-0010-repro", "IPC_ES_m10.pre")

pytestmark = pytest.mark.skipif(not os.path.exists(_PRE),
                                reason="falta IPC_ES_m10.pre")


def _ipc():
    import fue
    _ts, m = fue.load(_PRE)
    m.fit()
    return m


def _report(m):
    from art.describe import describe_formal_tests

    return describe_formal_tests(m, run_meg=False)


# ── el caso de la banda ────────────────────────────────────────────────────

def test_the_pair_is_reported_as_a_pair():
    d = _report(_ipc())
    assert "Par confirmatorio en f=0" in d.summary
    assert "lado AR" in d.summary and "lado MA" in d.summary


def test_the_disagreement_is_labelled_as_the_diagnostic():
    d = _report(_ipc())
    assert "cuasi-cancelación" in d.summary
    assert "DISCREPAN, y eso es el diagnóstico" in d.summary
    assert "equivalentes en previsión" in d.summary


def test_the_recommendation_no_longer_says_add_a_difference():
    """Lo que el informe emitía y no debía: «considerar d+1» a secas."""
    rec = _report(_ipc()).recommendation
    assert "cuasi-cancelación" in rec.lower()
    assert "NO cambies d" in rec
    # y la lectura antigua, como conclusión suelta, no puede estar
    assert "Considera aumentar d en 1" not in rec


def test_the_pair_travels_in_the_data():
    d = _report(_ipc())
    pair = d.data["f0_pair"]
    assert pair is not None
    assert pair["quasi_cancellation"] is True
    assert pair["sf_stationary"] is True          # el lado AR dice que d basta
    assert pair["dcd_lr"] > pair["dcd_crit_5pct"]  # el lado MA dice d+1
    assert 0.9 < pair["dcd_theta"] < 1.0           # θ̂ dentro de la banda


def test_both_paper_caveats_are_stated():
    """No basta con reportar el par: los dos límites conocidos del cálculo en
    f=0 tienen que salir, porque son los que explican el número."""
    s = _report(_ipc()).summary
    assert "RESONANTE" in s and "0.927" in s      # crítico: ley desnuda + resonancia
    assert "salto errático" in s                   # ℓ(θ=1) en la frontera


# ── el control: cuando NO discrepan, nada de esto debe aparecer ────────────

def test_a_series_where_the_pair_agrees_gets_no_band_warning():
    """Simulada I(1) con estacionalidad determinista: el testigo se apila en la
    frontera (θ̂=1.0000, LR≈0) y los dos contrastes coinciden en que d basta.
    Un aviso de banda ahí sería un falso positivo del propio aviso.
    """
    import numpy as np
    import fue
    from art.pipeline import _make_model

    rng = np.random.default_rng(203)
    n, t = 216, np.arange(216)
    y = (100 + np.cumsum(0.15 + rng.normal(0, 0.25, n))
         + 0.65 * np.cos(2 * np.pi * 2 * t / 12)
         + 0.325 * np.sin(2 * np.pi * 2 * t / 12))
    ts = fue.TimeSeries(list(y), freq=12, start=(2002, 1), name="SIM_I1")
    m = _make_model(ts, lam=1.0, d=1, D=0, p=1, q=0, n_harmonics=5,
                    seasonal=True, estimate_mu=True)
    m.fit()

    d = _report(m)
    assert d.data["f0_pair"]["quasi_cancellation"] is False
    assert "Los dos coinciden" in d.summary
    assert "DISCREPAN" not in d.summary
    assert "cuasi-cancelación" not in d.recommendation.lower()
