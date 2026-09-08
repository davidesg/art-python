"""La etiqueta de un factor de frecuencia fija ES su frecuencia (BUG-0115).

`_build_param_labels` las construía con el índice de `enumerate`, y con un solo
factor —el caso normal tras `meg_reformulate`— ese índice vale 0: el testigo
MA_f de **f=3** se etiquetaba **`MA_f(f=0)`**.

No es cosmético. La frecuencia es lo único que identifica al factor, y f=0
significa otra cosa —la frecuencia cero, la tendencia—, así que la etiqueta no
sólo era inútil: nombraba un objeto distinto del que estaba midiendo.
"""
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.diagnosis import _build_param_labels


def _serie():
    rng = np.random.default_rng(3)
    y = 100.0 + np.cumsum(rng.standard_normal(200) * 0.3)
    return fue.TimeSeries(y.tolist(), freq=12, start=(2005, 1), name="X")


def _de_frecuencia_fija(m):
    return [l for l in _build_param_labels(m) if "_f(" in l]


def test_un_solo_factor_no_se_etiqueta_f0():
    """El caso del informe, y el más frecuente: tras `meg_reformulate` hay UN
    testigo, así que el índice es 0 y la etiqueta salía siempre `f=0`."""
    m = fue.Model(_serie(), d=1, mu=0.0, estimate_mu=False, refactor=100.0,
                  ma_f=[fue.FixedFreqFactor(freq=3, coef=-0.5, free=True)])
    assert _de_frecuencia_fija(m) == ["MA_f(f=3)"]


def test_con_varios_factores_cada_uno_lleva_LA_SUYA():
    """Con varios, el índice acertaría por casualidad en el segundo si las
    frecuencias fuesen 0,1,2… Aquí no lo son, así que la prueba discrimina."""
    m = fue.Model(_serie(), d=1, mu=0.0, estimate_mu=False, refactor=100.0,
                  ar_f=[fue.FixedFreqFactor(freq=4, coef=-0.5, free=True),
                        fue.FixedFreqFactor(freq=2, coef=-0.5, free=True)],
                  ma_f=[fue.FixedFreqFactor(freq=5, coef=-0.5, free=True)])
    assert _de_frecuencia_fija(m) == ["AR_f(f=4)", "AR_f(f=2)", "MA_f(f=5)"]


def test_un_factor_FIJO_no_aparece():
    """Sólo se etiquetan los coeficientes libres: los fijos no se estiman y no
    ocupan sitio en el vector de parámetros."""
    m = fue.Model(_serie(), d=1, mu=0.0, estimate_mu=False, refactor=100.0,
                  ar_f=[fue.FixedFreqFactor(freq=4, coef=-0.5, free=False),
                        fue.FixedFreqFactor(freq=2, coef=-0.5, free=True)])
    assert _de_frecuencia_fija(m) == ["AR_f(f=2)"]


def test_la_etiqueta_no_usa_el_indice():
    """Lo que cierra la clase: que no vuelva a construirse con `enumerate`."""
    from tests._fuente import fuente_de
    src = "\n".join(l.split("#", 1)[0]
                    for l in fuente_de(_build_param_labels).splitlines())
    assert "enumerate(model.ar_f" not in src
    assert "enumerate(model.ma_f" not in src
    assert "ff.freq" in src
