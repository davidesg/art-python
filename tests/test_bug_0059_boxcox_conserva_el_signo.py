"""BUG-0059 — el módulo decide, el signo diagnostica.

La correlación media-dispersión se imprimía en valor absoluto. El módulo es el
criterio correcto para elegir escala, pero el signo dice si la transformación se
queda corta (corr>0) o se pasa (corr<0) — y con signos OPUESTOS la λ correcta
está entre las dos, que no es lo mismo que «ambas son razonables».
"""
import os
import warnings

import numpy as np
import pytest

import fue
from art.describe import describe_boxcox

from datos_replica import REPLICA, REPLICA_DS


R = REPLICA


def _desc(inp):
    if not os.path.exists(inp):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    from art.pipeline import _load_ts_model
    ts, _ = _load_ts_model(inp)
    return describe_boxcox(ts)


def test_el_signo_viaja_en_los_datos():
    d = _desc(R + "PGAS.inp")
    assert d.data["corr_raw_signed"] > 0
    assert d.data["corr_log_signed"] < 0


def test_el_modulo_sigue_siendo_el_que_decide():
    """`gap` y `corr_*` no cambian: la política no puede verse afectada."""
    d = _desc(R + "PGAS.inp")
    assert d.data["corr_raw"] == pytest.approx(abs(d.data["corr_raw_signed"]))
    assert d.data["corr_log"] == pytest.approx(abs(d.data["corr_log_signed"]))
    assert d.data["gap"] == pytest.approx(d.data["corr_raw"] - d.data["corr_log"])


def test_se_imprimen_con_signo():
    d = _desc(R + "PGAS.inp")
    assert f"{d.data['corr_raw_signed']:+.3f}" in d.summary
    assert f"{d.data['corr_log_signed']:+.3f}" in d.summary


def test_la_horquilla_se_nombra_cuando_la_hay():
    d = _desc(R + "PGAS.inp")
    assert d.data["horquilla"] is True
    txt = d.summary.replace("**", "")
    assert "signos son OPUESTOS" in txt
    assert "ENTRE las dos" in txt
    # y remite a quien SÍ cierra la decisión
    assert "DOMINIO" in txt


@pytest.mark.parametrize("serie", ["ITCER", "RATIO"])
def test_sin_horquilla_no_se_avisa(serie):
    d = _desc(R + f"{serie}.inp")
    assert d.data["horquilla"] is False
    assert "signos son OPUESTOS" not in d.summary.replace("**", "")


def test_la_lectura_del_signo_es_la_correcta():
    """corr>0 se queda corta; corr<0 se pasa."""
    d = _desc(R + "PGAS.inp")
    lineas = [l for l in d.summary.splitlines() if "Correlación media-std" in l]
    assert len(lineas) == 2
    l1 = next(l for l in lineas if "λ=1" in l)
    l0 = next(l for l in lineas if "λ=0" in l)
    assert "se queda corta" in l1     # +0.150
    assert "se pasa" in l0            # −0.173


def test_un_caso_sintetico_sin_dependencia_no_se_lee_como_nada():
    warnings.simplefilter("ignore")
    rng = np.random.default_rng(0)
    ts = fue.TimeSeries((100 + rng.standard_normal(120)).tolist(),
                        freq=4, start=(2000, 1), name="PLANA")
    d = describe_boxcox(ts)
    assert d.data["horquilla"] is False, (
        "sin dependencia apreciable no puede haber horquilla")
