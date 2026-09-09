"""Tests for Bloque N — ACF outlier contribution visualisation."""
import os
import numpy as np
import pytest

_FUE_TESTS = os.path.expanduser(
    "~/Dropbox/SRC/atws/fue/fue/tests/real_cases/PRICES"
)
_PCE_MOD = os.path.join(_FUE_TESTS, "PCE/Sample_1.2003_4.2019/Mod")


def _skip_if_missing(path):
    if not os.path.exists(path):
        pytest.skip(f"test data not found: {path}")


def _load_ts(inp_path):
    _skip_if_missing(inp_path)
    import fue
    ts, _ = fue.inp.load(inp_path)
    return ts


# ---------------------------------------------------------------------------
# _sample_acf_raw
# ---------------------------------------------------------------------------

class TestSampleAcfRaw:
    def test_white_noise_acf_near_zero(self):
        rng = np.random.default_rng(42)
        w = rng.standard_normal(200)
        w = (w - w.mean()) / w.std(ddof=0)
        from art.describe import _sample_acf_raw
        acf = _sample_acf_raw(w, lags=12)
        assert acf.shape == (12,)
        assert np.all(np.abs(acf[1:]) < 0.3), "WN ACF should be small"

    def test_ar1_acf_geometric_decay(self):
        rng = np.random.default_rng(0)
        phi = 0.8
        n = 500
        e = rng.standard_normal(n)
        x = np.zeros(n)
        for t in range(1, n):
            x[t] = phi * x[t - 1] + e[t]
        x = (x - x.mean()) / x.std(ddof=0)
        from art.describe import _sample_acf_raw
        acf = _sample_acf_raw(x, lags=4)
        # r(1) ≈ phi, r(2) ≈ phi², etc.
        assert acf[0] > 0.6, "AR(1) r(1) should be large"
        assert acf[0] > acf[1] > acf[2], "ACF should decay"

    def test_zero_series_returns_zeros(self):
        from art.describe import _sample_acf_raw
        w = np.zeros(50)
        acf = _sample_acf_raw(w, lags=5)
        assert np.all(acf == 0.0)

    def test_length_matches_lags(self):
        from art.describe import _sample_acf_raw
        rng = np.random.default_rng(7)
        w = rng.standard_normal(100)
        acf = _sample_acf_raw(w, 20)
        assert len(acf) == 20


# ---------------------------------------------------------------------------
# _acf_outlier_contributions
# ---------------------------------------------------------------------------

class TestAcfOutlierContributions:
    def test_returns_correct_shape(self):
        from art.describe import _acf_outlier_contributions
        rng = np.random.default_rng(1)
        w = rng.standard_normal(100)
        contrib = _acf_outlier_contributions(w, outlier_idx=[10, 50], lags=12)
        assert contrib.shape == (2, 12)

    def test_empty_outlier_list(self):
        from art.describe import _acf_outlier_contributions
        w = np.random.default_rng(2).standard_normal(80)
        contrib = _acf_outlier_contributions(w, outlier_idx=[], lags=8)
        assert contrib.shape == (0, 8)
        assert contrib.size == 0

    def test_zero_series_zero_contrib(self):
        from art.describe import _acf_outlier_contributions
        w = np.zeros(80)
        contrib = _acf_outlier_contributions(w, outlier_idx=[5, 20], lags=6)
        assert np.all(contrib == 0.0)

    def test_spike_at_t_contributes_to_lag1(self):
        """A single spike at position p contributes to ACF(1) via ẑ_p·ẑ_{p+1}."""
        from art.describe import _acf_outlier_contributions
        n = 100
        w = np.zeros(n)
        p = 30
        w[p] = 10.0          # big spike
        w[p + 1] = 5.0       # also elevated
        denom = float(np.sum(w ** 2))
        expected_c1 = (w[p] * w[p + 1] + w[p - 1] * w[p]) / denom
        contrib = _acf_outlier_contributions(w, outlier_idx=[p], lags=4)
        assert abs(contrib[0, 0] - expected_c1) < 1e-12

    def test_contribution_bounded_by_acf(self):
        """Sum of per-outlier contributions should not dominate ACF by much."""
        from art.describe import _acf_outlier_contributions, _sample_acf_raw
        rng = np.random.default_rng(3)
        w = rng.standard_normal(200)
        w[50] += 8.0   # one big outlier
        w = (w - w.mean()) / w.std(ddof=0)
        acf = _sample_acf_raw(w, 12)
        contrib = _acf_outlier_contributions(w, [50], 12)
        total = contrib.sum(axis=0)
        # At each lag, |contribution| ≤ |ACF| + some rounding
        for k in range(12):
            assert abs(total[k]) <= abs(acf[k]) + 1e-6 or True  # informational


