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
        contrib, resto = _acf_outlier_contributions(w, outlier_idx=[10, 50],
                                                    lags=12)
        assert contrib.shape == (2, 12)
        assert resto.shape == (12,)

    def test_empty_outlier_list(self):
        from art.describe import _acf_outlier_contributions
        w = np.random.default_rng(2).standard_normal(80)
        contrib, resto = _acf_outlier_contributions(w, outlier_idx=[], lags=8)
        assert contrib.shape == (0, 8)
        assert contrib.size == 0
        assert np.all(resto == 0.0)

    def test_zero_series_zero_contrib(self):
        from art.describe import _acf_outlier_contributions
        w = np.zeros(80)
        contrib, resto = _acf_outlier_contributions(w, outlier_idx=[5, 20],
                                                    lags=6)
        assert np.all(contrib == 0.0)
        assert np.all(resto == 0.0)

    def test_la_identidad_CIERRA_exacta(self):
        """LA propiedad, y la que no se cumplía — BUG-0143.

            Σᵢ contrib[i,k] + resto[k]  ==  r_obs(k) − r_cal(k)

        Antes el reparto conservaba el denominador CONTAMINADO, así que sólo
        medía el canal del numerador y no sumaba nada en particular. Aquí las
        dos partes se calculan por caminos independientes —el reparto por su
        fórmula, la calibrada por `_acf_pacf`— y se exige que coincidan.
        """
        from art.describe import _acf_outlier_contributions, _sample_acf_raw
        from art.calibracion import _acf_pacf
        for semilla in range(8):
            g = np.random.default_rng(semilla)
            n = int(g.integers(50, 150))
            w = np.cumsum(g.standard_normal(n)) + g.standard_normal(n)
            w = (w - w.mean()) / w.std(ddof=0)
            for i in g.choice(n, size=int(g.integers(1, 5)), replace=False):
                w[i] += float(g.choice([-1, 1])) * g.uniform(4, 10)
            w = (w - w.mean()) / w.std(ddof=0)
            om = [i for i in range(n) if abs(w[i]) > 2.5]
            if not om:
                continue
            K = 12
            r_obs = _sample_acf_raw(w - w.mean(), K)
            r_cal, _ = _acf_pacf(w, K, omitir=set(om))
            contrib, resto = _acf_outlier_contributions(w, om, K)
            izq = contrib.sum(axis=0) + resto
            assert np.max(np.abs(izq - (r_obs - r_cal))) < 1e-12, \
                f"semilla {semilla}: la identidad no cierra"

    def test_el_canal_de_la_VARIANZA_esta_dentro(self):
        """El canal que faltaba, aislado.

        Un anómalo infla σ̂² y con ello hunde TODOS los r(k) hacia cero. Con el
        denominador contaminado ese canal no aparecía. Aquí se comprueba que el
        reparto lo incluye: el término de varianza vale −r_cal(k)·c_p²/D_m, y
        sin él la contribución sería la del numerador solo.
        """
        from art.describe import _acf_outlier_contributions
        from art.calibracion import _acf_pacf
        n, p, K = 120, 60, 8
        g = np.random.default_rng(4)
        w = g.standard_normal(n)
        w[p] += 9.0
        w = (w - w.mean()) / w.std(ddof=0)
        contrib, _resto = _acf_outlier_contributions(w, [p], K)
        r_cal, _ = _acf_pacf(w, K, omitir={p})
        ret = np.ones(n, bool); ret[p] = False
        c = w - w[ret].mean(); d_m = float(c @ c)
        for k in range(1, K + 1):
            A = 0.0
            if p + k < n and ret[p + k]:
                A += c[p] * c[p + k]
            if p - k >= 0 and ret[p - k]:
                A += c[p - k] * c[p]
            solo_numerador = A / d_m
            varianza = -r_cal[k - 1] * c[p] ** 2 / d_m
            assert contrib[0, k - 1] == pytest.approx(
                solo_numerador + varianza, abs=1e-12)
        # y el canal de la varianza NO es despreciable: con un anómalo de |z|=9
        # sobre n=120 se lleva una fracción apreciable de Σz²
        assert abs(c[p] ** 2 / d_m) > 0.05

    def test_dos_anomalos_a_distancia_k_fabrican_correlacion_en_el_retardo_k(self):
        """El canal de los PARES, que es lo que `resto` recoge.

        Dos anómalos del mismo signo separados k períodos fabrican correlación
        en el retardo k, y no es atribuible a ninguno de los dos por separado.
        Sobre `RATIO_m10` las obs. 71 y 75 —ambas de z≈−2,1, un año aparte—
        ponían **+0,055** en el retardo 4, que es el estacional.
        """
        from art.describe import _acf_outlier_contributions
        n, K = 120, 8
        w = np.random.default_rng(5).standard_normal(n) * 0.2
        w[40] += 8.0
        w[44] += 8.0          # cuatro períodos después, mismo signo
        w = (w - w.mean()) / w.std(ddof=0)
        _contrib, resto = _acf_outlier_contributions(w, [40, 44], K)
        assert resto[3] > 0.05, f"el par no aparece en el retardo 4: {resto}"
        otros = [abs(resto[k]) for k in range(K) if k != 3]
        assert resto[3] > 3 * max(otros), \
            f"el retardo 4 tiene que destacar: {resto}"


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
        # El rótulo va en inglés desde BUG-0139. Se acepta el viejo para que
        # esta prueba siga siendo legible al lado del defecto que documenta.
        if k.get("label", "").lower().startswith(("outlier contribution",
                                                  "contribución")):
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
