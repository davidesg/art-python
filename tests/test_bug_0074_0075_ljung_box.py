"""BUG-0074 y BUG-0075 — dónde se evalúa el Ljung-Box y con cuántos df.

Los dos salieron del run 5 guiado sobre PGAS, y juntos invirtieron un veredicto:
la especificación simplificada de la intervención se descartaba por inadecuada
con Q(2) y es la mejor de las dos a la convención.

  0074  la etiqueta del gráfico imprimía el número de RETARDOS donde van los
        GRADOS DE LIBERTAD — no restaba los parámetros ARMA.
  0075  el conjunto de retardos empezaba en s//2 (1 g.l. tras corregir, y el
        que decidía por ser `min(q_pvalues)`) y no llegaba a f·3+3.

El árbitro de los dos es el `.out` del motor en C, que ya lo hacía bien.
"""
import numpy as np
import pytest

fue = pytest.importorskip("fue")
from art.diagnosis import diagnose
from art.identification import compute_stats


def _modelo(freq=4, n=120, semilla=3, p=1):
    rng = np.random.default_rng(semilla)
    y = np.cumsum(rng.standard_normal(n))
    ts = fue.TimeSeries(y.tolist(), freq=freq, start=(2000, 1), name="S")
    kw = dict(d=1, mu=0.0, estimate_mu=False)
    if p:
        kw.update(ar=[[0.3] * p], ar_free=[[True] * p])
    m = fue.Model(ts, **kw)
    m.fit()
    return m


# ───────────────── BUG-0075: dónde se evalúa ─────────────────

def test_trimestral_llega_a_f_por_3_mas_3():
    dg = diagnose(_modelo(freq=4))
    assert dg.q_lags[-1] == 15, "f·3+3 = 15 para trimestral"
    assert dg.q_lags == [4, 8, 12, 15]


def test_mensual_llega_a_f_por_3_mas_3():
    dg = diagnose(_modelo(freq=12, n=240))
    assert dg.q_lags[-1] == 39, "f·3+3 = 39 para mensual"
    assert dg.q_lags == [12, 24, 36, 39]


def test_sin_estacionalidad_el_punto_de_decision_es_9():
    """9 es la convención del motor: `_default_lags_fug` la devuelve para
    freq=1 porque es lo que hace `diagnose.c` de `fug`. Lo que importa en un
    Portmanteau no es el retardo exacto sino que Python y el motor decidan en
    el mismo sitio."""
    assert diagnose(_modelo(freq=1, n=120)).q_lags == [5, 9]
    assert diagnose(_modelo(freq=1, n=260)).q_lags == [5, 9], \
        "9 fijo, no dependiente del largo del correlograma"


def test_el_retardo_s_medios_ya_no_esta():
    """s//2 son 2 retardos en trimestral: 1 grado de libertad tras restar un
    parámetro ARMA, y era el que decidía por ser el mínimo p-valor."""
    dg = diagnose(_modelo(freq=4))
    assert 2 not in dg.q_lags


def test_los_retardos_coinciden_con_los_del_motor():
    """El `.out` de `fue` reporta el Ljung-Box en {s, 2s, 3s, 3s+3}. Que la
    diagnosis de Python evaluara en OTROS sitios era el defecto de fondo."""
    m = _modelo(freq=4)
    dg = diagnose(m)
    s = m.series.freq
    assert dg.q_lags == [s, 2 * s, 3 * s, 3 * s + 3]


def test_una_serie_corta_no_se_queda_sin_retardos():
    dg = diagnose(_modelo(freq=4, n=30))
    assert dg.q_lags, "siempre tiene que quedar al menos uno"


# ───────────────── BUG-0074: con cuántos grados de libertad ─────────────────

def test_la_etiqueta_resta_los_parametros_arma():
    r = np.random.default_rng(1).standard_normal(120)
    st = compute_stats(r, lags=15, npar=1)
    assert st.ljung_box_df == 14, "15 retardos − 1 parámetro ARMA"


def test_sin_modelo_no_hay_nada_que_restar():
    r = np.random.default_rng(1).standard_normal(120)
    st = compute_stats(r, lags=15)
    assert st.ljung_box_df == 15, "una serie cruda: retardos y df coinciden"


def test_los_df_no_bajan_de_uno():
    r = np.random.default_rng(1).standard_normal(60)
    st = compute_stats(r, lags=3, npar=8)
    assert st.ljung_box_df >= 1


@pytest.mark.parametrize("npar", [1, 2, 3])
def test_la_etiqueta_coincide_con_los_df_de_la_diagnosis(npar):
    r = np.random.default_rng(2).standard_normal(120)
    st = compute_stats(r, lags=15, npar=npar)
    assert st.ljung_box_df == 15 - npar


# ───────────── lo que los dos juntos costaban ─────────────

def test_el_veredicto_de_ruido_blanco_no_lo_decide_un_grado_de_libertad():
    """`min(q_pvalues)` sobre un conjunto que empieza en s//2 hacía que el
    punto de 1 g.l. decidiera la adecuación de casi todos los modelos."""
    dg = diagnose(_modelo(freq=4))
    df_min = min(l - dg.npar for l in dg.q_lags)
    assert df_min >= 3, ("el punto más frágil del conjunto debe tener margen; "
                         f"tiene {df_min} g.l.")
