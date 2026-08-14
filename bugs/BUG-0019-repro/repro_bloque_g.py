#!/usr/bin/env python3
"""BUG-0019, second locus: the same prescription AFTER estimation.

BUG-0010 put the "MEG before pruning" warning in three places — the
over-parametrisation note, two tool docstrings, and ETAPA 4 of the
instructions. None of them is the `recommendation` field of
`describe_seasonal_params`, which is the sentence the analyst actually reads
under the chart.

This builds a series whose seasonality is MIXED BY CONSTRUCTION — deterministic
at f=1, stochastic at f=2 — fits the initial specification, and prints what art
recommends.

    python repro_bloque_g.py
"""
import warnings

import numpy as np

warnings.simplefilter("ignore")
import fue

n, s = 240, 12
rng = np.random.RandomState(20260814)
t = np.arange(1, n + 1)

# f=1 DETERMINISTIC: fixed amplitude, forever
det = 3.0 * np.cos(2 * np.pi * t / s) + 1.5 * np.sin(2 * np.pi * t / s)

# f=2 STOCHASTIC: integrated at that frequency, so the amplitude wanders
c2 = 2 * np.cos(2 * np.pi * 2 / s)
x2 = np.zeros(n)
u = rng.normal(0, 0.35, n)
for k in range(2, n):
    x2[k] = c2 * x2[k - 1] - x2[k - 2] + u[k]

y = 100 + det + x2 + rng.normal(0, 1.0, n)
ts = fue.TimeSeries(list(y), freq=s, start=(2000, 1), name="MIXTA")

interv = []
for f in range(1, 6):
    interv.append(fue.Intervention("cos", harmonic=float(f), omega=[0.1]))
    interv.append(fue.Intervention("sin", harmonic=float(f), omega=[0.1]))
interv.append(fue.Intervention("alter", omega=[0.1]))

# NOTE the AR(1): the natural specification here is ARMA(0,0) — harmonics and
# white noise — and building it through the Python API segfaults the C engine.
# That is fue/bugs/BUG-0013, found while writing this repro.
m = fue.Model(ts, d=0, interventions=interv, ar=[[0.3]], ar_free=[[True]],
              mu=float(y.mean()), estimate_mu=True)
m.fit()

from art.describe import describe_seasonal_params

d = describe_seasonal_params(m)

print("TRUTH OF THE SIMULATION: f=1 deterministic, f=2 STOCHASTIC, rest absent\n")
print("what art computes:")
for h in d.data["harmonics"]:
    tc = "     " if h["t_cos"] is None else f"{h['t_cos']:6.2f}"
    tsn = "     " if h["t_sin"] is None else f"{h['t_sin']:6.2f}"
    print(f"   k={h['k']}   t_cos={tc}   t_sin={tsn}")

print(f"\n   droppable_k = {d.data['droppable_k']}")
print(f"\nwhat art RECOMMENDS, on this model:\n   {d.recommendation}\n")

falla = []
if "MEG" not in d.recommendation:
    falla.append("the recommendation never mentions the MEG")
if not any(w in d.recommendation.lower()
           for w in ("adecuad", "diagnos", "residuo")):
    falla.append("it does not require the model to be adequate")
for f in falla:
    print(f"   ✗ {f}")
print("\n   The model above is NOT adequate: the stochastic seasonality at f=2")
print("   is unmodelled, so it sits in the residuals and inflates every")
print("   standard error. The recommendation is emitted anyway.")
