"""BUG-0065 — la nula de Shin-Fuller es UNA raíz, con el resto libre.

El código imponía ρₘ en el primer coeficiente de CADA factor y cero en los
demás. Eso hacía el contraste dependiente de cómo estuviera escrito el AR —el
mismo modelo daba Φ̂₁ᵤ = 25.746 o 7.632— y medía «¿el AR completo ajusta mejor
que un AR(1) en ρₘ?» en vez de «¿la raíz dominante es 1?».
"""
import io
import os
import warnings

import numpy as np
import pytest

import fue
from art.formal_tests import shin_fuller

from datos_replica import REPLICA_DS, requiere_replica

M14 = REPLICA_DS + "run4/PGAS/PGAS_m14.pre" if REPLICA_DS else ""


def _fact(tmp_path):
    """El MISMO modelo escrito como dos AR(1) en vez de un AR(2)."""
    s = io.open(M14, encoding="utf-8").read()
    viejo = ("**Number and orders of regular AR operators:\n1 2\n**\n"
             "1.6390 1\n-0.6668 1")
    nuevo = ("**Number and orders of regular AR operators:\n2 1 1\n**\n"
             "0.8890 1\n**\n0.7500 1")
    assert s.count(viejo) == 1, "el .pre cambió; el test no mide nada"
    p = tmp_path / "fact.inp"
    p.write_text(s.replace(viejo, nuevo), encoding="utf-8")
    return str(p)


def _sf(p):
    warnings.simplefilter("ignore")
    ts, m = fue.load(p)
    m.fit()
    return m, shin_fuller(m)


# ── la propiedad que faltaba ──────────────────────────────────────────────

@requiere_replica
def test_el_contraste_es_invariante_a_la_parametrizacion(tmp_path):
    """Mismo modelo ajustado ⇒ mismo contraste. Es lo mínimo exigible."""
    ma, ra = _sf(M14)
    mb, rb = _sf(_fact(tmp_path))
    assert ra.loglik_free == pytest.approx(rb.loglik_free, abs=1e-6), \
        "no son el mismo ajuste; el test no compara lo que dice comparar"
    assert ra.phi_1u == pytest.approx(rb.phi_1u, abs=1e-4)
    assert ra.df == rb.df


@requiere_replica
def test_la_nula_restringe_una_sola_raiz():
    _, r = _sf(M14)
    assert r.df == 1


@requiere_replica
def test_el_caso_del_run4_pide_d_mas_uno():
    """φ=[1.639, −0.667]: raíz dominante 0.889, indistinguible de 1 con n=84."""
    _, r = _sf(M14)
    assert r.phi_1u < r.crit_10pct, (
        f"Φ̂₁ᵤ={r.phi_1u:.3f} no debería superar el crítico al 10%")


# ── y lo que no puede romperse ────────────────────────────────────────────

@requiere_replica
# PGAS_m20 queda fuera a propósito: su AR(2) tiene raíces COMPLEJAS y el
# contraste no aplica — lo fija `test_un_AR2_de_raices_COMPLEJAS_...`.
@pytest.mark.parametrize("rel", ["guiado/ITCER/ITCER_m20.pre",
                                 "run3/PGAS/PGAS_m03.pre"])
def test_un_AR_estacionario_sigue_diciendo_que_d_basta(rel):
    from datos_replica import REPLICA
    p = REPLICA + rel
    if not os.path.exists(p):
        pytest.skip("modelo no disponible")
    _, r = _sf(p)
    assert r.phi_1u > r.crit_5pct, (
        f"{rel}: Φ̂₁ᵤ={r.phi_1u:.3f} debería rechazar la raíz unitaria")


