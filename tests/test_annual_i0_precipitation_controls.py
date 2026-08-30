"""Los controles del lado «no debe dispararse»: dos series anuales I(0).

Todo lo añadido a la política en agosto de 2026 empuja en una dirección — la
regla índice fuerza logs, el tope estacional y el límite de un paso bajan `d`, la
regla de la media la enciende. Una regla que sólo se comprueba donde debe actuar
no está comprobada: hace falta el banco donde debe CALLARSE.

Las series de precipitación de `~/Dropbox/Cycles` (proyecto "Joseph's Cycles")
sirven para eso, y para cuatro cosas a la vez:

  * **anuales** (freq=1) — el caso de BUG-0018;
  * **no estacionales** — decisión "A", `n_harmonics=0`;
  * **I(0)** — el ADF rechaza ya en el nivel, así que `d=0` es la respuesta y el
    tope de BUG-0016 no debe convertirlo en 1;
  * **una en niveles y otra en logs** — Ginebra cuenta DÍAS con precipitación, un
    recuento acotado (0–365) con cero y unidad naturales, que quiere λ=1; Zúrich
    mide MILÍMETROS, cantidad positiva sin techo y de variabilidad
    multiplicativa, que quiere λ=0. Ninguna lleva prefijo de índice, así que la
    regla de BUG-0015 tampoco debe tocarlas.

Medido el 12-ago-2026:

    serie             n  inicio    λ  estac  ADF rechaza en  rec_d  decide_d  pipeline
    Ginebra_dias    248    1768  1.0  False       [0, 1, 2]      0         0         0
    Zurich_mm       207    1708  0.0  False       [0, 1, 2]      0         0         0
"""
import os

import pytest

_CYCLES = os.path.expanduser("~/Dropbox/Cycles")
_GENEVA = os.path.join(_CYCLES, "precipitacion_ginebra_1768-1900.csv")
_ZURICH = os.path.join(_CYCLES, "lluvias_zurich_1768-1900.csv")

pytestmark = pytest.mark.skipif(
    not (os.path.exists(_GENEVA) and os.path.exists(_ZURICH)),
    reason="series de precipitación de Cycles no presentes")


def _load(path, name):
    """Lectura a mano: el campo Source lleva comas sin comillas y descuadra a
    pandas ("S:Deluc, Journées_Precipitations_Genève")."""
    import fue
    years, vals = [], []
    for line in open(path, encoding="utf-8", errors="replace").read().splitlines()[1:]:
        parts = line.split(",")
        if len(parts) < 2:
            continue
        try:
            years.append(int(parts[0]))
            vals.append(float(parts[1]))
        except ValueError:
            continue
    return fue.TimeSeries(vals, freq=1, start=(years[0], 1), name=name)


def _geneva():
    return _load(_GENEVA, "Ginebra_dias")


def _zurich():
    return _load(_ZURICH, "Zurich_mm")


# ── I(0): el tope no debe inventar una diferencia ──────────────────────────

@pytest.mark.parametrize("loader", [_geneva, _zurich], ids=["ginebra", "zurich"])
def test_a_stationary_annual_series_keeps_d_zero(loader):
    """El ADF rechaza YA en el nivel. Topar en 1 sería sobrediferenciar por
    prudencia, que es el error opuesto al que BUG-0016 arregló."""
    from art.describe import describe_boxcox, describe_seasonality, describe_unit_root
    from art import policy

    ts = loader()
    lam = policy.decide_lambda(describe_boxcox(ts).data, policy.decide_domain(ts))
    seas = describe_seasonality(ts)
    _D, decision, _nh = policy.decide_seasonal_structure(seas.data, ts.freq)
    urt = describe_unit_root(ts, lam=lam).data

    assert urt["recommended_d"] == 0, "precondición: la evidencia dice I(0)"
    assert policy.decide_d(urt, seasonal=(decision != "A")) == 0


@pytest.mark.parametrize("loader", [_geneva, _zurich], ids=["ginebra", "zurich"])
def test_the_pipeline_agrees_end_to_end(loader):
    import tempfile

    from art.pipeline import run_full

    r = run_full(loader(), os.path.join(tempfile.mkdtemp(), "p.inp"), max_rounds=1)
    assert r.d == 0
    assert r.decision == "A" and r.n_harmonics == 0 and r.D == 0


