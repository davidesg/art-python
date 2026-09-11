"""BUG-0166 — la Q restaba TODOS los parámetros de sus grados de libertad.

Ljung-Box corrige `df = m − p − q`: los parámetros **ARMA**, que son los que se
estiman a partir de la autocorrelación de los residuos. Los DETERMINISTAS
—armónicos, intervenciones, media— no entran.

art restaba `npar`, que son todos. Un modelo con 11 armónicos restaba 11; con 20
intervenciones, 20 más. **El df se iba a cero y por debajo, y un df negativo no
daba error: daba un p-valor.**

Es el veredicto primario de adecuación —de él dependen `white_noise`, el
`q_pass` de la escalera y el `residuals_ok` de los contrastes formales— y el
daño se COMPONE: se lee «no es ruido blanco», se añade una intervención, `npar`
sube, el df baja y el rechazo se refuerza. Empuja hacia la sobreparametrización
que el método existe para evitar.

Lo encontró el analista en la corrida real: *«el estadístico Q en el gráfico de
art no calcula correctamente los grados de libertad»*.
"""
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.diagnosis import diagnose
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar


def _modelo(n_armonicos=5, n_itv=0, con_ar=True, n=292, seed=3):
    """RUIDO BLANCO con el paquete determinista que se quiera encima.

    Los residuos son ruido blanco por construcción, así que la Q **tiene que
    pasar** por muchos deterministas que lleve el modelo. Ésa es la propiedad.
    """
    rng = np.random.default_rng(seed)
    y = 100.0 + np.cumsum(rng.standard_normal(n) * 0.5)
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2002, 1), name="Q")
    itvs = []
    for k in range(1, n_armonicos + 1):
        itvs.append(fue.Intervention("cos", at=0, omega=[0.0],
                                     omega_free=[True], harmonic=float(k)))
        itvs.append(fue.Intervention("sin", at=0, omega=[0.0],
                                     omega_free=[True], harmonic=float(k)))
    for j in range(n_itv):
        itvs.append(fue.Intervention("step", at=40 + 3 * j, omega=[0.0],
                                     omega_free=[True]))
    kw = dict(ar=[[0.0]], ar_free=[[True]]) if con_ar else {}
    return fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                     refactor=_RESCALE_FACTOR, interventions=itvs, **kw)


def _ajusta(m, tmp_path, nom="Q"):
    f = str(tmp_path / f"{nom}.inp")
    _write_inp(m.series, m, f)
    return estimar(f)[1]


# ── la propiedad: los deterministas no gastan grados de libertad ────────────

@pytest.mark.parametrize("n_armonicos,n_itv", [(5, 0), (5, 8), (6, 14)])
def test_el_ruido_blanco_PASA_por_muchos_deterministas_que_haya(
        n_armonicos, n_itv, tmp_path):
    """Antes: con 13 parámetros el ruido blanco ya se rechazaba, y con 39 el df
    valía 0. La adecuación de los residuos no puede depender de cuántos
    armónicos lleve el modelo."""
    m = _ajusta(_modelo(n_armonicos, n_itv), tmp_path, f"a{n_armonicos}_{n_itv}")
    d = diagnose(m)
    assert d.white_noise, (
        f"ruido blanco rechazado con npar={m._result.npar}: "
        f"p={[round(p, 4) for p in d.q_pvalues]}")


def test_los_df_se_restan_de_los_ARMA_y_de_nada_mas(tmp_path):
    """La comprobación directa: el p-valor que art publica tiene que ser el de
    `df = m − (p+q+P+Q)`, no el de `m − npar`."""
    from fue.diagnostics import ljung_box as lb
    m = _ajusta(_modelo(5, 6), tmp_path, "df")
    d = diagnose(m)
    r = np.asarray(m._result.residuals, dtype=float)
    arma = (sum(len(f) for f in (m.ar or [])) + sum(len(f) for f in (m.ma or []))
            + sum(len(f) for f in (m.ar_s or []))
            + sum(len(f) for f in (m.ma_s or [])))
    assert arma < int(m._result.npar), "el testigo no separa ARMA de npar"
    for L, p_art in zip(d.q_lags, d.q_pvalues):
        esperado = lb(r, lags=L, df_correction=arma)["pvalue"][0]
        malo = lb(r, lags=L, df_correction=int(m._result.npar))["pvalue"][0]
        assert abs(p_art - esperado) < 1e-9, f"lag {L}: {p_art} ≠ {esperado}"
        if abs(esperado - malo) > 1e-6:
            assert abs(p_art - malo) > 1e-9, f"lag {L}: sigue usando npar"


def test_un_df_no_POSITIVO_no_publica_un_p_valor(tmp_path):
    """Un df ≤ 0 no es un contraste flojo: es que no hay contraste. Antes daba
    p=3,7e-10 sin pestañear, y sobre `ES_CPI_m10` el retardo 12 salía con df=−1
    y p=0,0033 contra el 0,658 correcto."""
    m = _ajusta(_modelo(6, 14), tmp_path, "neg")
    d = diagnose(m)
    arma = sum(len(f) for f in (m.ar or [])) + sum(len(f) for f in (m.ma or []))
    for L in d.q_lags:
        assert L - arma >= 1, f"lag {L} con df={L - arma}: no es un contraste"
    assert all(0.0 <= p <= 1.0 for p in d.q_pvalues)


