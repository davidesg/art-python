"""BUG-0007 reproduction — `update_and_forecast` rebuilds the fuf model with
`_fue.Model(...)` and does not pass `refactor` (fue default 1.0, fuf models carry
100.0). `mu0` lives in the rescaled space, so the rebuilt model reads the drift 100x
off and the forecast LEVEL EXPLODES: FR_CPI (index ~107) goes to 1031.97 at h=24.

Only models with a mean are affected: with mu0 = 0 there is no drift to mis-scale.

Run from this folder:  python repro.py
Needs: fue (any version -- this is an ART-side defect, not a fue regression).

FR_CPI.fuf.inp is the French HICP (monthly, 2002:01-2019:12, n=216) with the SF_MEG
deterministic baseline (5 harmonic pairs + Nyquist + AR(1)_12 + mu), horizon 24, so
the repro is self-contained. NEW is the realised 2020:01-2021:12, i.e. exactly what an
`update_and_forecast(fuf, new_values=NEW)` call appends.
"""
import numpy as np
import fue

# realised FR_CPI, 2020:01 - 2021:12 (the 24 observations to append)
NEW = [103.94, 103.93, 103.85, 103.81, 103.95, 104.04, 104.44, 104.34, 103.80,
       103.75, 103.86, 104.09, 104.24, 104.24, 104.89, 105.00, 105.34, 105.48,
       105.55, 106.21, 105.97, 106.42, 106.82, 107.03]
# realised 2022:01 - 2023:12, for reference only (what the updated forecast aims at)
ACTUAL = {1: 107.30, 12: 113.42, 24: 117.50}

ts_old, m_old = fue.load_fuf("FR_CPI.fuf.inp")
import inspect
print("Model.__init__ refactor default =",
      inspect.signature(fue.Model.__init__).parameters["refactor"].default)
print(f"fuf model: refactor = {m_old.refactor}   mu0 = {m_old.mu0:.6f}\n")

ts_new = fue.TimeSeries(list(ts_old.data) + NEW, freq=ts_old.freq,
                        start=ts_old.start, name=ts_old.name)

# exactly the field list of art.mcp_server.update_and_forecast (v0.1.3)
FIELDS = dict(
    ar=m_old.ar, ar_free=m_old.ar_free, ma=m_old.ma, ma_free=m_old.ma_free,
    ar_s=m_old.ar_s, ar_s_free=m_old.ar_s_free, ma_s=m_old.ma_s, ma_s_free=m_old.ma_s_free,
    ar_f=m_old.ar_f, ma_f=m_old.ma_f, d=m_old.d, D=m_old.D, ifadf=m_old.ifadf,
    interventions=m_old.interventions, mu=m_old.mu0, estimate_mu=m_old.estimate_mu,
    boxlam=m_old.boxlam,
)

for label, extra in (("as update_and_forecast does (no refactor)", {}),
                     ("+ refactor=m_old.refactor", {"refactor": m_old.refactor})):
    m = fue.Model(ts_new, **FIELDS, **extra)
    lv = np.asarray(m.forecast_fuf(horizon=24, sigma2=m_old._fuf_sigma2).level,
                    float).ravel()
    print(f"  {label:42s} refactor={m.refactor:>5} -> "
          f"h=1 {lv[0]:8.2f}  h=12 {lv[11]:8.2f}  h=24 {lv[23]:8.2f}")

print(f"  {'actual':42s} {'':>15} -> "
      f"h=1 {ACTUAL[1]:8.2f}  h=12 {ACTUAL[12]:8.2f}  h=24 {ACTUAL[24]:8.2f}")
