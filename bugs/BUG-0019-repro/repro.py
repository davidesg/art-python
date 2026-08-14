"""BUG-0019 — `describe_seasonality` PRESCRIBES pruning the seasonal harmonics from a
per-frequency HAC test computed with NO MODEL AT ALL, at the guided node where the
analyst is choosing the harmonic set.

Step 3 of `guided_identification` runs the HAC seasonality test on the differenced
series -- there is no ARMA yet, no mu, nothing estimated -- and prints

    - Frecuencias significativas: f=1 (...), f=2 (...), f=3 (...), f=4 (...), f=6 (...)

    **Decision B1 -- deterministic seasonality (recommended starting point).**
    - D=0, with cos/sin harmonics FOR EACH SIGNIFICANT FREQUENCY.

That second line is an instruction, and read literally it says: build the model with
harmonics at {1,2,3,4,6} and none at f=5. Meanwhile the code block printed a few lines
below in the same output recommends `n_harmonics=5` -- the FULL set -- because
`mcp_server.py:1907` computes it as `freq // 2 - 1`, with no reference to significance.
One screen, two contradictory instructions, and the wrong one is the one in prose.

Two things are wrong with the prescribed prune, and they compound:

1. THE CRITERION IS NOT AVAILABLE YET. At this node nothing has been estimated. Any
   significance statement about the harmonics belongs to a model that does not exist.
   The one model the analyst can build here is m00 (harmonics only, no ARMA, no mu),
   which is NOT adequate -- its residuals carry the whole regular AR(1) -- so its
   standard errors are inflated by the unmodelled dynamics.

2. LOW AMPLITUDE IS NOT ABSENCE. A fixed-coefficient harmonic fitted to a frequency
   whose amplitude wanders averages toward zero, so a low t at f is evidence FOR
   stochastic seasonality at f. And the MEG's null model IS the deterministic harmonic
   at f: prune it and the frequency becomes untestable. BUG-0010 established this and
   fixed the guidance at ETAPA 4 and in the pruning tools -- but every one of those
   fixes lives DOWNSTREAM of estimation. None of them reaches this node, which is
   upstream of the first `.pre`, and which prescribes the prune in its own words.

On IPC_ES the two defects meet on the frequency that carries the case's entire result.

Run:  python repro.py
"""
import os

import fue

from art.describe import describe_seasonality

HERE = os.path.dirname(os.path.abspath(__file__))

LABELS = {1: "cos1", 2: "sin1", 3: "cos2", 4: "sin2", 5: "cos3", 6: "sin3",
          7: "cos4", 8: "sin4", 9: "cos5", 10: "sin5", 11: "alter(f=6)"}
FREQ_OF = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3, 7: 4, 8: 4, 9: 5, 10: 5, 11: 6}


def load(name):
    """Estimate from the .inp (neutral seeds) -- NEVER from a .pre.

    Starting at the optimum leaves the optimizer no path and the accumulated
    covariance comes out mis-scaled: on this very model the harmonic standard
    errors inflate by up to 4.4x. Point estimates and the likelihood are
    unaffected, but every t-ratio below would be wrong.
    """
    ts, model = fue.load(os.path.join(HERE, name))
    model.fit()
    return ts, model


def t_ratios(model):
    """|t| of each deterministic (omega) coefficient, in .out print order."""
    est, se = model.params, model.std_errors
    return [est[i] / se[i] for i in range(len(LABELS))]


print(__doc__.split("Run:")[0])

# ---------------------------------------------------------------- PART 1
print("=" * 78)
print("PART 1 -- what the guided node prints, with nothing estimated")
print("=" * 78)

ts, _ = load("IPC_ES_m10.inp")
desc = describe_seasonality(ts)
text = desc.summary   # NOT str(desc): that carries the base64 figure too

for line in text.splitlines():
    if ("Frecuencias significativas" in line
            or "frecuencia significativa" in line
            or "F-test HAC" in line):
        print("   ", line.strip())

print()
print("    -> f=5 is absent from the list, and the line below it says to put a")
print("       harmonic on each SIGNIFICANT frequency. Read literally: drop f=5.")
print("    -> the code block in the same output says n_harmonics=5 (mcp_server.py:1907,")
print("       `freq // 2 - 1`), which contradicts it. Nothing has been estimated yet.")

# ---------------------------------------------------------------- PART 2
print()
print("=" * 78)
print("PART 2 -- the criterion is not stable: inadequate model vs adequate model")
print("=" * 78)

_, m00 = load("IPC_ES_m00.inp")   # harmonics only: no ARMA, no mu -- NOT adequate
_, m10 = load("IPC_ES_m10.inp")   # AR(1) + mu -- the adequate model of the case

t00, t10 = t_ratios(m00), t_ratios(m10)

print(f"    {'':12} {'m00 (no ARMA)':>16} {'m10 (adequate)':>18}")
print(f"    {'':12} {'INADEQUATE':>16} {'':>18}")
flips = []
for i, lab in LABELS.items():
    a, b = t00[i - 1], t10[i - 1]
    va = "keep " if abs(a) > 2 else "PRUNE"
    vb = "keep " if abs(b) > 2 else "prune"
    mark = ""
    if va.strip().lower() != vb.strip().lower():
        mark = "   <<< VERDICT FLIPS"
        flips.append((lab, FREQ_OF[i], a, b))
    print(f"    {lab:12} t={a:7.2f} ({va})   t={b:7.2f} ({vb}){mark}")

print()
print(f"    sigma^2:  m00 = {m00._result.sigma2:.4f}   m10 = {m10._result.sigma2:.4f}"
      f"   ({100 * (1 - m10._result.sigma2 / m00._result.sigma2):.0f} % absorbed by the AR(1))")
print("    The unmodelled AR(1) inflates every standard error, so the pruning filter")
print("    applied at this node is systematically more aggressive than on the model")
print("    the analyst would actually keep.")

# ---------------------------------------------------------------- PART 3
print()
print("=" * 78)
print("PART 3 -- what the prescribed prune costs, on this series")
print("=" * 78)

for lab, f, a, b in flips:
    print(f"    {lab} (frequency f={f}): |t| = {abs(a):.2f} on the inadequate model")
    print(f"    -> PRUNE, but {abs(b):.2f} on the adequate one -> keep.")

print()
print("    f=3 is the frequency the MEG declares STOCHASTIC on this series")
print("    (LR = 2.304 against a 2.07 critical value at n=216) -- the ONLY")
print("    non-deterministic frequency, i.e. the entire result of the case.")
print()
print("    So the criterion the guided node volunteers deletes HALF the harmonic")
print("    pair at the one frequency the MEG exists to find, and deletes f=5")
print("    outright -- the frequency with the second-highest MEG statistic (1.759).")
print("    Both deletions remove the null model the MEG needs, before the MEG runs.")
