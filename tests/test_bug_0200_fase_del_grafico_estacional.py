"""BUG-0200 — el gráfico estacional rotulaba la primera barra como enero.

`detect_seasonality` devolvía los efectos en el orden de la MUESTRA (el
primero, el del periodo en que empieza la serie) y `plot_seasonality` los
rotulaba Jan…Dec. En el IPC español, que empieza en febrero, cada barra estaba
desplazada un mes.

Los efectos son los del NIVEL (100·ln y), estimados sobre ∇^d. No son las
medias de ∇ por mes; las diferencias entre meses consecutivos sí lo son.
"""

import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")

from art.seasonal_detection import detect_seasonality, plot_seasonality

# Un patrón de nivel conocido, en orden de calendario Jan..Dec, suma cero.
PATRON = np.array([-3.0, -2.0, 0.5, 1.5, 2.0, 2.5, -1.0, -0.5, 0.0, 1.0, 1.5, -2.5])


def _serie(mes_inicio, d=1, n=240, seed=7):
    rng = np.random.default_rng(seed)
    meses = (mes_inicio - 1 + np.arange(n)) % 12
    nivel = PATRON[meses] + 0.2 * np.arange(n) / 12
    if d == 1:
        nivel = nivel + np.cumsum(rng.standard_normal(n) * 0.05)
    else:
        nivel = nivel + rng.standard_normal(n) * 0.05
    y = np.exp((460.0 + nivel) / 100.0)
    return fue.TimeSeries(y.tolist(), freq=12, start=(2002, mes_inicio), name="S")


@pytest.mark.parametrize("mes_inicio", [1, 2, 7, 12])
@pytest.mark.parametrize("d", [0, 1])
def test_los_efectos_van_en_ORDEN_DE_CALENDARIO(mes_inicio, d):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = detect_seasonality(_serie(mes_inicio, d), d=d, lam=0.0)
    np.testing.assert_allclose(r.dummies, PATRON, atol=0.15)


def test_el_caso_del_informe_empieza_en_febrero():
    """Con el orden de la muestra, la barra «Jan» era la de febrero (−2.0)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = detect_seasonality(_serie(2), d=1, lam=0.0)
    assert r.dummies[0] == pytest.approx(-3.0, abs=0.15)
    assert r.dummies[1] == pytest.approx(-2.0, abs=0.15)


def test_el_titulo_dice_que_es_el_efecto_sobre_el_NIVEL():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = detect_seasonality(_serie(2), d=1, lam=0.0)
        fig = plot_seasonality(r)
    assert "level" in fig.axes[0].get_title()
