"""
Regression test for BUG-0002 — guided_identification over-specifies d.

`recommended_d` used to require the strict consensus verdict 'stationary'
(ADF rejects AND KPSS does not), so a KPSS rejection at a low d — common in
bounded / mean-reverting climate series — escalated d even when ADF rejected the
unit root decisively.  The fix lets ADF's rejection govern: the smallest d at
which ADF rejects is chosen regardless of KPSS.

See bugs/BUG-0002-over-differencing-kpss.md.
"""

from art.identification import UnitRootResult, recommended_d


def _r(d, adf_p, kpss_p):
    adf_rej, kpss_rej = adf_p < 0.05, kpss_p < 0.05
    verdict = ("stationary" if adf_rej and not kpss_rej else
               "unit_root" if not adf_rej and kpss_rej else "ambiguous")
    return UnitRootResult(
        d=d, label=f"d{d}", n=200,
        adf_stat=-5.0, adf_pvalue=adf_p, adf_rejects=adf_rej,
        kpss_stat=0.5, kpss_pvalue=kpss_p, kpss_rejects=kpss_rej,
        verdict=verdict)


def test_decisive_adf_rejection_prevents_overdifferencing():
    # GEP-like: ADF rejects hard at every d; KPSS also rejects at d0/d1.
    res = [_r(0, 0.0001, 0.02), _r(1, 0.0, 0.04), _r(2, 0.0, 0.09)]
    assert recommended_d(res) == 0           # was 2 (double over-differencing)


def test_marginal_adf_rejection_still_d0():
    # GE-days-like: ADF rejects at 5% (p≈0.011) at d0 though KPSS rejects.
    res = [_r(0, 0.011, 0.010), _r(1, 0.0, 0.10)]
    assert recommended_d(res) == 0           # was 1


def test_genuine_unit_root_gives_d1():
    # ADF fails to reject at d0, rejects at d1 → difference once.
    res = [_r(0, 0.40, 0.01), _r(1, 0.001, 0.10)]
    assert recommended_d(res) == 1


def test_i2_only_when_adf_fails_at_d0_and_d1():
    res = [_r(0, 0.50, 0.01), _r(1, 0.20, 0.02), _r(2, 0.001, 0.10)]
    assert recommended_d(res) == 2


def test_no_adf_rejection_falls_back_to_last():
    res = [_r(0, 0.50, 0.01), _r(1, 0.20, 0.02)]
    assert recommended_d(res) == 1           # last d tested


def test_empty_results():
    assert recommended_d([]) == 0