# ── y lo que NO puede cambiar ──────────────────────────────────────────────

def test_los_retardos_siguen_siendo_la_CONVENCION_DEL_MOTOR(tmp_path):
    """El cancerbero es `3f+3` —la longitud del correlograma de `diagnose.c`— y
    ahí es donde se decide si se pasa a los contrastes formales. El arreglo
    toca los grados de libertad, no dónde se mira."""
    m = _ajusta(_modelo(5, 0), tmp_path, "lags")
    d = diagnose(m)
    s = 12
    assert d.q_lags == [s, 2 * s, 3 * s, 3 * s + 3]


def test_un_modelo_que_de_VERDAD_falla_sigue_fallando(tmp_path):
    """El arreglo no puede volver ciega la Q: sube el p-valor de todo el mundo,
    y hay que comprobar que lo que debe rechazarse se sigue rechazando."""
    rng = np.random.default_rng(5)
    n = 292
    e = rng.standard_normal(n) * 0.5
    for t in range(1, n):                       # AR(1) fuerte SIN modelizar
        e[t] += 0.75 * e[t - 1]
    ts = fue.TimeSeries((100.0 + np.cumsum(e)).tolist(), freq=12,
                        start=(2002, 1), name="MAL")
    f = str(tmp_path / "MAL.inp")
    _write_inp(ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                             refactor=_RESCALE_FACTOR), f)
    d = diagnose(estimar(f)[1])
    assert not d.white_noise, "la Q dejó de ver una autocorrelación evidente"


# ═══════ EL CANCERBERO — decisión del analista, 11-sep-2026 ═══════════════
#
# «Lags es arbitrario y por defecto está lags=3*f+3. Ese es cancerbero […] es el
# que decide si cancerbero lo deja pasar a formal tests o no. O si lo hace, lo
# hace con esta salvedad de forma consciente.»
#
# Antes `white_noise` era `all(p > 0.05)` sobre los cuatro retardos: una regla
# MÁS ESTRICTA que la del método, y que nadie había decidido. Cualquiera de los
# cuatro bloqueaba.

def _testigo_con_salvedad(tmp_path):
    """Un MA(1) DÉBIL sin modelizar: muerde en el retardo 12 y se diluye en 39."""
    rng = np.random.default_rng(1)
    n = 292
    a = rng.standard_normal(n) * 0.5
    e = np.zeros(n)
    for t in range(1, n):
        e[t] = a[t] + 0.28 * a[t - 1]
    ts = fue.TimeSeries((100.0 + np.cumsum(e)).tolist(), freq=12,
                        start=(2002, 1), name="SALV")
    f = str(tmp_path / "SALV.inp")
    _write_inp(ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                             refactor=_RESCALE_FACTOR), f)
    return estimar(f)[1]


def test_decide_el_3f_mas_3_y_no_los_cuatro(tmp_path):
    d = diagnose(_testigo_con_salvedad(tmp_path))
    assert d.q_lag_cancerbero == 39, "el cancerbero no es 3f+3"
    assert d.q_p_cancerbero > 0.05
    assert d.white_noise, "un retardo bajo sigue bloqueando el veredicto"
    # y los que rechazan NO se tiran
    assert [l for l, _ in d.salvedades_q] == [12, 24]


def test_la_salvedad_se_DICE(tmp_path):
    """Pasar «con salvedad» tiene que ser consciente. Si no se dice, el analista
    no distingue un modelo limpio de uno que pasa por dónde se mira."""
    from art.describe import describe_diagnosis
    txt = describe_diagnosis(_testigo_con_salvedad(tmp_path)).summary
    assert "decide 3f+3" in txt
    assert "Salvedad" in txt and "lag 12" in txt
    assert "Seguir es legítimo; seguir sin saberlo, no" in txt


def test_sin_salvedades_no_se_dice_nada(tmp_path):
    """El aviso sólo sale cuando hay algo que advertir: si no, es ruido."""
    from art.describe import describe_diagnosis
    m = _ajusta(_modelo(5, 0), tmp_path, "limpio")
    d = diagnose(m)
    assert d.salvedades_q == []
    assert "Salvedad" not in describe_diagnosis(m).summary


def test_si_el_cancerbero_RECHAZA_el_veredicto_es_no(tmp_path):
    """La otra mitad: que decida el 3f+3 no lo vuelve permisivo."""
    rng = np.random.default_rng(5)
    n = 292
    e = rng.standard_normal(n) * 0.5
    for t in range(1, n):
        e[t] += 0.75 * e[t - 1]
    ts = fue.TimeSeries((100.0 + np.cumsum(e)).tolist(), freq=12,
                        start=(2002, 1), name="NO")
    f = str(tmp_path / "NO.inp")
    _write_inp(ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                             refactor=_RESCALE_FACTOR), f)
    d = diagnose(estimar(f)[1])
    assert d.q_p_cancerbero <= 0.05
    assert not d.white_noise


def test_la_tabla_marca_quien_decide(tmp_path):
    """`summary()` imprimía cuatro líneas iguales, y se leían como cuatro
    veredictos."""
    t = diagnose(_testigo_con_salvedad(tmp_path)).summary()
    assert "<- DECIDE (3f+3)" in t
    assert "(salvedad)" in t
