"""El `.pre` que se encadena tiene que ser de ESTA serie (BUG-0099).

El guardián comparaba `nobs` y `freq` —la FORMA— y no el contenido. Dos series
mensuales de la misma longitud pasaban, y en el propio TFM hay tres. Lo que sale
es un modelo con los deterministas de otra serie —armónicos, media,
intervenciones y sus fechas— estimado sobre ésta, sin un solo aviso.
"""
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.mcp_server import _exige_la_misma_serie
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar


def _serie(seed, escala=0.4, start=(2010, 1), n=120):
    r = np.random.default_rng(seed)
    y = np.cumsum(r.standard_normal(n) * escala) + 100.0
    return fue.TimeSeries(y.tolist(), freq=12, start=start, name="S")


@pytest.fixture(scope="module")
def pre_de_A(tmp_path_factory):
    d = tmp_path_factory.mktemp("enc")
    A = _serie(7)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = fue.Model(A, d=1, mu=0.0, estimate_mu=True, refactor=_RESCALE_FACTOR)
        _write_inp(A, m, str(d / "A.inp"))
        _, mA = estimar(str(d / "A.inp"))
    return A, mA.series


def test_el_encadenado_legitimo_pasa(pre_de_A):
    """El `.inp` reproduce la serie a ~5e-7, que es su precisión de escritura y
    no ruido. Si esto falla, el guardián se ha vuelto inutilizable."""
    A, base = pre_de_A
    _exige_la_misma_serie(A, base, "A.inp", "A.pre")


def test_otra_serie_de_la_misma_longitud_se_rechaza(pre_de_A):
    _, base = pre_de_A
    with pytest.raises(ValueError, match="NO es de esta serie"):
        _exige_la_misma_serie(_serie(9, escala=0.9), base, "B.inp", "A.pre")


def test_el_mensaje_dice_donde_divergen(pre_de_A):
    _, base = pre_de_A
    with pytest.raises(ValueError) as ex:
        _exige_la_misma_serie(_serie(9, escala=0.9), base, "B.inp", "A.pre")
    msg = str(ex.value)
    assert "desde el dato" in msg
    assert "B.inp" in msg and "A.pre" in msg


def test_la_misma_serie_desalineada_se_rechaza(pre_de_A):
    """Igual longitud y frecuencia, arranque distinto: las fechas de las
    intervenciones del `.pre` son índices y apuntarían a otro periodo."""
    _, base = pre_de_A
    with pytest.raises(ValueError, match="desalineadas"):
        _exige_la_misma_serie(_serie(7, start=(2011, 1)), base, "A2.inp", "A.pre")


def test_longitud_distinta_se_sigue_rechazando(pre_de_A):
    _, base = pre_de_A
    with pytest.raises(ValueError, match="Series mismatch"):
        _exige_la_misma_serie(_serie(7, n=100), base, "A3.inp", "A.pre")


def test_una_diferencia_de_redondeo_no_se_rechaza(pre_de_A):
    """El umbral tiene ocho órdenes de margen: 5e-7 legítimo contra 0,115 del
    caso cruzado. No puede confundir un redondeo con otra serie."""
    A, base = pre_de_A
    y = np.asarray(A.data, float) * (1 + 1e-9)
    casi = fue.TimeSeries(y.tolist(), freq=12, start=A.start, name="S")
    _exige_la_misma_serie(casi, base, "A.inp", "A.pre")


def test_el_guardian_se_usa_en_el_camino_recomendado():
    """`base_pre_path` es lo que las instrucciones mandan usar por defecto."""
    from tests._fuente import cuerpo_de
    import art.mcp_server as srv
    ce = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
    src = cuerpo_de(ce)
    assert "_exige_la_misma_serie(ts, ts_b" in src
    assert "ts.nobs != ts_b.nobs or ts.freq != ts_b.freq" not in src


def test_el_defecto_esta_documentado():
    assert os.path.exists("bugs/BUG-0099-repro/repro.py")
