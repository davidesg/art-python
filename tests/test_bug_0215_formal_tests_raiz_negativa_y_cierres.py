"""BUG-0215 — formal_tests: raíz negativa, cierres y mensajes.

* Shin-Fuller tomaba la raíz AR real de menor módulo sin mirar su signo: un
  φ̂ = −0,9855 (frecuencia π) se leía como una raíz cerca de +1 y salía
  «raíz unitaria — considerar d+1» (Moncloa ARIMA(1,2,2)).
* El par en f=0 discrepando en el sentido «SF no rechaza / el DCD dice que la
  ∇ extra sobra» se rotulaba como la banda de cuasi-cancelación con el texto
  al revés.
* Con el par discrepando fuera de la banda, el cierre decía «no detectan
  problemas. El modelo es adecuado» (Latina AR(4)).
* Sobre un (0,1,0) con μ daba el DCD y a continuación «Ningún contraste
  aplicable» (IPC_DE).
* «medido sin AR» junto a un θ̂ testigo que depende del AR del modelo base.
"""
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.describe as describe
from art.describe import describe_formal_tests
from art.formal_tests import DCDResult, ShinFullerResult, shin_fuller
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar


def _estima(tmp, nombre, y, **kw):
    ts = fue.TimeSeries(list(map(float, y)), freq=1, start=(1900, 1),
                        name=nombre)
    f = str(tmp / f"{nombre}.inp")
    _write_inp(ts, fue.Model(ts, refactor=_RESCALE_FACTOR, **kw), f)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, m = estimar(f)
    return m


def _ar(phis, n, semilla):
    """∇y con el AR producto de (1 − φᵢB), y en nivel."""
    g = np.random.default_rng(semilla)
    poli = np.array([1.0])
    for p in phis:
        poli = np.convolve(poli, [1.0, -p])
    w = np.zeros(n + 50)
    e = g.standard_normal(n + 50)
    for t in range(len(poli), n + 50):
        w[t] = e[t] - sum(poli[j] * w[t - j] for j in range(1, len(poli)))
    return 50 + np.cumsum(w[50:] * 0.3)


@pytest.fixture(scope="module")
def tmp(tmp_path_factory):
    return tmp_path_factory.mktemp("b215")


@pytest.fixture(scope="module")
def negativo(tmp):
    """AR(1) con φ̂ ≈ −0,984 sobre ∇y, n=100: |φ̂| por encima de ρₘ=0,96,
    que es el caso de Moncloa (φ̂ = −0,9855)."""
    return _estima(tmp, "NEG", _ar([-0.99], 100, 5), d=1, boxlam=1.0,
                   ar=[[-0.9]], ar_free=[[True]])


# ═══════════════ Shin-Fuller: la raíz más cercana a +1, con signo ═══════════

def test_una_raiz_negativa_no_es_una_raiz_unitaria(negativo):
    phi = negativo.ar[0][0]
    # el testigo vale si |φ̂| supera ρₘ: ahí la versión anterior comparaba
    # |φ̂| con ρₘ y decía «raíz unitaria — considerar d+1»
    assert phi < -(1 - 4 / negativo.series.nobs), phi
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sf = shin_fuller(negativo)
    assert sf.phi_dominant == pytest.approx(phi, abs=1e-6)
    assert not sf.mas_integrado_que_la_nula
    assert sf.stationary, "no hay raíz en +1: el lado AR dice que d basta"


def test_el_informe_no_pide_d_mas_1_por_una_raiz_en_pi(negativo):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        d = describe_formal_tests(negativo, run_meg=False)
    s = d.summary
    assert "Raíz unitaria — considerar d+1" not in s
    assert "POR ENCIMA de la nula" not in s
    assert "NEGATIVA" in s and "Nyquist" in s
    assert "Considera aumentar d en 1" not in d.recommendation


def test_un_ar_negativo_pequeño_conserva_el_lado_ar(tmp):
    """Un ARIMA(1,1,0) con φ̂ < 0 es corriente: su lado AR existe."""
    m = _estima(tmp, "NEG3", _ar([-0.3], 240, 2), d=1, boxlam=1.0,
                ar=[[-0.2]], ar_free=[[True]])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sf = shin_fuller(m)
    assert sf.phi_dominant < 0 and sf.stationary


def test_con_una_raiz_positiva_y_otra_negativa_aisla_la_positiva(tmp):
    m = _estima(tmp, "MIX", _ar([0.5, -0.95], 240, 11), d=1, boxlam=1.0,
                ar=[[0.4], [-0.9]], ar_free=[[True], [True]])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sf = shin_fuller(m)
    assert sf.phi_dominant is not None and 0 < sf.phi_dominant < 0.9
    assert sf.stationary


# ═══════════════ el par: quién dice qué, y el cierre ═══════════════

@pytest.fixture(scope="module")
def base(tmp):
    """Un AR(1) adecuado sobre ∇y: el par se forma."""
    return _estima(tmp, "AR1", _ar([0.5], 240, 3), d=1, boxlam=1.0,
                   ar=[[0.4]], ar_free=[[True]])


