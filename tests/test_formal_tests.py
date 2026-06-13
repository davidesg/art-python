"""Tests for formal_tests.py — Shin-Fuller, DCD and RV tests."""
import os
import pytest
import fue
from art.formal_tests import shin_fuller, dcd, dcd_f, DCDResult, rv, RVResult, meg, MEGResult

# Paths to real-case test files (fue project)
_FUE_TESTS = os.path.expanduser(
    "~/Dropbox/SRC/atws/fue/fue/tests/real_cases/PRICES"
)
_PCE_MOD   = os.path.join(_FUE_TESTS, "PCE/Sample_1.2003_4.2019/Mod")
_IPC_TRIM  = os.path.join(_FUE_TESTS, "IPC/Trimestral/Sample_1.2003_4.2019/Mod")


def _skip_if_missing(path):
    if not os.path.exists(path):
        pytest.skip(f"test data not found: {path}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_and_fit(inp_path):
    _skip_if_missing(inp_path)
    ts, m = fue.inp.load(inp_path)
    m.fit()
    return m


# ---------------------------------------------------------------------------
# phi_null formula
# ---------------------------------------------------------------------------

def test_phi_null_quarterly_68():
    """phi_null = 1 - s/n = 1 - 4/68 = 64/68 = 16/17 ≈ 0.941176."""
    m = _load_and_fit(os.path.join(_PCE_MOD, "R.1.inp"))
    result = shin_fuller(m)
    assert result.n == 68
    assert result.s == 4
    assert abs(result.phi_null - (1 - 4 / 68)) < 1e-10
    assert abs(result.phi_null - 16 / 17) < 1e-6


# ---------------------------------------------------------------------------
# PCE R.1: no harmonics, AR(1) free → SF/R.1 comparison
# ---------------------------------------------------------------------------

class TestPCE_R1:
    """PCE R.1 (no harmonics, free AR) vs SF/R.1 (AR fixed at phi_null)."""

    @pytest.fixture(autouse=True)
    def model(self):
        self.m = _load_and_fit(os.path.join(_PCE_MOD, "R.1.inp"))
        self.result = shin_fuller(self.m)

    def test_lr_matches_reference(self):
        """LR ≈ 19.94 (2 × [−108.234 − (−118.203)])."""
        assert abs(self.result.lr - 19.937) < 0.01

    def test_loglik_free(self):
        assert abs(self.result.loglik_free - (-108.234)) < 0.01

    def test_loglik_constrained(self):
        """Constrained loglik must match SF/R.1.out: −118.2027."""
        assert abs(self.result.loglik_constrained - (-118.203)) < 0.01

    def test_pvalue_small(self):
        assert self.result.pvalue < 0.001

    def test_stationary(self):
        assert self.result.stationary is True

    def test_df(self):
        assert self.result.df == 1

    def test_phi_free_positive(self):
        assert len(self.result.phi_free) == 1
        assert self.result.phi_free[0] > 0


# ---------------------------------------------------------------------------
# IPC Trimestral R.2: harmonics + AR(1) free → SF/R.2 comparison
# ---------------------------------------------------------------------------

class TestIPC_Trim_R2:
    """IPC Trim R.2 (harmonics + free AR) vs SF/R.2 (AR fixed at phi_null)."""

    @pytest.fixture(autouse=True)
    def model(self):
        self.m = _load_and_fit(os.path.join(_IPC_TRIM, "R.2.inp"))
        self.result = shin_fuller(self.m)

    def test_lr_matches_reference(self):
        """LR ≈ 16.02 (2 × [−72.297 − (−80.309)])."""
        assert abs(self.result.lr - 16.023) < 0.01

    def test_loglik_free(self):
        assert abs(self.result.loglik_free - (-72.297)) < 0.01

    def test_loglik_constrained(self):
        """Constrained loglik must match SF/R.2.out: −80.3087."""
        assert abs(self.result.loglik_constrained - (-80.309)) < 0.01

    def test_stationary(self):
        assert self.result.stationary is True

    def test_df(self):
        assert self.result.df == 1


# ---------------------------------------------------------------------------
# API / error handling
# ---------------------------------------------------------------------------

def test_raises_without_fit():
    """shin_fuller must raise if model not fitted."""
    _skip_if_missing(os.path.join(_PCE_MOD, "R.1.inp"))
    ts, m = fue.inp.load(os.path.join(_PCE_MOD, "R.1.inp"))
    with pytest.raises(RuntimeError, match="not been fitted"):
        shin_fuller(m)


def test_raises_no_ar():
    """shin_fuller must raise if model has no free AR parameters."""
    _skip_if_missing(os.path.join(_PCE_MOD, "PE.1.inp"))
    m = _load_and_fit(os.path.join(_PCE_MOD, "PE.1.inp"))
    # PE.1 has AR fixed at 0 (ar_free = [[False]])
    with pytest.raises(ValueError, match="No free regular AR"):
        shin_fuller(m)


def test_summary_string():
    """summary() returns a non-empty string with key labels."""
    m = _load_and_fit(os.path.join(_PCE_MOD, "R.1.inp"))
    s = shin_fuller(m).summary()
    assert "Shin-Fuller" in s
    assert "LR" in s
    assert "ESTACIONARIO" in s or "RAÍZ" in s


# ===========================================================================
# DCD non-invertibility test
# ===========================================================================

_COLOMBIA_GUION = os.path.expanduser(
    "~/Documents/Documentos/Tesis/Analisis/Colombia/"
    "ipc/mensuales/analisis/muestra_1.89_12.01/guion1"
)
_PO3_INP = os.path.join(_COLOMBIA_GUION, "PO3.inp")


def _skip_if_no_colombia(path=_PO3_INP):
    if not os.path.exists(path):
        pytest.skip(f"Colombia thesis data not found: {path}")


# ---------------------------------------------------------------------------
# PO3: ARMA model with MA(1) θ≈0.827 — strongly rejects H₀: θ=1
# Thesis guion: DCD(122.0) without overfit, DCD(26.6) with AR(1) overfit.
# fue-Python gives ≈126.8 (fue C vs Python numerical difference ≈4%).
# ---------------------------------------------------------------------------

class TestDCD_PO3:
    """Colombia PO3 model: MA(1) θ≈0.827 should strongly reject H₀: θ=1."""

    @pytest.fixture(autouse=True)
    def model(self):
        _skip_if_no_colombia()
        ts, m = fue.inp.load(_PO3_INP)
        m.fit()
        self.m = m
        self.results = dcd(m)

    def test_returns_one_result(self):
        assert len(self.results) == 1

    def test_result_type(self):
        assert isinstance(self.results[0], DCDResult)

    def test_freq_is_none(self):
        """Regular MA has freq=None."""
        assert self.results[0].freq is None

    def test_factor_index(self):
        assert self.results[0].factor_index == 0

    def test_coef_free_near_0827(self):
        """Estimated MA coefficient should be close to 0.827."""
        assert abs(self.results[0].coef_free - 0.827) < 0.01

    def test_coef_null_is_one(self):
        assert self.results[0].coef_null == 1.0

    def test_lr_strongly_rejects(self):
        """LR >> 4.41 (1% critical value); thesis says ≈122, fue-py ≈127."""
        assert self.results[0].lr > 100.0

    def test_loglik_free(self):
        assert abs(self.results[0].loglik_free - (-47.888)) < 0.01

    def test_loglik_constrained_lower(self):
        """Constrained loglik must be lower (more negative) than free."""
        assert self.results[0].loglik_constrained < self.results[0].loglik_free

    def test_rejects_1pct(self):
        assert self.results[0].rejects_1pct is True

    def test_invertible(self):
        assert self.results[0].invertible is True

    def test_summary_contains_key_labels(self):
        s = self.results[0].summary()
        assert "DCD" in s
        assert "LR" in s
        assert "INVERTIBLE" in s


# ---------------------------------------------------------------------------
# API / error handling
# ---------------------------------------------------------------------------

def test_dcd_raises_without_fit():
    """dcd must raise if model not fitted."""
    _skip_if_no_colombia()
    ts, m = fue.inp.load(_PO3_INP)
    with pytest.raises(RuntimeError, match="not been fitted"):
        dcd(m)


def test_dcd_raises_no_ma():
    """dcd must raise if model has no regular MA factors."""
    _skip_if_missing(os.path.join(_PCE_MOD, "R.1.inp"))
    m = _load_and_fit(os.path.join(_PCE_MOD, "R.1.inp"))
    # PCE R.1 has AR but no MA
    with pytest.raises(ValueError, match="No free regular MA"):
        dcd(m)


def test_dcd_raises_fixed_ma():
    """dcd must raise if all MA factors are already fixed."""
    _skip_if_no_colombia()
    ts, m = fue.inp.load(_PO3_INP)
    m.ma_free = [[False]]
    m.fit()
    with pytest.raises(ValueError, match="No free regular MA"):
        dcd(m)


# ===========================================================================
# DCD_f — fixed-frequency MA non-invertibility test
# ===========================================================================

_IPC_MENSUAL = os.path.join(_FUE_TESTS, "IPC/Mensual/sample_1.2002_12.2007")
_RIPC1_INP   = os.path.join(_IPC_MENSUAL, "RIPC.1.inp")


def _skip_if_no_ripc1(path=_RIPC1_INP):
    if not os.path.exists(path):
        pytest.skip(f"IPC mensual data not found: {path}")


def _force_fit_py(model):
    """Fit model in-place using pure-Python estimator; skip on failure."""
    from fue.cast_us import estimate_py
    from fue.model import FitResult
    raw = estimate_py(model)
    model._result = FitResult(raw)
    if not model._result.converged:
        pytest.skip(f"Pure-Python estimation failed: ifault={model._result.ifault}")
    return model


# ---------------------------------------------------------------------------
# Functional test: IPC mensual data + MA_f(freq=6) — semiannual component
# Uses estimate_py for the initial fit (no C backend needed).
# ---------------------------------------------------------------------------

class TestDCDF_MensualMAf:
    """dcd_f on a monthly IPC model with a free MA_f at freq=6."""

    @pytest.fixture(autouse=True)
    def model(self):
        _skip_if_no_ripc1()
        ts, _ = fue.inp.load(_RIPC1_INP)
        # Minimal model: d=1, one free MA_f at the semiannual frequency
        m = fue.Model(ts, d=1, ma_f=[fue.FixedFreqFactor(freq=6, coef=-0.5)])
        _force_fit_py(m)
        self.m = m
        self.results = dcd_f(m)

    def test_returns_one_result(self):
        assert len(self.results) == 1

    def test_result_type(self):
        assert isinstance(self.results[0], DCDResult)

    def test_freq(self):
        assert self.results[0].freq == 6.0

    def test_factor_index(self):
        assert self.results[0].factor_index == 0

    def test_coef_null(self):
        assert self.results[0].coef_null == -1.0

    def test_coef_free_negative(self):
        """Estimated MA_f coef must be negative (FixedFreqFactor constraint)."""
        assert self.results[0].coef_free < 0.0

    def test_lr_nonnegative(self):
        """LR ≥ 0: free model cannot have lower loglik than constrained."""
        assert self.results[0].lr >= -1e-6

    def test_loglik_free_geq_constrained(self):
        assert self.results[0].loglik_free >= self.results[0].loglik_constrained - 1e-6

    def test_summary_contains_key_labels(self):
        s = self.results[0].summary()
        assert "DCD" in s
        assert "LR" in s


# ---------------------------------------------------------------------------
# API / error handling
# ---------------------------------------------------------------------------

def test_dcd_f_raises_without_fit():
    """dcd_f must raise if model not fitted."""
    _skip_if_no_ripc1()
    ts, _ = fue.inp.load(_RIPC1_INP)
    m = fue.Model(ts, d=1, ma_f=[fue.FixedFreqFactor(freq=6, coef=-0.5)])
    with pytest.raises(RuntimeError, match="not been fitted"):
        dcd_f(m)


def test_dcd_f_raises_no_ma_f():
    """dcd_f must raise if model has no MA_f factors."""
    _skip_if_missing(os.path.join(_PCE_MOD, "R.1.inp"))
    m = _load_and_fit(os.path.join(_PCE_MOD, "R.1.inp"))
    with pytest.raises(ValueError, match="No free MA_f"):
        dcd_f(m)


def test_dcd_f_raises_fixed_ma_f():
    """dcd_f must raise if all MA_f factors are already fixed."""
    _skip_if_no_ripc1()
    ts, _ = fue.inp.load(_RIPC1_INP)
    m = fue.Model(ts, d=1, ma_f=[fue.FixedFreqFactor(freq=6, coef=-0.5, free=False)])
    _force_fit_py(m)
    with pytest.raises(ValueError, match="No free MA_f"):
        dcd_f(m)


# ===========================================================================
# Chile IPC tests — muestra 1.1986–12.2001 (guion3 models)
# Series: 100·ln(IPC), n=192, monthly. Reference: thesis graficos_chile.pdf.
# ===========================================================================

_CHILE_GUION3 = os.path.expanduser(
    "~/Documents/Documentos/Tesis/Analisis/"
    "Chile/ipc/mensuales/analisis/muestra_1.86_12.01/guion3"
)
_PC6_INP = os.path.join(_CHILE_GUION3, "PC6.inp")
_PC7_INP = os.path.join(_CHILE_GUION3, "PC7.inp")


def _skip_if_no_chile(path=_PC6_INP):
    if not os.path.exists(path):
        pytest.skip(f"Chile thesis data not found: {path}")


# ---------------------------------------------------------------------------
# PC6 (≈APC6): MA(1) θ≈0.78, d=2, no seasonal diff, with deterministic
# harmonics + pulse intervention (Gulf War 9/1990). σ≈0.46%.
# DCD must strongly reject H₀: θ=1 — MA is far from unit root.
# ---------------------------------------------------------------------------

class TestDCD_ChilePC6:
    """Chile IPC PC6: pure MA(1) d=2 — non-invertibility strongly rejected."""

    @pytest.fixture(autouse=True)
    def model(self):
        _skip_if_no_chile(_PC6_INP)
        ts, m = fue.inp.load(_PC6_INP)
        _force_fit_py(m)
        self.m = m
        self.results = dcd(m)

    def test_returns_one_result(self):
        assert len(self.results) == 1

    def test_result_type(self):
        assert isinstance(self.results[0], DCDResult)

    def test_freq_is_none(self):
        assert self.results[0].freq is None

    def test_factor_index(self):
        assert self.results[0].factor_index == 0

    def test_coef_free_near_078(self):
        """Estimated θ ≈ 0.783, well below the unit root."""
        assert abs(self.results[0].coef_free - 0.783) < 0.01

    def test_coef_null_is_one(self):
        assert self.results[0].coef_null == 1.0

    def test_lr_strongly_rejects(self):
        """LR ≈ 149.6 >> 4.41 (1% critical value)."""
        assert self.results[0].lr > 100.0

    def test_loglik_free(self):
        assert abs(self.results[0].loglik_free - (-121.249)) < 0.01

    def test_loglik_constrained_lower(self):
        assert self.results[0].loglik_constrained < self.results[0].loglik_free

    def test_rejects_1pct(self):
        assert self.results[0].rejects_1pct is True

    def test_invertible(self):
        assert self.results[0].invertible is True

    def test_summary(self):
        s = self.results[0].summary()
        assert "DCD" in s and "LR" in s and "INVERTIBLE" in s


# ---------------------------------------------------------------------------
# PC7 (≈APC7): MA(1) + MA_f(freq=1), ifadf includes annual freq=1.
# ∇²·(1−√3B+B²)·N_t = (1−θB)·(1−λ√(−c)·√3·B − c·B²)·ε_t
# DCD (regular MA): strongly rejects (θ≈0.80, LR≈152).
# DCD_f (annual MA_f): borderline — rejects at 5% but NOT 1% (LR≈4.32).
# This borderline result confirms annual seasonality is near-stochastic.
# ---------------------------------------------------------------------------

class TestDCDF_ChilePC7:
    """Chile IPC PC7: MA(1) + annual MA_f (freq=1). DCD_f borderline case."""

    @pytest.fixture(autouse=True)
    def model(self):
        _skip_if_no_chile(_PC7_INP)
        ts, m = fue.inp.load(_PC7_INP)
        _force_fit_py(m)
        self.m = m
        self.dcd_results = dcd(m)
        self.dcd_f_results = dcd_f(m)

    # --- regular MA (DCD) ---

    def test_dcd_returns_one(self):
        assert len(self.dcd_results) == 1

    def test_dcd_coef_near_080(self):
        assert abs(self.dcd_results[0].coef_free - 0.796) < 0.01

    def test_dcd_lr_strongly_rejects(self):
        """LR ≈ 152: regular MA strongly invertible."""
        assert self.dcd_results[0].lr > 100.0

    def test_dcd_loglik_free(self):
        assert abs(self.dcd_results[0].loglik_free - (-125.584)) < 0.01

    def test_dcd_rejects_1pct(self):
        assert self.dcd_results[0].rejects_1pct is True

    # --- annual MA_f (DCD_f) ---

    def test_dcd_f_returns_one(self):
        assert len(self.dcd_f_results) == 1

    def test_dcd_f_freq(self):
        assert self.dcd_f_results[0].freq == 1.0

    def test_dcd_f_factor_index(self):
        assert self.dcd_f_results[0].factor_index == 0

    def test_dcd_f_coef_free_near_neg091(self):
        """Annual MA_f coef ≈ -0.915: close to unit root -1."""
        assert abs(self.dcd_f_results[0].coef_free - (-0.915)) < 0.01

    def test_dcd_f_coef_null(self):
        assert self.dcd_f_results[0].coef_null == -1.0

    def test_dcd_f_lr_near_432(self):
        """LR ≈ 4.32: between 5% (2.02) and 1% (4.52) critical values."""
        assert abs(self.dcd_f_results[0].lr - 4.316) < 0.1

    def test_dcd_f_loglik_free(self):
        assert abs(self.dcd_f_results[0].loglik_free - (-125.584)) < 0.01

    def test_dcd_f_loglik_constrained(self):
        assert abs(self.dcd_f_results[0].loglik_constrained - (-127.742)) < 0.01

    def test_dcd_f_rejects_5pct(self):
        """Rejects at 5%: annual MA_f is not at unit root."""
        assert self.dcd_f_results[0].rejects_5pct is True

    def test_dcd_f_not_rejects_1pct(self):
        """Does NOT reject at 1%: borderline annual MA_f."""
        assert self.dcd_f_results[0].rejects_1pct is False

    def test_dcd_f_invertible(self):
        assert self.dcd_f_results[0].invertible is True

    def test_dcd_f_summary(self):
        s = self.dcd_f_results[0].summary()
        assert "DCD" in s and "LR" in s


# ===========================================================================
# RV fixed-frequency test — USA Monetary Base M1 (M1.5 model)
# ===========================================================================
# M1.5: AR(2) libre con raíces complejas, f̂≈3.91 (mensual, s=12).
# Datos: USA M1 monthly, d=2, D=1, n=204, 1.1991–12.2007.
# Referencia: thesis Analisis/eeuu/monetarios/m1/muestra_1.91_1.08/
# ===========================================================================

_USA_M1 = os.path.expanduser(
    "~/Documents/Documentos/Tesis/Analisis/"
    "eeuu/monetarios/m1/muestra_1.91_1.08"
)
_M15_INP = os.path.join(_USA_M1, "M1.5.inp")


def _skip_if_no_m15(path=_M15_INP):
    if not os.path.exists(path):
        pytest.skip(f"USA M1 thesis data not found: {path}")


# ---------------------------------------------------------------------------
# M1.5: AR(2) libre, φ̂₁≈−0.538, φ̂₂≈−0.345, f̂≈3.91
# H₀: f=4 → no rechaza (LR≈0.49, p≈0.48)
# H₀: f=2 → rechaza fuertemente (LR≈57.2)
# ---------------------------------------------------------------------------

class TestRV_M15:
    """USA M1 M1.5: AR(2) libre con raíces complejas en f̂≈3.91 ≈ harmónico 4."""

    @pytest.fixture(autouse=True)
    def model(self):
        _skip_if_no_m15()
        ts, m = fue.inp.load(_M15_INP)
        _force_fit_py(m)
        self.m = m
        self.r4 = rv(m, freq_null=4)[0]   # H₀: f=4
        self.r2 = rv(m, freq_null=2)[0]   # H₀: f=2 (control: rechaza)

    # --- estructura del resultado ---

    def test_result_type(self):
        assert isinstance(self.r4, RVResult)

    def test_ar_factor_index(self):
        assert self.r4.ar_factor_index == 0

    def test_freq_estimated_near_391(self):
        """Frecuencia estimada ≈ 3.91 (entre armónicos 3 y 4)."""
        assert abs(self.r4.freq_estimated - 3.907) < 0.01

    def test_phi1_near_neg054(self):
        assert abs(self.r4.phi1 - (-0.5375)) < 0.005

    def test_phi2_near_neg035(self):
        assert abs(self.r4.phi2 - (-0.3452)) < 0.005

    def test_rho_near_059(self):
        assert abs(self.r4.rho - 0.5876) < 0.005

    def test_loglik_free(self):
        assert abs(self.r4.loglik_free - (-211.035)) < 0.01

    # --- H₀: f=4 → no rechaza ---

    def test_freq_null_4(self):
        assert self.r4.freq_null == 4

    def test_lr_near_049(self):
        """LR ≈ 0.49 << 3.84 (χ²₀.₀₅): compatible con f=4."""
        assert self.r4.lr < 2.0

    def test_pvalue_high(self):
        assert self.r4.pvalue > 0.4

    def test_not_rejects_5pct(self):
        assert self.r4.rejects_5pct is False

    def test_fixed_frequency(self):
        assert self.r4.fixed_frequency is True

    def test_loglik_constrained_near_free(self):
        """Constrained loglik casi igual al libre (f≈4 ajusta bien)."""
        assert abs(self.r4.loglik_constrained - self.r4.loglik_free) < 1.0

    # --- H₀: f=2 → rechaza fuertemente ---

    def test_r2_freq_null(self):
        assert self.r2.freq_null == 2

    def test_r2_lr_large(self):
        """LR ≈ 57 >> 3.84: f=2 es incompatible con f̂≈3.91."""
        assert self.r2.lr > 30.0

    def test_r2_rejects_1pct(self):
        assert self.r2.rejects_1pct is True

    def test_r2_not_fixed_frequency(self):
        assert self.r2.fixed_frequency is False

    # --- summary ---

    def test_summary_contains_key_labels(self):
        s = self.r4.summary()
        assert "RV" in s and "LR" in s and "FRECUENCIA FIJA" in s


# ---------------------------------------------------------------------------
# rv() — test all harmonics at once (freq_null=None)
# ---------------------------------------------------------------------------

def test_rv_all_harmonics():
    """rv(freq_null=None) returns one result per harmonic k=1..s//2."""
    _skip_if_no_m15()
    ts, m = fue.inp.load(_M15_INP)
    _force_fit_py(m)
    results = rv(m)
    s = m.series.freq
    assert len(results) == s // 2
    # Only k=4 should not be rejected
    not_rejected = [r for r in results if not r.rejects_5pct]
    assert any(r.freq_null == 4 for r in not_rejected)


# ---------------------------------------------------------------------------
# API / error handling
# ---------------------------------------------------------------------------

def test_rv_raises_without_fit():
    _skip_if_no_m15()
    ts, m = fue.inp.load(_M15_INP)
    with pytest.raises(RuntimeError, match="not been fitted"):
        rv(m)


def test_rv_raises_no_ar():
    _skip_if_no_m15()
    ts, m = fue.inp.load(_M15_INP)
    m.ar = []
    m.ar_free = None
    _force_fit_py(m)
    with pytest.raises(ValueError, match="no regular AR"):
        rv(m)


def test_rv_raises_ar1_not_ar2():
    """rv must raise if the AR factor has order 1, not 2."""
    _skip_if_missing(os.path.join(_PCE_MOD, "R.1.inp"))
    m = _load_and_fit(os.path.join(_PCE_MOD, "R.1.inp"))
    with pytest.raises(ValueError, match="order 1, not 2"):
        rv(m)


def test_rv_raises_fixed_ar2():
    """rv must raise if AR(2) has no free coefficients."""
    _skip_if_no_m15()
    ts, m = fue.inp.load(_M15_INP)
    m.ar_free = [[False, False]]   # both fixed → 0 free params
    _force_fit_py(m)
    with pytest.raises(ValueError, match="free coefficient"):
        rv(m)


# ===========================================================================
# MEG stochastic seasonality evaluation — Chile IPC (guion3)
# ===========================================================================
# Base model: PC6 (all deterministic harmonics, d=2, no ifadf, no MA_f).
# MEG at freq=1: augments to PC7-equivalent, applies DCD_f.
# Expected: MA_f coef ≈ -0.915, LR ≈ 4.32, rejects at 5% → stochastic.
# ===========================================================================


class TestMEG_ChilePC6_Freq1:
    """MEG on Chile PC6 at freq=1 should reproduce PC7 DCD_f results."""

    @pytest.fixture(autouse=True)
    def model(self):
        _skip_if_no_chile(_PC6_INP)
        ts, m = fue.inp.load(_PC6_INP)
        _force_fit_py(m)
        self.m = m
        self.results = meg(m, frequencies=[1])

    def test_returns_one_result(self):
        assert len(self.results) == 1

    def test_result_type(self):
        assert isinstance(self.results[0], MEGResult)

    def test_freq(self):
        assert self.results[0].freq == 1

    def test_status_stochastic(self):
        """DCD_f rejects at 5%: annual seasonality is stochastic."""
        assert self.results[0].status == 'stochastic'

    def test_stochastic_property(self):
        assert self.results[0].stochastic is True

    def test_deterministic_property(self):
        assert self.results[0].deterministic is False

    def test_coef_near_neg091(self):
        """MA_f testigo coef ≈ -0.915 (same as PC7 DCD_f free model)."""
        assert abs(self.results[0].coef_ma_f - (-0.915)) < 0.02

    def test_dcd_result_not_none(self):
        assert self.results[0].dcd_result is not None

    def test_lr_near_432(self):
        """LR ≈ 4.32: between 5% (2.02) and 1% (4.52) critical values."""
        assert abs(self.results[0].dcd_result.lr - 4.316) < 0.2

    def test_dcd_rejects_5pct(self):
        assert self.results[0].dcd_result.rejects_5pct is True

    def test_dcd_not_rejects_1pct(self):
        assert self.results[0].dcd_result.rejects_1pct is False

    def test_loglik_free_matches_pc7(self):
        """Augmented free model loglik ≈ -125.584 (same as PC7)."""
        assert abs(self.results[0].dcd_result.loglik_free - (-125.584)) < 0.01

    def test_summary_contains_key_labels(self):
        s = self.results[0].summary()
        assert "MEG" in s and "freq=1" in s and "ESTOCÁSTICA" in s


# ---------------------------------------------------------------------------
# MEG all harmonics (default frequencies)
# ---------------------------------------------------------------------------

def test_meg_all_harmonics_chile_pc6():
    """meg(freq=None) returns s//2-1=5 results for monthly PC6."""
    _skip_if_no_chile()
    ts, m = fue.inp.load(_PC6_INP)
    _force_fit_py(m)
    results = meg(m)
    s = m.series.freq
    assert len(results) == s // 2 - 1          # 5 for monthly
    assert [r.freq for r in results] == list(range(1, s // 2))
    # freq=1 must be stochastic (confirmed by PC7)
    assert results[0].status == 'stochastic'
    # all results must not be ambiguous
    assert all(r.status != 'ambiguous' for r in results)


# ---------------------------------------------------------------------------
# API / error handling
# ---------------------------------------------------------------------------

def test_meg_raises_without_fit():
    """meg must raise if model not fitted."""
    _skip_if_no_chile()
    ts, m = fue.inp.load(_PC6_INP)
    with pytest.raises(RuntimeError, match="not been fitted"):
        meg(m)


def test_meg_raises_freq_already_stochastic():
    """meg must raise if the requested frequency is already stochastic."""
    _skip_if_no_chile(_PC7_INP)
    ts, m = fue.inp.load(_PC7_INP)
    _force_fit_py(m)
    # PC7 has ifadf[1]=1 — freq=1 is already stochastic
    with pytest.raises(ValueError, match="already stochastic"):
        meg(m, frequencies=[1])


def test_meg_raises_freq_out_of_range():
    """meg must raise if a requested frequency exceeds s//2."""
    _skip_if_no_chile()
    ts, m = fue.inp.load(_PC6_INP)
    _force_fit_py(m)
    with pytest.raises(ValueError, match="out of range"):
        meg(m, frequencies=[7])   # s//2=6, 7 is invalid
