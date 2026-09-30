"""The domain procedure in the orders node (docs/DISENO-dominio-en-los-ordenes.md,
decisions of 2026-09-30, §10.bis).

* The engine's card of implied dynamics reproduces the study's worked example,
  PGAS (§7): the AR(2) φ = (0.765, −0.264) against the MA(2) 1 + 0.788B + 0.276B².
* The (∇, MA) pair is read (§5): a stochastic mean with 1 − θ; θ < 0
  alternates; a root near 1 sends the question back to d.
* On a genuine tie the identification listing carries the card by itself.
* The `dominio` node requires the expectations; `criterio="dominio"` requires
  a `dominio` node that declared them.
"""
import json
import os

import numpy as np
import pytest

from art.dinamica import card, render

F = os.path.join(os.path.dirname(__file__), "fixtures", "bug_0196_0197")


def _fn(name):
    from art import mcp_server as M
    t = getattr(M, name)
    return getattr(t, "fn", t)


# ── the card, on the study's PGAS ─────────────────────────────────────────────

def test_pgas_card_is_the_studys():
    ar = card("AR(2)", phi=(0.765, -0.264), d=1, s=4)
    ma = card("MA(2)", theta=(-0.788, -0.276), d=1, s=4)
    assert np.allclose(ar.psi[1:4], [0.765, 0.321, 0.044], atol=5e-3)
    assert np.allclose(ma.psi[1:4], [0.788, 0.276, 0.0], atol=5e-3)
    assert ar.psi_min == pytest.approx(-0.05, abs=5e-3)          # the weak cycle
    (mod, per), = ar.ar_roots
    assert mod == pytest.approx(0.51, abs=0.01) and per == pytest.approx(8.6, abs=0.1)
    assert ar.long_run == pytest.approx(2.00, abs=0.01)
    assert ma.long_run == pytest.approx(2.06, abs=0.01)
    # forecast weights on the levels: finite for the AR(2), alternating for the MA(2)
    assert np.allclose(ar.pi[:3], [1.77, -1.03, 0.26], atol=0.01) and ar.pi_finite
    assert np.allclose(ma.pi[:3], [1.79, -1.13, 0.40], atol=0.01)
    assert not ma.pi_finite and ma.pi_alternates


def test_the_pair_of_a_difference_and_its_ma():
    """§5.1: (1 − 0.70B) with d = 1 is an exponential mean, 1 − θ = 0.30;
    θ < 0 alternates; an MA root near 1 is a question of d."""
    m = card("MA(1)", theta=(0.70,), d=1)
    assert np.allclose(m.pi[:5], [0.30, 0.21, 0.15, 0.10, 0.07], atol=0.01)
    assert "1 − θ = 0.30" in m.pairs[0][2]
    neg = card("MA(1)", theta=(-0.42,), d=1)
    assert "alternan" in neg.pairs[0][2]
    near = card("ARMA(1,2)", phi=(0.43,), theta=(0.23, 0.616), d=1)   # the muskrat's
    assert any("la pregunta es de d" in r for _w, _t, r in near.pairs)


def test_materiality_is_said():
    txt = render([card("A", phi=(0.5,)), card("B", theta=(-0.5,))], gap=0.1)
    assert "interpretativa" in txt
    assert "cambia la previsión" in render([card("A", phi=(0.5,))], gap=1.0)


# ── the card arrives by itself on a genuine tie ──────────────────────────────

def test_the_listing_carries_the_card_on_a_tie():
    from art.describe import describe_identification
    from art.mcp_server import _load_ts_model
    ts, _ = _load_ts_model(os.path.join(F, "MUSKRAT.inp"))
    r = describe_identification(ts, d=1, D=0, lam=0.0)
    assert len(r.data["tie"]) >= 2 and (2, 0, 0, 0) in r.data["tie"]
    assert "ficha de dinámica implícita" in r.summary
    assert "expectativas declaradas en el nodo `dominio`" in r.summary
    assert "Materialidad" in r.data["card"]


# ── the guion ─────────────────────────────────────────────────────────────────

def test_the_dominio_node_requires_expectations(tmp_path):
    gp = str(tmp_path / "X_guion.json")
    out = _fn("guion_node")(gp, "dominio", "price_index", "un IPC")
    assert "obligatoria" in out[0].text
    out = _fn("guion_node")(gp, "dominio", "price_index", "un IPC",
                            expectativas="persistencia alta de la inflación (indexación)")
    assert "expectativas: persistencia alta" in out[0].text
    g = json.load(open(gp))
    assert g["entries"][-1]["node"]["expectativas"].startswith("persistencia alta")


def test_criterio_dominio_cites_a_declared_expectation(tmp_path):
    gp = str(tmp_path / "Y_guion.json")
    out = _fn("guion_node")(gp, "ordenes", "AR(2)", "…", criterio="dominio")
    assert "no tiene ninguno con expectativas" in out[0].text
    _fn("guion_node")(gp, "dominio", "multiplicative", "precio",
                      expectativas="ciclo de oferta de 2-3 años")
    out = _fn("guion_node")(gp, "ordenes", "AR(2)", "…", criterio="dominio")
    assert "criterio: dominio" in out[0].text
    assert "`criterio` es" in _fn("guion_node")(gp, "ordenes", "AR(2)", "…",
                                                criterio="gusto")[0].text
