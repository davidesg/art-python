"""BUG-0054 y BUG-0055 — un aviso que no se puede leer, y un titular que se retira.

0054: la alarma de estacionalidad residual se calcula sobre los residuos, así que
sobre residuos sucios no es un contraste. En trimestral el retardo 2 ES Nyquist.
0055: el titular del DCD de sobrediferenciación decía «considerar d+1» y el mismo
bloque lo desmentía tres párrafos más abajo.
"""
import os
import warnings

import numpy as np
import pytest

from datos_replica import REPLICA, REPLICA_DS


PGAS = REPLICA + "run2/PGAS/"


def _modelo(nombre):
    if not os.path.exists(PGAS + nombre):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    from art.mcp_server import _load_fitted
    return _load_fitted(PGAS + nombre)[1]


# ── BUG-0054 ──────────────────────────────────────────────────────────────

def test_sobre_residuos_sucios_la_alarma_se_declara_no_leible():
    from art.describe import describe_diagnosis
    from art.diagnosis import diagnose

    m = _modelo("PGAS_m03.pre")
    dg = diagnose(m)
    if not (min(dg.q_pvalues) < 0.05 and dg.seasonal and dg.seasonal.seasonal_detected):
        # Ya no es un testigo (fue >= 0.1.17 estima mejor): la lógica la guarda
        # test_sintetico_residuos_sucios_alarma_no_leible.
        pytest.skip("el testigo de la réplica ya no tiene residuos sucios con la "
                    "alarma estacional: no mide nada (la guarda el caso sintético)")

    txt = describe_diagnosis(m).summary
    assert "NO LEÍBLE" in txt
    assert "REGULAR" in txt          # nombra la causa
    assert "Nyquist" in txt          # y el mecanismo


def test_corregido_el_arma_regular_la_alarma_se_calla_sola():
    """La prueba de que era estructura regular disfrazada: no se tocó nada estacional."""
    from art.diagnosis import diagnose
    m3, m4 = _modelo("PGAS_m03.pre"), _modelo("PGAS_m04.pre")
    d3, d4 = diagnose(m3), diagnose(m4)
    if not (d3.seasonal and d3.seasonal.seasonal_detected):
        pytest.skip("el testigo de la réplica ya no levanta la alarma en m03: "
                    "no mide nada")
    assert d3.seasonal.seasonal_detected and not d4.seasonal.seasonal_detected
    assert min(d4.q_pvalues) > 0.05


def test_con_residuos_limpios_no_se_pone_la_coletilla():
    """La advertencia sólo aparece donde hay algo que advertir."""
    from art.describe import describe_diagnosis
    txt = describe_diagnosis(_modelo("PGAS_m04.pre")).summary
    assert "NO LEÍBLE" not in txt


# ── BUG-0055 ──────────────────────────────────────────────────────────────

def _titular_dcd_sobre(m):
    from art.describe import describe_formal_tests
    t = describe_formal_tests(m).summary
    i = t.find("DCD sobre-diferenciación")
    if i < 0:
        pytest.skip("el DCD de sobrediferenciación no aplica a este modelo")
    return t[i:].splitlines()[1]


def test_el_titular_no_afirma_lo_que_el_bloque_retira():
    tit = _titular_dcd_sobre(_modelo("PGAS_m04.pre"))
    if "d+1" not in tit:
        pytest.skip("el testigo de la réplica ya no produce el veredicto d+1: no "
                    "mide nada (la guarda test_sintetico_titular_d_mas_1_no_desnudo)")
    # No puede quedarse en la afirmación desnuda.
    assert ("NO es concluyente" in tit) or ("un solo lado" in tit)


def test_el_titular_nombra_por_que_no_concluye():
    tit = _titular_dcd_sobre(_modelo("PGAS_m04.pre"))
    if "d+1" not in tit:
        pytest.skip("el testigo de la réplica ya no produce el veredicto d+1")
    # BUG-0011: con sólo armónicos el crítico es «algo bajo» (medido ≈2.15);
    # con deterministas de baja frecuencia, «puede estar SUBESTIMADO».
    assert "SUBESTIMADO" in tit or "algo bajo" in tit or "par" in tit


# ── los mismos casos, construidos: no dependen de la réplica ───────────────