def test_sintetico_i1_no_rechaza_la_raiz_unitaria(tmp_path):
    """Sin datos de la réplica: un I(1) puro no puede salir estacionario."""
    warnings.simplefilter("ignore")
    rng = np.random.default_rng(7)
    y = np.cumsum(rng.standard_normal(200))
    ts = fue.TimeSeries((100 + y).tolist(), freq=4, start=(2000, 1), name="I1")
    from art.pipeline import ModelSpec, build_and_fit
    fr = build_and_fit(ts, ModelSpec(lam=1.0, d=0, D=0, p=1, q=0, P=0, Q=0,
                                     n_harmonics=0, estimate_mu=True),
                       str(tmp_path / "i1.inp"), 3.5)
    r = shin_fuller(fr.model)
    assert r.df == 1
    assert r.phi_1u < r.crit_10pct, (
        f"un paseo aleatorio salió estacionario: Φ̂₁ᵤ={r.phi_1u:.3f}")


def test_sintetico_estacionario_si_rechaza(tmp_path):
    warnings.simplefilter("ignore")
    rng = np.random.default_rng(3)
    a = rng.standard_normal(300)
    w = np.zeros(300)
    for t in range(1, 300):
        w[t] = 0.35 * w[t - 1] + a[t]
    ts = fue.TimeSeries((50 + w[100:]).tolist(), freq=4, start=(2000, 1), name="E")
    from art.pipeline import ModelSpec, build_and_fit
    fr = build_and_fit(ts, ModelSpec(lam=1.0, d=0, D=0, p=1, q=0, P=0, Q=0,
                                     n_harmonics=0, estimate_mu=True),
                       str(tmp_path / "e.inp"), 3.5)
    r = shin_fuller(fr.model)
    assert r.phi_1u > r.crit_5pct, (
        f"un AR(1) con φ=0.35 no salió estacionario: Φ̂₁ᵤ={r.phi_1u:.3f}")


def test_la_ecuacion_35_pone_el_estadistico_a_cero(tmp_path):
    """Φ̂₁ᵤ = 0 cuando ρ̂ > 1−4/n (Shin-Fuller 1998, ec. 3.5)."""
    warnings.simplefilter("ignore")
    rng = np.random.default_rng(7)
    ts = fue.TimeSeries((100 + np.cumsum(rng.standard_normal(200))).tolist(),
                        freq=4, start=(2000, 1), name="I1")
    from art.pipeline import ModelSpec, build_and_fit
    fr = build_and_fit(ts, ModelSpec(lam=1.0, d=0, D=0, p=1, q=0, P=0, Q=0,
                                     n_harmonics=0, estimate_mu=True),
                       str(tmp_path / "z.inp"), 3.5)
    r = shin_fuller(fr.model)
    assert r.phi_dominant > r.phi_null
    assert r.phi_1u == 0.0
    assert r.stationary is False


def test_un_AR2_de_raices_COMPLEJAS_no_admite_el_contraste():
    """La reparametrización (m − ρ)·A(m) exige ρ REAL: un par conjugado no la tiene.

    Forzarla es peor que no hacerla — deflactar por una raíz compleja da
    coeficientes complejos cuya parte imaginaria `float()` descarta EN SILENCIO,
    produciendo un factor que no es el del modelo. Un par cerca del círculo
    unidad es no estacionariedad en ω≠0: eso lo contrastan el MEG y el DCD_f.
    """
    from datos_replica import REPLICA
    p = REPLICA + "guiado/PGAS/PGAS_m20.pre" if REPLICA else ""
    if not p or not os.path.exists(p):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    _, m = fue.load(p)
    m.fit()
    raices = np.roots([-c for c in reversed(m.ar[0])] + [1.0])
    assert all(abs(z.imag) > 1e-6 for z in raices), \
        "el caso ya no tiene raíces complejas; el test no mide nada"
    with pytest.raises(ValueError, match="raíz REAL"):
        shin_fuller(m)


def test_el_mensaje_remite_al_contraste_que_si_aplica():
    from datos_replica import REPLICA
    p = REPLICA + "guiado/PGAS/PGAS_m20.pre" if REPLICA else ""
    if not p or not os.path.exists(p):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    _, m = fue.load(p)
    m.fit()
    try:
        shin_fuller(m)
        pytest.fail("debería no aplicar")
    except ValueError as e:
        assert "MEG" in str(e) and "DCD_f" in str(e)