def test_a_significant_slope_is_not_enough_to_difference_them():
    """El control que decide el criterio de tendencia.

    Las dos series **tienen** tendencia real: Ginebra sube de 121 a 135 días
    entre los primeros y los últimos 50 años, y la pendiente es significativa
    incluso con errores HAC (t = 3.37 y 2.20). Si la regla de «si el gráfico sube
    y el contraste dice d=0, falla el contraste» se hubiera escrito como un
    contraste de pendiente, habría diferenciado estas dos.

    El criterio es cuánto de la serie ES la tendencia — una recta explica 0.076 y
    0.035 de ellas —, que es lo que corresponde a mirar el gráfico. IPC_ES da
    0.910: eso es una serie que sube.
    """
    from art.describe import describe_boxcox, describe_unit_root
    from art import policy

    for loader in (_geneva, _zurich):
        ts = loader()
        lam = policy.decide_lambda(describe_boxcox(ts).data, policy.decide_domain(ts))
        urt = describe_unit_root(ts, lam=lam).data
        assert urt["trend_r2"] < policy.THRESHOLDS["trend_dominates"], ts.name
        assert policy.decide_d(urt) == 0, ts.name


def test_but_a_dominant_trend_does_override_a_d0_recommendation():
    """El otro lado de la misma regla: si el contraste dice d=0 sobre una serie
    cuyo gráfico sube, el que falla es el contraste."""
    from art import policy

    assert policy.decide_d({"recommended_d": 0, "trend_r2": 0.91}) == 1
    assert policy.decide_d({"recommended_d": 0, "trend_r2": 0.076}) == 0
    assert policy.decide_d({"recommended_d": 0}) == 0      # sin evidencia, nada


# ── λ en las dos direcciones ───────────────────────────────────────────────

def test_a_bounded_count_stays_in_levels():
    """Días con precipitación: acotado en [0, 365], con cero y unidad naturales.
    No es un índice, así que la regla de BUG-0015 no debe forzarlo a logs."""
    from art.describe import describe_boxcox
    from art import policy

    ts = _geneva()
    assert policy.decide_domain(ts) == "generic"
    assert policy.decide_lambda(describe_boxcox(ts).data, policy.decide_domain(ts)) == 1.0


def test_an_unbounded_positive_quantity_goes_to_logs():
    """Milímetros de lluvia: positivo, sin techo, variabilidad multiplicativa.

    Este test fijaba `decide_domain(ts) == "generic"`, que era lo que devolvía la
    taxonomía binaria — pero su propio nombre y su propia descripción dicen
    «cantidad positiva sin techo, variabilidad multiplicativa», que es justo la
    categoría que faltaba (BUG-0040). Zúrich va de 626 a 1988 mm, un factor de
    3.17: es multiplicativa por la misma definición que el test enunciaba.

    Lo que NO cambia es λ, y ésa es la propiedad que importa: `gap = +0.429` está
    muy fuera de la banda en que el estadístico no discrimina, así que aquí
    decide el dato y el dominio no interviene. El dominio sólo manda donde el
    estadístico calla.
    """
    from art.describe import describe_boxcox
    from art import policy

    ts = _zurich()
    assert policy.decide_domain(ts) == "multiplicative"
    bc = describe_boxcox(ts).data
    assert abs(bc["gap"]) >= policy.BANDA_AMBIGUA_BOXCOX, (
        "el testigo dejó de valer: si el gap entrara en la banda, este caso ya "
        "no probaría que decide el DATO")
    assert policy.decide_lambda(bc, policy.decide_domain(ts)) == 0.0


def test_the_pair_disagrees_on_lambda_which_is_the_point():
    """Dos series del mismo fenómeno, la misma frecuencia y la misma época, y la
    transformación correcta es distinta. Si un cambio futuro las iguala, ha roto
    algo aunque las baterías pasen.

    Sobrevivió intacto a BUG-0040 —que cambió la taxonomía de dominio— y merece
    decirse por qué: los dos `gap` (−0.318 y +0.429) están lejos de la banda
    ambigua, así que en ambas series decide el dato. Un cambio en la regla del
    dominio que rompiera ESTE par estaría haciendo del dominio un decreto, que es
    exactamente lo que no debe ser.
    """
    import tempfile

    from art.pipeline import run_full

    d = tempfile.mkdtemp()
    lam_g = run_full(_geneva(), os.path.join(d, "g.inp"), max_rounds=1).lam
    lam_z = run_full(_zurich(), os.path.join(d, "z.inp"), max_rounds=1).lam
    assert (lam_g, lam_z) == (1.0, 0.0)
