"""BUG-0051 — loglik/AIC/BIC sólo se comparan en la misma escala.

`ifadf` (diferenciación por frecuencia) se caía del spec, y con ella de la
ecuación, del diff de versiones y de la detección de anidamiento. Dos modelos que
explican variables dependientes distintas se comparaban por AIC.
"""
import os
import warnings

import pytest

from art.guion import _build_equation, _extract_spec
from art.mcp_server import _nested_relation, _spec_diff

R = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/run2/RATIO/"


def _spec(**kw):
    base = dict(lam=0.0, d=1, D=0, p=0, q=0, P=0, Q=0,
                n_harmonics=0, interventions=[], ifadf=[0, 0, 0])
    base.update(kw)
    return base


# ── La transformación viaja en el spec ────────────────────────────────────

def test_el_spec_lleva_ifadf():
    if not os.path.exists(R + "RATIO_m06.pre"):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    from art.mcp_server import _load_fitted
    _, m = _load_fitted(R + "RATIO_m06.pre")
    assert _extract_spec(m, lam=0.0)["ifadf"] == [0, 1, 0]


# ── La ecuación lo dice ───────────────────────────────────────────────────

@pytest.mark.parametrize("ifadf,freq,esperado", [
    ([0, 1, 0], 4,  "(1+B²)"),        # f=1 trimestral: 2cos(π/2)=0
    ([0, 0, 1], 4,  "(1+B)"),         # Nyquist
    ([1, 0, 0], 4,  "(1−B)"),         # f=0
    ([0, 1, 0, 0, 0, 0, 0], 12, "(1−1.732B+B²)"),   # f=1 mensual
])
def test_la_ecuacion_nombra_el_factor(ifadf, freq, esperado):
    eq = _build_equation(_spec(ifadf=ifadf), freq)
    assert esperado in eq, eq


def test_sin_ifadf_la_ecuacion_no_cambia():
    assert _build_equation(_spec(), 4).startswith("∇[ln y_t]")


# ── El diff lo anuncia ────────────────────────────────────────────────────

def test_el_diff_anuncia_el_cambio_de_ifadf():
    ch = _spec_diff(_spec(), _spec(ifadf=[0, 1, 0]))
    assert any("ifadf" in c for c in ch), ch


def test_el_diff_anuncia_el_cambio_de_lambda():
    ch = _spec_diff(_spec(lam=0.0), _spec(lam=1.0))
    assert any("lam" in c for c in ch), ch


# ── El anidamiento exige la misma transformación ──────────────────────────

@pytest.mark.parametrize("cambio", [
    {"ifadf": [0, 1, 0]},
    {"lam": 1.0},
    {"d": 2},
    {"D": 1},
])
def test_transformacion_distinta_no_es_anidamiento(cambio):
    a = _spec()
    b = _spec(q=1, **cambio)          # b tiene MÁS parámetros
    assert _nested_relation(a, b, 1, 2) == "none", (
        f"con {cambio} no puede haber anidamiento: son escalas distintas")


def test_misma_transformacion_si_puede_anidar():
    """La corrección no puede cargarse el caso legítimo."""
    a = _spec()
    b = _spec(q=1)
    assert _nested_relation(a, b, 1, 2) == "A_in_B"
