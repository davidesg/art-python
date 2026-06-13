"""Basic tests for identification listing."""
import numpy as np
import pytest

import fue
from art.identification import (
    boxcox_transform,
    apply_differences,
    mean_stdev_data,
    compute_stats,
    identification_listing,
)


def _ripc():
    return fue.datasets.ripc()


# --- Box-Cox ---

def test_boxcox_log():
    y = np.array([1.0, 2.0, 4.0, 8.0])
    z = boxcox_transform(y, lam=0.0)
    np.testing.assert_allclose(z, np.log(y))


def test_boxcox_identity():
    y = np.array([1.0, 2.0, 3.0])
    np.testing.assert_array_equal(boxcox_transform(y, lam=1.0), y)


# --- Differencing ---

def test_regular_diff():
    y = np.array([1.0, 3.0, 6.0, 10.0])
    w = apply_differences(y, freq=1, nrdiff=1, nadiff=0)
    np.testing.assert_allclose(w, [2.0, 3.0, 4.0])


def test_seasonal_diff():
    y = np.ones(24)
    y[12:] = 2.0
    w = apply_differences(y, freq=12, nrdiff=0, nadiff=1)
    assert len(w) == 12
    np.testing.assert_allclose(w, np.ones(12))


def test_double_diff():
    y = np.arange(1.0, 11.0)
    w = apply_differences(y, freq=1, nrdiff=2, nadiff=0)
    np.testing.assert_allclose(w, np.zeros(8), atol=1e-12)


# --- Mean–std data ---

def test_mdt_shape():
    ts = _ripc()
    z = boxcox_transform(np.asarray(ts.data), lam=0.0)
    mdt = mean_stdev_data(z, nog=12)
    assert mdt.ng == len(z) // 12
    assert len(mdt.means_std) == mdt.ng
    assert len(mdt.stds_std)  == mdt.ng


def test_mdt_standardised():
    ts = _ripc()
    z = boxcox_transform(np.asarray(ts.data), lam=0.0)
    mdt = mean_stdev_data(z, nog=12)
    np.testing.assert_allclose(mdt.means_std.mean(), 0.0, atol=1e-10)
    np.testing.assert_allclose(mdt.stds_std.mean(),  0.0, atol=1e-10)


# --- Stats ---

def test_stats_n():
    ts = _ripc()
    z = boxcox_transform(np.asarray(ts.data), lam=0.0)
    w = apply_differences(z, freq=12, nrdiff=1, nadiff=0)
    st = compute_stats(w, lags=36)
    assert st.n == len(w)
    assert len(st.acf)  == 36
    assert len(st.pacf) == 36


# --- Full listing ---

def test_listing_panels_monthly():
    ts = _ripc()
    lst = identification_listing(ts, lam=0.0, max_d=2, max_D=1)
    # monthly: (D=0,d=0),(D=0,d=1),(D=0,d=2),(D=1,d=0),(D=1,d=1),(D=1,d=2)
    assert len(lst.panels) == 6
    assert lst.freq == 12


def test_listing_html(tmp_path):
    ts = _ripc()
    out = str(tmp_path / "listing.html")
    lst = identification_listing(ts, lam=0.0, output_path=out)
    import os
    assert os.path.exists(out)
    html = open(out).read()
    assert "Identification Listing" in html
    assert "Mean" in html
    assert len(lst.panels) == 6
