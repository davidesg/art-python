"""BUG-0006 (ART side) — the seasonal-AR seed must carry the sign of the NOISE, not
of the deterministic seasonality.

For a D=0 model with deterministic harmonics, the differenced series still contains
the seasonal pattern, whose seasonal autocorrelation is POSITIVE (it repeats every
s). Seeding the seasonal AR by Yule-Walker on that series gives a POSITIVE seed even
when the residual noise's seasonal AR is NEGATIVE — the wrong sign, which sends a
multimodal AR×AR fit to a spurious basin on some builds (Windows). `_make_model` now
regresses the harmonics out before seeding, so the seed follows the noise.
"""
import numpy as np
import fue
from art.pipeline import _make_model, _arma_starts


def _series_det_seasonality_negative_seasonal_ar(freq=12, n=360, phi_s=-0.5, seed=11):
    """∇log(y) = deterministic seasonal profile (repeats -> +ve seasonal autocorr)
    + a noise with a NEGATIVE seasonal AR(s).  Return the level series y."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    det = 0.6 * np.cos(2 * np.pi * t / freq) + 0.4 * np.sin(2 * np.pi * 2 * t / freq)
    a = rng.normal(0.0, 0.08, n)
    e = np.zeros(n)
    for i in range(n):
        e[i] = a[i] + (phi_s * e[i - freq] if i >= freq else 0.0)
    w = 0.001 + det + e                      # differenced-log space (+ tiny drift)
    y = np.exp(np.cumsum(w) + 4.0)           # integrate to a positive level
    return y


def test_seasonal_ar_seed_is_negative_when_noise_is():
    y = _series_det_seasonality_negative_seasonal_ar()
    ts = fue.TimeSeries(data=y.tolist(), freq=12, start=[1990, 1], name="SIM")
    m = _make_model(ts, lam=0.0, d=1, D=0, p=0, q=0,
                    n_harmonics=5, P=1, Q=0, estimate_mu=False)
    seed = m.ar_s[0][0]
    # The deterministic seasonality alone would give r(12) > 0 (a positive seed);
    # the fix seeds on the de-harmonized noise, whose seasonal AR is negative.
    assert seed < 0.0, f"seasonal-AR seed should be negative (noise sign), got {seed:+.3f}"


def test_raw_series_seasonal_autocorr_is_positive():
    """Guard the premise: the OBSERVED differenced series has POSITIVE seasonal
    autocorrelation (from the deterministic pattern), so a naive YW on it seeds
    positive — which is exactly the trap the fix avoids."""
    y = _series_det_seasonality_negative_seasonal_ar()
    w = np.diff(np.log(y))
    wc = w - w.mean()
    r12 = float(wc[12:] @ wc[:-12] / (wc @ wc))
    assert r12 > 0.1, f"expected positive seasonal autocorr from the det. pattern, got {r12:+.3f}"
    # and Yule-Walker on the RAW series would seed positive (the bug):
    naive = _arma_starts(w, 0, 0, 1, 0, 12)[2]
    assert naive[0] > 0.0, f"naive seed (on raw series) should be positive, got {naive}"
