"""BUG-0063 — cada bloque nombra lo que mide.

`guided_identification(pre_path=…)` publica dos cosas con orígenes distintos: la
identificación ARMA, que SÍ va sobre los residuos, y la decisión de la media, que
BUG-0013 puso deliberadamente sobre la serie diferenciada. Compartían etiqueta.
"""
import os
import re
import warnings

import numpy as np
import pytest

R = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/run3/"
PGAS = R + "PGAS/PGAS_m03.pre"
ITCER = R + "ITCER/ITCER_m02.pre"


def _salida(p):
    if not os.path.exists(p):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    import art.mcp_server as M
    f = getattr(M.guided_identification, "fn", M.guided_identification)
    out = f(p, lam=0.0, d=1, D=0, pre_path=p)
    return out[0].text if isinstance(out, list) else str(out)


def _bloque_media(txt):
    i = txt.find("¿Incluir media")
    assert i >= 0, "no está el bloque de la media"
    return txt[i:i + 700]


def _media_publicada(txt):
    mo = re.search(r"μ̄=([-+]?\d+\.\d+)", _bloque_media(txt))
    assert mo
    return float(mo.group(1))


@pytest.mark.parametrize("p", [PGAS, ITCER])
def test_la_cifra_es_la_de_la_serie_diferenciada(p):
    """El número siempre fue el correcto (BUG-0013); se fija para que siga."""
    from art.mcp_server import _load_fitted
    from art.identification import boxcox_transform as bct, apply_differences as adiff
    if not os.path.exists(p):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    ts, _ = _load_fitted(p)
    w = np.array(adiff(bct(ts.data, 0.0), ts.freq, 1, 0))
    assert _media_publicada(_salida(p)) == pytest.approx(w.mean(), abs=1e-3)


@pytest.mark.parametrize("p", [PGAS, ITCER])
def test_la_etiqueta_no_dice_residuos(p):
    assert "Deriva de residuos" not in _bloque_media(_salida(p))


@pytest.mark.parametrize("p", [PGAS, ITCER])
def test_se_explica_por_que_no_son_los_residuos(p):
    b = _bloque_media(_salida(p))
    assert "NO sobre los residuos" in b
    assert "media cero por construcción" in b


def test_el_caso_que_lo_demuestra():
    """ITCER_m02 tiene media residual ~0 PORQUE μ está dentro del modelo."""
    from art.mcp_server import _load_fitted
    if not os.path.exists(ITCER):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    _, m = _load_fitted(ITCER)
    res = np.asarray(m.residuals.data, dtype=float)
    assert abs(res.mean()) < 1e-4, "el caso ya no ilustra nada"
    # y aun así el bloque detecta la deriva
    assert abs(_media_publicada(_salida(ITCER))) > 1e-3


def test_la_identificacion_ARMA_conserva_su_etiqueta():
    """Ésa sí va sobre residuos: el arreglo no puede pasarse de frenada."""
    txt = _salida(ITCER)
    assert "residuos de `ITCER_m02.pre`" in txt


def test_sin_pre_path_no_se_añade_la_nota():
    inp = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/ITCER.inp"
    if not os.path.exists(inp):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    import art.mcp_server as M
    f = getattr(M.guided_identification, "fn", M.guided_identification)
    out = f(inp, lam=0.0, d=1, D=0)
    txt = out[0].text if isinstance(out, list) else str(out)
    assert "NO sobre los residuos" not in txt