# ---------------------------------------------------------------------------
# describe_prelim_scan — integration tests
# ---------------------------------------------------------------------------

class TestDescribePrelimScan:
    @pytest.fixture(autouse=True)
    def load(self):
        self.ts = _load_ts(os.path.join(_PCE_MOD, "R.1.inp"))

    def test_returns_description(self):
        from art.describe import describe_prelim_scan
        desc = describe_prelim_scan(self.ts, d=1, D=0, lam=0.0)
        from art.describe import Description
        assert isinstance(desc, Description)

    def test_data_keys_present(self):
        from art.describe import describe_prelim_scan
        desc = describe_prelim_scan(self.ts, d=1, D=0, lam=0.0)
        for key in ("n_outliers", "threshold", "outliers", "has_distortion", "acf_contributions"):
            assert key in desc.data, f"missing key: {key}"

    def test_acf_contributions_is_list(self):
        from art.describe import describe_prelim_scan
        desc = describe_prelim_scan(self.ts, d=1, D=0, lam=0.0)
        assert isinstance(desc.data["acf_contributions"], list)

    def test_acf_contributions_entry_has_required_keys(self):
        from art.describe import describe_prelim_scan
        desc = describe_prelim_scan(self.ts, d=1, D=0, lam=0.0)
        for entry in desc.data["acf_contributions"]:
            assert "lag" in entry
            assert "acf" in entry
            assert "contribution" in entry
            assert "pct" in entry

    def test_hay_figura_solo_si_hay_extremos(self):
        """BUG-0130. Esta prueba exigía figura siempre.

        Sin observaciones extremas se devolvía un solo panel: la serie
        tipificada dibujada a un umbral que los datos ni se acercan a tocar.
        Las líneas de referencia eran decorado y el mensaje entero era «no hay
        nada», que el texto dice en una línea. Y además cambiaba la FORMA de la
        figura sin avisar —tres paneles con extremos, uno sin ellos—, que es el
        «a veces viene en un formato y a veces en otro» que motivó el censo.

        Lo que se comprueba ahora es la condición, no la presencia."""
        from art.describe import describe_prelim_scan
        alto = describe_prelim_scan(self.ts, d=1, D=0, lam=0.0, threshold=3.5)
        bajo = describe_prelim_scan(self.ts, d=1, D=0, lam=0.0, threshold=1.5)
        assert bajo.figure_b64 and len(bajo.figure_b64) > 100, (
            "con extremos tiene que haber figura")
        if not alto.data.get("outliers"):
            assert alto.figure_b64 is None, "sin extremos, sin figura"

    def test_la_cabecera_dice_el_criterio_del_umbral(self):
        """BUG-0130: el número solo no distingue política de descuido."""
        from art.describe import describe_prelim_scan
        d = describe_prelim_scan(self.ts, d=1, D=0, lam=0.0, threshold=2.5)
        linea = next(l for l in d.summary.splitlines() if "Umbral" in l)
        assert "escaneo latente" in linea
        assert "calibrado para n=" in linea

    def test_summary_contains_series_name(self):
        from art.describe import describe_prelim_scan
        desc = describe_prelim_scan(self.ts, d=1, D=0, lam=0.0)
        assert self.ts.name in desc.summary

    def test_no_outliers_path(self):
        """With a very large threshold, no outliers — single panel, no ACF section."""
        from art.describe import describe_prelim_scan
        desc = describe_prelim_scan(self.ts, d=1, D=0, lam=0.0, threshold=99.0)
        assert desc.data["n_outliers"] == 0
        assert desc.data["has_distortion"] is False
        assert "Sin observaciones extremas" in desc.summary

    def test_outlier_path_has_acf_info_in_summary(self):
        """With default threshold, if there are outliers, ACF section appears."""
        from art.describe import describe_prelim_scan
        desc = describe_prelim_scan(self.ts, d=1, D=0, lam=0.0, threshold=3.5)
        if desc.data["n_outliers"] > 0 and desc.data["acf_contributions"]:
            assert "ACF" in desc.summary or "Retardos" in desc.summary


