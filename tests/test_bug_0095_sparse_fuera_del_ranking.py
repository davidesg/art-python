"""BUG-0095 — los candidatos «sólo en B^k» iban en el ranking de identificación.

Un «AR sólo en B^k» impone φ₁=…=φₖ₋₁=0 **antes de estimar nada**. Eso no es un
orden: es una restricción de identificación, y la práctica Box-Jenkins estima el
polinomio COMPLETO y reserva las restricciones —frecuencia fija, ceros
intermedios— al análisis de raíces a posteriori (`ar_factorization`), donde la
estructura se DESCUBRE en vez de imponerse.

Y no es purismo. El significado de la forma dispersa **depende del signo del
coeficiente que aún no se ha estimado**. Para (1 − θB²) en datos mensuales:

    θ < 0  →  raíces imaginarias puras, ω = π/2, periodo 4  →  la frecuencia f=3
    θ > 0  →  dos raíces reales; ninguna frecuencia fija

La misma restricción es un factor estacional o no lo es según un signo. Y fue
tiene operadores AR(2)/MA(2) de frecuencia fija para expresarlo bien, una vez
que se sabe.

**No se eliminan**: son plausibles y a veces son la respuesta. Se sacan del
ranking y se ofrecen aparte, marcados.
"""
import math

import numpy as np
import pytest

fue = pytest.importorskip("fue")

from art.model_detection import suggest_orders


def _disperso(sp):
    return bool(getattr(sp, "sparse_ar_lag", 0)
                or getattr(sp, "sparse_ma_lag", 0))


@pytest.fixture(scope="module")
def serie():
    rng = np.random.default_rng(4)
    y = np.cumsum(rng.standard_normal(180) * 0.4) + 100.0
    return fue.TimeSeries(y.tolist(), freq=12, start=(2000, 1), name="X95")


# ───────────── la aritmética que justifica la regla ─────────────

def test_el_signo_decide_lo_que_ES_la_restriccion():
    """(1 − θB²): con θ<0 es la frecuencia π/2 (periodo 4, f=3 en mensual);
    con θ>0 son dos raíces reales y no hay frecuencia ninguna."""
    def frec(theta):
        r = np.roots([-theta, 0.0, 1.0])[0]
        return abs(math.atan2(r.imag, r.real))

    assert abs(frec(-0.6) - math.pi / 2) < 1e-9
    assert abs(2 * math.pi / frec(-0.6) - 4.0) < 1e-9      # periodo 4
    assert frec(0.5) < 1e-9                                # raíces reales


def test_periodo_4_es_la_frecuencia_3_en_mensual():
    assert abs(2 * math.pi / (math.pi * 3 / 6) - 4.0) < 1e-9


# ───────────── el ranking ─────────────

def test_el_ranking_no_lleva_dispersos(serie):
    for sp in suggest_orders(serie, d=1, D=0, lam=0.0, top_n=8):
        assert not _disperso(sp), f"{sp} entró en el ranking"


def test_pero_siguen_existiendo_si_se_piden(serie):
    """No se eliminan: son plausibles."""
    con = suggest_orders(serie, d=1, D=0, lam=0.0, top_n=8,
                         incluir_dispersos=True)
    assert any(_disperso(sp) for sp in con)


def test_los_completos_van_primero_y_ordenados(serie):
    con = suggest_orders(serie, d=1, D=0, lam=0.0, top_n=8,
                         incluir_dispersos=True)
    tipos = [_disperso(sp) for sp in con]
    assert tipos == sorted(tipos), "un disperso se coló entre los completos"
    comp = [sp for sp in con if not _disperso(sp)]
    assert [s.similarity for s in comp] == sorted(
        (s.similarity for s in comp), reverse=True)


def test_el_defecto_es_no_incluirlos(serie):
    """La API limpia por defecto: quien itere la lista no los mezcla sin querer.
    Ese descuido es el que ponía un modelo restringido en manos de quien pedía
    «el AR(2) de la lista»."""
    import inspect
    p = inspect.signature(suggest_orders).parameters["incluir_dispersos"]
    assert p.default is False


# ───────────── la presentación los ofrece, marcados ─────────────

def test_la_presentacion_los_separa_y_explica(serie):
    from art.describe import describe_identification
    t = describe_identification(serie, d=1, D=0, lam=0.0).summary
    assert "Candidatos ARMA" in t
    assert "Restricciones por confirmar" in t
    assert "NO estimar de entrada" in t
    assert "ar_factorization" in t


def test_la_presentacion_da_el_argumento_del_signo(serie):
    """Sin el porqué, «no estimar de entrada» es una prohibición arbitraria."""
    from art.describe import describe_identification
    t = describe_identification(serie, d=1, D=0, lam=0.0).summary
    assert "θ<0" in t and "θ>0" in t
    assert "f=3" in t or "periodo 4" in t


def test_la_ambiguedad_se_juzga_sobre_el_ranking(serie):
    """El aviso de «decisión ambigua» compara los dos primeros. Si un disperso
    se cuela ahí, avisa de una ambigüedad entre cosas que no compiten."""
    from tests._fuente import fuente_de

    from art.describe import describe_identification
    src = fuente_de(describe_identification)
    i = src.find("ambiguous =")
    assert "specs = completos or specs" in src[:i]
