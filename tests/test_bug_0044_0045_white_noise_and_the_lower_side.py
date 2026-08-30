"""BUG-0044 y BUG-0045 — dos huecos que dejaban al analista sin la respuesta
correcta en la papeleta. Los encontró el experimento del chat limpio.

**BUG-0044.** La lista de identificación imprimía la regla «Sin estructura →
p=0, q=0» y luego nunca ofrecía ese candidato: estaba excluido por
`if p == 0 and q == 0 and P == 0 and Q == 0: continue`. Y al admitirlo apareció
lo de fondo: `_parsimony_score` empezaba con `if total == 0: return 0.0` — la
función de PARSIMONIA daba la peor nota al modelo más parsimonioso. Era una rama
«esto no puede pasar» que, quitada la exclusión, se convirtió en el ranking.

Medido sobre los residuos del ITCER con su intervención puesta: la similitud
CRUDA del ruido blanco es 0.9197, la más alta de las ocho candidatas (mejor
rival 0.8575), y salía último con 0.0000. Con cero retardos fuera de banda era la
respuesta correcta.

**BUG-0045.** El par confirmatorio en f=0 miraba entero hacia arriba: Shin-Fuller
contrasta si hace falta MÁS diferenciación y `dcd_overdiff_regular` impone una
EXTRA. Ninguno preguntaba si con `d−1` habría bastado — justo la duda cuando la
tabla ADF/KPSS recomienda una d menor que la adoptada. Sobre PGAS la etapa formal
concluía «el orden de integración no está en la banda ambigua», una afirmación
más fuerte de lo que los dos contrastes sostenían.
"""
import numpy as np
import pytest

import fue
from art.model_detection import _parsimony_score, suggest_orders
from art.formal_tests import dcd_overdiff_regular, dcd_underdiff_regular
from art.pipeline import _load_fitted, _write_inp

from datos_replica import REPLICA, REPLICA_DS, requiere_replica



# ── BUG-0044 ────────────────────────────────────────────────────────────────

def test_the_parsimony_score_does_not_punish_zero_parameters():
    """La función de parsimonia no puede dar cero al más parsimonioso."""
    from art.model_detection import _pattern_features
    emp = _pattern_features(np.zeros(13), np.zeros(13), 4, 83)
    assert _parsimony_score(0.92, 0, 0, 0, 0, emp, 4) > 0.9
    # y no queda por debajo de un candidato con parámetros y la misma similitud
    assert (_parsimony_score(0.92, 0, 0, 0, 0, emp, 4)
            > _parsimony_score(0.92, 1, 0, 0, 0, emp, 4))
    # ni por debajo de cero, que era el defecto
    assert _parsimony_score(0.10, 0, 0, 0, 0, emp, 4) > 0.0


@requiere_replica
def test_white_noise_wins_when_there_is_nothing_to_model():
    """Testigo real: residuos del ITCER con la intervención, cero retardos fuera
    de banda."""
    import os
    ruta = (REPLICA + "autonomo2/"
            "ITCER/ITCER_m10.pre")
    if not os.path.exists(ruta):
        pytest.skip("el testigo de la réplica no está en esta máquina")
    _ts, m = _load_fitted(ruta)
    top = suggest_orders(m.residuals, d=0, D=0, lam=1.0, top_n=5)
    p, q, P, Q = top[0].p, top[0].q, top[0].P, top[0].Q
    assert (p, q, P, Q) == (0, 0, 0, 0), (
        f"con la ACF entera dentro de banda el candidato en cabeza es "
        f"({p},{q},{P},{Q})")


def test_white_noise_does_not_win_when_there_IS_structure():
    """La otra cara, y la que importa: admitirlo no puede hacerlo ganar siempre."""
    rng = np.random.default_rng(4)
    w = np.zeros(200)
    for t in range(1, 200):
        w[t] = 0.7 * w[t - 1] + rng.standard_normal()
    ts = fue.TimeSeries((100 + np.cumsum(w)).tolist(), freq=4,
                        start=(2000, 1), name="CONAR")
    top = suggest_orders(ts, d=1, D=0, lam=1.0, top_n=5)
    assert (top[0].p, top[0].q) != (0, 0), (
        "el ruido blanco no puede encabezar una serie con autocorrelación clara")


def test_zero_parameters_has_no_special_case():
    """La fórmula general trata bien el caso, y ésa es la corrección.

    Los dos intentos anteriores fallaron por lados opuestos, y el caso dorado del
    proyecto cazó el primero: sin penalización y CON bonificación, el ruido
    blanco ganaba al MA(1) pese a tener peor similitud cruda (0.7880 contra
    0.8173) y empeoraba el AIC del modelo autónomo en 10 puntos; sin penalización
    y SIN bonificación, perdía a igual similitud cruda, que es parsimonia al
    revés. Sin caso especial no ocurre ninguna de las dos cosas.
    """
    from art.model_detection import _pattern_features
    emp = _pattern_features(np.zeros(13), np.zeros(13), 12, 180)
    # a igual forma, menos parámetros gana
    assert (_parsimony_score(0.92, 0, 0, 0, 0, emp, 12)
            > _parsimony_score(0.92, 1, 0, 0, 0, emp, 12))
    # pero una forma claramente mejor gana igualmente, aunque cueste un parámetro
    assert (_parsimony_score(0.8173, 1, 0, 0, 0, emp, 12)
            > _parsimony_score(0.7880, 0, 0, 0, 0, emp, 12))