def _sf(stationary: bool, n=240):
    return ShinFullerResult(
        phi_null=1 - 4 / n, phi_free=[0.97 if not stationary else 0.5],
        loglik_free=0.0, loglik_constrained=-5.0 if stationary else 0.0,
        phi_1u=5.0 if stationary else 0.3, crit_10pct=1.07, crit_5pct=1.76,
        crit_1pct=3.43, df=1, pvalue=0.5, n=n, s=1,
        phi_dominant=0.5 if stationary else 0.97)


def _od(theta: float, lr: float, n=240):
    return DCDResult(factor_index=0, freq=None, coef_free=theta, coef_null=1.0,
                     loglik_free=lr / 2, loglik_constrained=0.0, lr=lr, n=n)


def _informe(monkeypatch, m, sf, od):
    monkeypatch.setattr(describe, "shin_fuller", lambda _m: sf)
    monkeypatch.setattr(describe, "dcd_overdiff_regular", lambda _m: od)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return describe_formal_tests(m, run_meg=False)


def test_sf_no_rechaza_y_el_dcd_tampoco_el_texto_no_se_invierte(base,
                                                                 monkeypatch):
    """SF no rechaza la raíz unitaria y el testigo se apila en θ=1: con la
    distancia ≈0 se afirmaba la banda con el texto AL REVÉS («el lado MA
    detecta que r<1 y el lado AR ve un proceso casi estacionario»)."""
    d = _informe(monkeypatch, base, _sf(False), _od(0.98, 0.15))
    s, rec = d.summary, d.recommendation
    assert "NINGUNO rechaza su nula" in s
    assert "el lado MA detecta que r<1" not in s
    assert "equivalentes en previsión" in s
    assert d.data["f0_pair"]["quasi_cancellation"] is True
    assert d.data["f0_pair"]["discrepa"] == "sf_d+1"
    assert "Shin-Fuller dice que d basta" not in rec
    assert "Shin-Fuller no rechaza la raíz unitaria" in rec
    assert "El modelo es adecuado" not in rec


def test_sf_no_rechaza_fuera_de_la_banda_no_cierra(base, monkeypatch):
    d = _informe(monkeypatch, base, _sf(False), _od(0.80, 1.0))
    s, rec = d.summary, d.recommendation
    assert "NINGUNO rechaza su nula" in s and "NO es la banda" in s
    assert d.data["f0_pair"]["quasi_cancellation"] is False
    # el cierre lee el par: ni «adecuado» ni «considera aumentar d»
    assert "El modelo es adecuado" not in rec
    assert "Considera aumentar d en 1" not in rec
    assert "no cierran" in rec and "discrepa" in rec


def test_discrepan_fuera_de_la_banda_no_cierra_adecuado(base, monkeypatch):
    """Latina AR(4): SF dice que d basta, el DCD pide d+1 con θ̂ lejos de la
    frontera, y el cierre era «el modelo es adecuado»."""
    d = _informe(monkeypatch, base, _sf(True), _od(0.70, 9.0))
    s, rec = d.summary, d.recommendation
    assert "NO es la banda de cuasi-cancelación" in s
    assert "El modelo es adecuado" not in rec
    assert "no cierran" in rec and "fuera de la banda" in rec
    assert d.data["f0_pair"]["discrepa"] == "dcd_d+1"
    assert d.data["pendientes"]


def test_en_la_banda_el_texto_sigue_siendo_el_de_la_banda(base, monkeypatch):
    d = _informe(monkeypatch, base, _sf(True), _od(0.95, 9.0))
    assert "eso es el diagnóstico" in d.summary
    assert "Shin-Fuller dice que d basta" in d.recommendation
    assert d.data["f0_pair"]["quasi_cancellation"] is True


def test_si_coinciden_el_cierre_es_adecuado(base, monkeypatch):
    d = _informe(monkeypatch, base, _sf(True), _od(0.999, 0.0))
    assert "Los dos coinciden" in d.summary
    assert d.recommendation.endswith("El modelo es adecuado.")
    assert d.data["f0_pair"]["discrepa"] is None


# ═══════════════ mensajes: aplicabilidad y testigo ═══════════════

@pytest.fixture(scope="module")
def paseo(tmp):
    """(0,1,0) con μ, como IPC_DE."""
    g = np.random.default_rng(215)
    z = np.cumsum(g.standard_normal(200) * 0.01 + 0.002)
    return _estima(tmp, "RW", np.exp(4 + z), d=1, boxlam=0.0, mu=0.002,
                   estimate_mu=True)


def test_no_dice_ningun_contraste_tras_dar_el_dcd(paseo):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        d = describe_formal_tests(paseo, run_meg=False)
    assert "DCD sobre-diferenciación regular" in d.summary
    assert "Ningún contraste aplicable" not in d.summary


def test_el_testigo_dice_que_ar_conserva(paseo, base, monkeypatch):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sin_ar = describe_formal_tests(paseo, run_meg=False).summary
    assert "Candidato: ∇^2, sin AR regular" in sin_ar
    # con AR: lo nombra, y dice que θ̂ depende de él
    con_ar = _informe(monkeypatch, base, _sf(True), _od(0.999, 0.0)).summary
    assert "con el AR regular del modelo (AR(1), reestimado) dentro" in con_ar
    assert "depende del modelo base" in con_ar
    assert "medido sin AR)" not in con_ar