def _sintetico(tmp_path, freq=4, n=120, seed=5, **kw):
    import fue
    rng = np.random.default_rng(seed)
    y = 100.0 + np.cumsum(rng.standard_normal(n))
    ts = fue.TimeSeries(y.tolist(), freq=freq, start=(2000, 1), name="S")
    m = fue.Model(ts, boxlam=1.0, d=1, mu=0.0, estimate_mu=False, **kw)
    warnings.simplefilter("ignore")
    m.fit()
    return m


def _alarma(freq):
    from art.seasonal_detection import FreqResult, SeasonalDetectionResult
    return SeasonalDetectionResult(
        name="residuals", freq=freq, d=0, lam=1.0, seasonal_detected=True,
        f_stat=3.16, p_value=0.0293, dummies=np.zeros(freq), dummy_se=np.ones(freq),
        harmonic_coeffs=np.zeros(freq - 1),
        freq_results=[FreqResult(2, 1, 6.1, 0.013, True)], n_obs=119, message="")


def test_sintetico_residuos_sucios_alarma_no_leible(tmp_path, monkeypatch):
    """BUG-0054: la alarma estacional sobre residuos que no son ruido blanco se
    declara NO LEÍBLE, nombra la causa (estructura REGULAR) y el mecanismo
    (Nyquist en s=4)."""
    import art.describe as D
    from art.diagnosis import diagnose
    m = _sintetico(tmp_path)
    r = diagnose(m)
    r.q_pvalues = [0.0358] * len(r.q_pvalues)
    r.seasonal = _alarma(4)
    assert not r.white_noise
    monkeypatch.setattr(D, "diagnose", lambda model: r)
    txt = D.describe_diagnosis(m).summary
    assert "NO LEÍBLE" in txt and "REGULAR" in txt and "Nyquist" in txt


def test_sintetico_residuos_limpios_sin_coletilla(tmp_path, monkeypatch):
    """La misma alarma con residuos de ruido blanco no lleva la advertencia."""
    import art.describe as D
    from art.diagnosis import diagnose
    m = _sintetico(tmp_path)
    r = diagnose(m)
    r.q_pvalues = [0.6] * len(r.q_pvalues)
    r.seasonal = _alarma(4)
    assert r.white_noise
    monkeypatch.setattr(D, "diagnose", lambda model: r)
    assert "NO LEÍBLE" not in D.describe_diagnosis(m).summary


def _dcd_rechaza():
    import types
    return types.SimpleNamespace(calculable=True, coef_free=0.62, lr=7.4,
                                 _crit={"1%": 3.2, "5%": 1.94, "10%": 1.3},
                                 motivo_no_calculable="")


def _titular(m, monkeypatch, sf_falta):
    import art.describe as D
    monkeypatch.setattr(D, "dcd_overdiff_regular", lambda model: _dcd_rechaza())
    if sf_falta:
        def _sin_sf(model):
            raise ValueError("este modelo no tiene AR regular libre")
        monkeypatch.setattr(D, "shin_fuller", _sin_sf)
    t = D.describe_formal_tests(m, run_meg=False).summary
    i = t.find("DCD sobre-diferenciación")
    assert i >= 0, "el bloque del DCD no salió"
    return t[i:].splitlines()[1]


def test_sintetico_titular_d_mas_1_no_desnudo(tmp_path, monkeypatch):
    """BUG-0055: cuando el lado MA rechaza pero falta el lado AR, el titular dice
    d+1 CON su salvedad dentro, no a pelo."""
    m = _sintetico(tmp_path)
    tit = _titular(m, monkeypatch, sf_falta=True)
    assert "d+1" in tit
    assert "NO es concluyente" in tit and "falta el lado AR del par" in tit


def test_sintetico_titular_nombra_los_deterministas(tmp_path, monkeypatch):
    """Con un escalón (determinista de baja frecuencia) el crítico puede estar
    SUBESTIMADO, y el titular lo dice."""
    import fue
    m = _sintetico(tmp_path, interventions=[fue.Intervention(
        "step", at=60, omega=[0.0], omega_free=[True])])
    tit = _titular(m, monkeypatch, sf_falta=False)
    assert "d+1" in tit and "SUBESTIMADO" in tit
