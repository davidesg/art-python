"""BUG-0124 and BUG-0151 — one list of seed-contaminated standard errors.

BUG-0124: the exact-seed detector and the near-seed one ran in if/else, so
with one exact match the near ones were never counted (RATIO_m50: the warning
said 1 of 6, four were within 0.03 % of the seed), and the equation's ✗ marks
came from yet another test. BUG-0151: the seed can survive in a ROTATED
direction (ITCER fase 1: eigenvalues 0.0175 and 0.0214 against 2/n = 0.024)
with no diagonal near it. Now one list — exact, near and rotated — gives the
count and the marks; with fdhess (fue >= 0.1.17) it is empty: the covariance
is the curvature at the optimum.
"""
import numpy as np
import pytest

from art.diagnosis import (seed_contaminated_indices, seed_contaminated_se,
                           seed_directions, degenerate_variance_indices,
                           near_seed_variance_indices)


class _Res:
    def __init__(self, n, cov, niter=1, se_method=None):
        self.residuals = np.zeros(n)
        self.cov_matrix = np.asarray(cov, float)
        self.niter = niter
        self.npar = self.cov_matrix.shape[0]
        self.std_errors = np.sqrt(np.diag(self.cov_matrix))
        self.se_method = se_method


def test_partial_degeneracy_counts_every_seed_variance():
    """The report's synthetic repro: one exact, three at seed*(1+2e-4)."""
    n = 81
    seed = 2.0 / n
    cov = np.diag([seed, seed * (1 + 2e-4), seed * (1 + 2e-4), seed * (1 + 2e-4), 0.9, 0.004])
    r = _Res(n, cov)
    assert degenerate_variance_indices(r) == [0]
    assert seed_contaminated_indices(r) == [0, 1, 2, 3]


def test_ratio_m50_as_measured():
    """RATIO_m50, niter = 1: the measured diagonal. Exact [1], near [0, 2, 3, 4]."""
    n = 81
    v = [0.02469424, 0.02469155, 0.02469575, 0.02469722, 0.02265081, 0.00391465]
    r = _Res(n, np.diag(v))
    assert seed_contaminated_indices(r) == [0, 1, 2, 3, 4]


def test_a_rotated_seed_is_seen():
    """ITCER m01: the omega block, one direction left at the seed, rotated."""
    n = 83
    seed = 2.0 / n
    u = np.array([0.67, 0.74, -0.08]); u /= np.linalg.norm(u)
    Q, _ = np.linalg.qr(np.column_stack([u, [1, 0, 0], [0, 0, 1]]))
    Q[:, 0] = u if Q[:, 0] @ u > 0 else -u
    cov = Q @ np.diag([seed * 0.73, 5.20, 5.41]) @ Q.T
    r = _Res(n, cov)
    assert degenerate_variance_indices(r) == [] and near_seed_variance_indices(r) == []
    (w, vec), = seed_directions(r, tol=0.5)
    assert w == pytest.approx(seed * 0.73)
    assert seed_contaminated_indices(r, tol=0.5) == [0, 1]


def test_fdhess_has_no_seed():
    n = 81
    r = _Res(n, np.diag([2.0 / n] * 3), se_method="fdhess")
    assert seed_contaminated_indices(r) == [] and seed_contaminated_se(r) == []


def test_the_count_and_the_marks_are_one_list():
    """The equation's ✗ marks and the warning's count come from the same list."""
    import re
    import fue
    from art.mcp_server import _equation_for_prompt
    rng = np.random.default_rng(3)
    a = rng.standard_normal(200)
    y = np.zeros(200)
    for t in range(2, 200):
        y[t] = 0.5 * y[t - 1] - 0.3 * y[t - 2] + a[t]
    ts = fue.TimeSeries(list(100 + y), freq=12, start=(2000, 1), name="S")
    m = fue.Model(ts, ar=[[0.1, 0.1]], estimate_mu=True, mu=100.0)
    m.fit()
    r = m._result
    n = len(np.asarray(r.residuals))
    seed = 2.0 / n
    k = len(np.asarray(r.std_errors).ravel())
    cov = np.diag([seed, seed * (1 + 1e-4)] + [0.5] * (k - 2))
    r.cov_matrix, r.std_errors, r.se_method, r.niter = cov, np.sqrt(np.diag(cov)), None, 1
    txt = _equation_for_prompt(ts, m)
    marks = txt.count("(✗")
    said = re.search(r"(\d+) de los (\d+) errores típicos", txt)
    assert marks == 2 and said and int(said.group(1)) == 2