def test_the_golden_case_still_prefers_the_MA1():
    """El caso dorado del proyecto es el testigo de que admitir el ruido blanco
    no puede volcar una serie que SÍ tiene estructura."""
    import json
    import os
    ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "tests", "golden", "synth_b1_series.json")
    if not os.path.exists(ruta):
        pytest.skip("la serie dorada no está")
    with open(ruta) as fh:
        d = json.load(fh)
    ts = fue.TimeSeries(d["data"], freq=d["freq"], start=tuple(d["start"]),
                        name=d["name"])
    top = suggest_orders(ts, d=1, D=0, lam=1.0, top_n=3)
    assert (top[0].p, top[0].q, top[0].P, top[0].Q) == (0, 1, 0, 0)


def test_the_white_noise_candidate_is_generated_at_all():
    rng = np.random.default_rng(9)
    ts = fue.TimeSeries((100 + np.cumsum(rng.standard_normal(120))).tolist(),
                        freq=4, start=(2000, 1), name="RW")
    todos = suggest_orders(ts, d=1, D=0, lam=1.0, top_n=99)
    assert any((c.p, c.q, c.P, c.Q) == (0, 0, 0, 0) for c in todos)


# ── BUG-0045 ────────────────────────────────────────────────────────────────

def _modelo(ts, tmp_path, nombre, **kw):
    ruta = str(tmp_path / f"{nombre}.inp")
    m = fue.Model(ts, boxlam=1.0, **kw)
    _write_inp(ts, m, ruta)
    _, mf = _load_fitted(ruta)
    return mf


def test_a_model_without_a_regular_MA_still_gets_the_lower_side(tmp_path):
    """El hueco exacto: un AR puro no tenía MA que contrastar, así que no había
    forma de preguntar si la ∇ sobraba."""
    rng = np.random.default_rng(2)
    w = np.zeros(150)
    for t in range(2, 150):
        w[t] = 0.6 * w[t - 1] - 0.2 * w[t - 2] + rng.standard_normal()
    ts = fue.TimeSeries((100 + np.cumsum(w)).tolist(), freq=4,
                        start=(2000, 1), name="AR2")
    m = _modelo(ts, tmp_path, "ar2", d=1, ar=[[0.5, -0.2]],
                ar_free=[[True, True]], mu=0.0, estimate_mu=False)
    assert not m.ma, "el testigo debe no tener MA regular"
    r = dcd_underdiff_regular(m)
    assert r is not None
    assert r.lr >= r._crit["5%"], "una ∇ genuina no debe salir cancelada"


def test_an_over_differenced_series_is_caught_from_below(tmp_path):
    """Ruido blanco diferenciado de más: el testigo debe apilarse en +1.

    Se mide sobre VARIAS realizaciones y no sobre una. El contraste tiene tamaño
    5% —rechaza la nula una de cada veinte veces aunque sea cierta— y la
    probabilidad de apilamiento de la ley s=1 es 0.6575, no 1: una sola
    realización puede dar θ̂=0.96 sin que nada esté mal, y de hecho la primera
    semilla que probé lo hizo. Un test de una extracción sobre un estadístico con
    apilamiento mide la suerte, no el código.
    """
    apilados, rechazos, n = 0, 0, 12
    for seed in range(n):
        rng = np.random.default_rng(seed)
        ts = fue.TimeSeries((50.0 + rng.standard_normal(200)).tolist(),
                            freq=4, start=(2000, 1), name="WN")
        m = _modelo(ts, tmp_path, f"wn{seed}", d=1, ar=[[0.0]],
                    ar_free=[[False]], mu=0.0, estimate_mu=False)
        r = dcd_underdiff_regular(m)
        assert r is not None
        if r.coef_free > 0.999:
            apilados += 1
        if r.lr >= r._crit["5%"]:
            rechazos += 1

    # Apilamiento: la ley da 0.6575 asintótico; se exige holgadamente la mayoría.
    assert apilados >= n // 2, (
        f"sólo {apilados}/{n} testigos se apilaron en +1 sobre series que SÍ "
        "están diferenciadas de más")
    # Tamaño: rechazar la cancelación cuando la ∇ sobra es el error de tipo I.
    assert rechazos <= max(2, n // 4), (
        f"{rechazos}/{n} rechazos sobre la nula — el tamaño se ha ido")


def test_with_d_zero_there_is_no_difference_to_question(tmp_path):
    rng = np.random.default_rng(8)
    ts = fue.TimeSeries((50 + rng.standard_normal(120)).tolist(), freq=4,
                        start=(2000, 1), name="WN0")
    m = _modelo(ts, tmp_path, "wn0", d=0, ma=[[0.0]], ma_free=[[True]],
                mu=0.0, estimate_mu=False)
    assert dcd_underdiff_regular(m) is None


@requiere_replica
def test_the_report_bounds_the_order_from_both_sides():
    """La frase «no está en la banda ambigua» necesitaba los dos lados."""
    import os
    from art.describe import describe_formal_tests
    ruta = (REPLICA + "autonomo2/"
            "PGAS/PGAS_m20.inp")
    if not os.path.exists(ruta):
        pytest.skip("el testigo de la réplica no está en esta máquina")
    _ts, m = fue.load(ruta)
    m.fit()
    txt = describe_formal_tests(m).summary
    assert "sub-diferenciación" in txt
    assert "acotado por ABAJO" in txt or "por ABAJO no cierra" in txt