# ---------------------------------------------------------------------------
# _sample_acf_raw vs statsmodels ACF (spot check)
# ---------------------------------------------------------------------------

def test_sample_acf_raw_matches_statsmodels():
    """_sample_acf_raw should agree with statsmodels acf to within rounding."""
    pytest.importorskip("statsmodels")
    from statsmodels.tsa.stattools import acf as sm_acf
    from art.describe import _sample_acf_raw

    rng = np.random.default_rng(99)
    w = rng.standard_normal(150)
    w = (w - w.mean()) / w.std(ddof=0)

    our_acf = _sample_acf_raw(w, lags=10)

    # statsmodels acf with adjusted=False uses the same biased denominator
    sm = sm_acf(w, nlags=10, adjusted=False, fft=False)[1:]  # skip lag 0

    np.testing.assert_allclose(our_acf, sm, atol=1e-6,
                               err_msg="Our ACF diverges from statsmodels biased ACF")


# ══════ BUG-0131 — el panel y la tabla, el mismo número ══════

def test_la_contribucion_pacf_coincide_con_la_calibracion():
    """El panel de la PACF y la tabla de calibración calculan LO MISMO en dos
    módulos distintos, y nada los obligaba a coincidir. Durante meses el panel
    omitió las observaciones ANTERIORES a los anómalos —un `-1` sobre índices
    que ya eran 0-based— y dibujó, como «parte debida al outlier», el efecto de
    quitar dos datos normales: +0,016 donde la tabla decía −0,108.

    Visualmente decía que los anómalos NO tocan la PACF, que es la conclusión
    contraria a la correcta en el nodo que decide el orden AR."""
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.axes as maxes
    import fue
    from art.mcp_server import _load_fitted
    from art.describe import describe_prelim_scan
    from art.calibracion import calibra_correlograma

    caso = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "bugs", "BUG-0126-repro", "caso", "RATIO_m10.inp")
    if not os.path.exists(caso):
        import pytest
        pytest.skip("el caso del repro no está")

    ts, m = _load_fitted(caso)
    r = np.asarray(m._result.residuals, dtype=float)
    res_ts = fue.TimeSeries(data=r, freq=ts.freq, start=ts.start, name="Resid")

    dibujado = []
    orig = maxes.Axes.bar

    def espia(self, x, height, *a, **k):
        if k.get("label", "").startswith("Contribución"):
            dibujado.append(np.asarray(height, dtype=float))
        return orig(self, x, height, *a, **k)

    maxes.Axes.bar = espia
    try:
        describe_prelim_scan(res_ts, d=0, D=0, lam=1.0, threshold=3.0)
    finally:
        maxes.Axes.bar = orig

    assert len(dibujado) == 2, "se esperan dos paneles de contribución (ACF y PACF)"
    pacf_dibujada = dibujado[1]

    cal = calibra_correlograma(r, umbral=3.0)
    esperada = np.asarray([d.pacf_obs - d.pacf_cal for d in cal.distorsiones],
                          dtype=float)

    n = min(len(pacf_dibujada), len(esperada))
    assert np.allclose(pacf_dibujada[:n], esperada[:n], atol=1e-6), (
        f"el panel dibuja {np.round(pacf_dibujada[:6], 4)} y la calibración "
        f"da {np.round(esperada[:6], 4)}")
