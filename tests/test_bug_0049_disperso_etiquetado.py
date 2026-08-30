"""BUG-0049 — un candidato disperso no puede llevar la etiqueta del completo.

Un AR/MA DISPERSO tiene un solo coeficiente, en el retardo k, con los anteriores
en cero. Es un modelo distinto del completo del mismo orden, y se enumeraba con
la misma etiqueta: `ARIMA(2,1,0)(0,0,0)_4` aparecía dos veces con similitudes
distintas.
"""
import os
import warnings

import pytest

from art.describe import describe_identification
from art.model_detection import suggest_orders

INP = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/PGAS.inp"


@pytest.fixture
def resumen():
    if not os.path.exists(INP):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    from art.pipeline import _load_ts_model
    ts, _ = _load_ts_model(INP)
    return describe_identification(ts, d=1, D=0, lam=0.0).summary


def _lineas_candidatos(resumen):
    i = resumen.find("Candidatos ARMA")
    return [l for l in resumen[i:].splitlines() if "ARIMA(" in l]


def test_hay_un_caso_disperso_que_medir():
    """Si el caso deja de producir un disperso, el test no mide nada."""
    if not os.path.exists(INP):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    from art.pipeline import _load_ts_model
    ts, _ = _load_ts_model(INP)
    specs = suggest_orders(ts, d=1, D=0, lam=0.0, top_n=10)
    assert any(s.sparse_ar_lag or s.sparse_ma_lag for s in specs)


def test_ninguna_etiqueta_se_repite(resumen):
    """Dos modelos distintos no pueden presentarse con el mismo nombre."""
    etiquetas = []
    for linea in _lineas_candidatos(resumen):
        # todo lo que va del "ARIMA(" hasta el "sim=" identifica al candidato
        i, j = linea.find("ARIMA("), linea.find("sim=")
        etiquetas.append(linea[i:j].strip())
    assert len(etiquetas) == len(set(etiquetas)), (
        f"etiquetas repetidas: {etiquetas}")


def test_el_disperso_dice_en_que_retardo_esta(resumen):
    lineas = [l for l in _lineas_candidatos(resumen) if "sólo en B^" in l]
    assert lineas, "ningún candidato disperso se identificó como tal"
    for l in lineas:
        assert "AR sólo en B^" in l or "MA sólo en B^" in l
