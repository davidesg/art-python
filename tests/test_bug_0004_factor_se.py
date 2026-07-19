"""
Regression test for BUG-0004 — ar_factorization now returns SEs for the damping
and period of complex AR(2) factors (delta method).

Ports and pins `caracterizar_operadores.car_ar2` / ABTreadway-Dperar2.xls.

See bugs/BUG-0004-ar-factorization-standard-errors.md.
"""

import numpy as np
import pytest

from art.roots import complex_factor_se, factor_ar

# ABTreadway-Dperar2.xls, sheet AR2.
_A1, _A2 = -0.146222, -0.26976
_V = [[0.016215, 0.001902], [0.001902, 0.015497]]


def test_complex_factor_se_matches_excel():
    se = complex_factor_se(_A1, _A2, _V, excel_compat=True)
    assert se["se_r"] == pytest.approx(0.119839, abs=1e-4)
    assert se["se_period"] == pytest.approx(0.381938, abs=1e-4)


def test_consistent_period_se_differs_from_excel():
    # Default (consistent) derivative uses w, not arccos(|t|); smaller here.
    excel = complex_factor_se(_A1, _A2, _V, excel_compat=True)
    cons = complex_factor_se(_A1, _A2, _V)
    assert cons["se_period"] == pytest.approx(0.266303, abs=1e-4)
    assert cons["se_period"] < excel["se_period"]


def test_factor_ar_attaches_se_for_direct_ar2():
    fac = factor_ar([_A1, _A2], sper=12, cov=_V)
    cf = fac.complex[0]
    assert cf.se_r == pytest.approx(0.11984, abs=1e-4)
    assert cf.se_period == pytest.approx(0.26630, abs=1e-4)   # consistent default
    # half-life = ln(0.5)/ln(d)
    assert cf.half_life == pytest.approx(np.log(0.5) / np.log(cf.r), rel=1e-9)


def test_factor_ar_without_cov_has_no_se():
    cf = factor_ar([_A1, _A2], sper=12).complex[0]
    assert cf.se_r is None and cf.se_period is None


def test_higher_order_ignores_cov():
    # order-3 operator: sub-factors are derived from roots; cov must be ignored,
    # not crash, and leave SEs unset.
    fac = factor_ar([0.5, -0.81, 0.405], sper=12, cov=_V)
    assert all(c.se_r is None and c.se_period is None for c in fac.complex)


def test_describe_shows_se_when_present():
    from art.roots import describe
    txt = describe(factor_ar([_A1, _A2], sper=12, cov=_V))
    assert "±" in txt
    txt_no = describe(factor_ar([_A1, _A2], sper=12))
    assert "±" not in txt_no
