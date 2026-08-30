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

PGAS = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/run2/PGAS/"


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
    assert min(dg.q_pvalues) < 0.05, "el caso ya no tiene residuos sucios"
    assert dg.seasonal and dg.seasonal.seasonal_detected, "la alarma ya no salta"

    txt = describe_diagnosis(m).summary
    assert "NO LEÍBLE" in txt
    assert "REGULAR" in txt          # nombra la causa
    assert "Nyquist" in txt          # y el mecanismo


def test_corregido_el_arma_regular_la_alarma_se_calla_sola():
    """La prueba de que era estructura regular disfrazada: no se tocó nada estacional."""
    from art.diagnosis import diagnose
    m3, m4 = _modelo("PGAS_m03.pre"), _modelo("PGAS_m04.pre")
    d3, d4 = diagnose(m3), diagnose(m4)
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
    assert "d+1" in tit, "el caso ya no produce ese veredicto"
    # No puede quedarse en la afirmación desnuda.
    assert ("NO es concluyente" in tit) or ("un solo lado" in tit)


def test_el_titular_nombra_por_que_no_concluye():
    tit = _titular_dcd_sobre(_modelo("PGAS_m04.pre"))
    assert "SUBESTIMADO" in tit or "par" in tit
