"""BUG-0056 — la capa de evidencia informa; no manda.

`describe_unit_root` es la capa de EVIDENCIA: `recommended_d` sigue en crudo para
que `policy.decide_d` no lo tope dos veces. Lo que no puede hacer es presentar ese
crudo con voz de recomendación, porque quien llama a la herramienta directamente
se salta la política sin enterarse.
"""
import os
import warnings

import numpy as np
import pytest

import fue
from art.describe import describe_unit_root
from art.policy import decide_d

R = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/"


def _desc(inp):
    if not os.path.exists(inp):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    from art.pipeline import _load_ts_model
    ts, _ = _load_ts_model(inp)
    return describe_unit_root(ts, lam=0.0, max_d=2)


def test_la_evidencia_sigue_cruda():
    """Si se topara aquí, `decide_d` toparía sobre lo ya topado."""
    d = _desc(R + "RATIO.inp")
    assert d.data["recommended_d"] == 2, (
        "el caso cambió: RATIO ya no produce el salto que este test mide")


def test_el_texto_lleva_el_tope_y_su_razon():
    d = _desc(R + "RATIO.inp")
    assert d.data["recommended_d_policy"] == 1
    assert "Punto de partida recomendado: d = 1" in d.summary
    # Las dos razones, no una: el paso y la estacionalidad sin contrastar.
    assert "Un paso cada vez" in d.summary
    assert "estacionalidad" in d.summary
    # Y adónde se difiere la decisión de verdad.
    assert "formal_tests" in d.summary


def test_no_ordena_usar_el_d_crudo():
    d = _desc(R + "RATIO.inp")
    assert "Usa d=2" not in d.recommendation
    assert "d=1" in d.recommendation


@pytest.mark.parametrize("serie", ["ITCER", "PGAS"])
def test_sin_discrepancia_no_se_añade_ruido(serie):
    """El aviso sólo aparece donde evidencia y política difieren."""
    d = _desc(R + f"{serie}.inp")
    assert d.data["recommended_d"] == d.data["recommended_d_policy"]
    assert "Punto de partida recomendado" not in d.summary


def test_sintetico_i2_tambien_se_topa(tmp_path):
    """No depende de los datos de la réplica: cualquier salto 0→2 se topa."""
    warnings.simplefilter("ignore")
    rng = np.random.default_rng(5)
    w = np.cumsum(np.cumsum(rng.standard_normal(160)))     # I(2)
    ts = fue.TimeSeries((100.0 + w / w.std() * 10).tolist(),
                        freq=4, start=(2000, 1), name="I2")
    d = describe_unit_root(ts, lam=1.0, max_d=2)
    if d.data["recommended_d"] < 2:
        pytest.skip("la muestra no produjo un d crudo de 2")
    assert d.data["recommended_d_policy"] == 1
    assert decide_d(d.data, seasonal=None, current_d=0, max_step=1) == 1
