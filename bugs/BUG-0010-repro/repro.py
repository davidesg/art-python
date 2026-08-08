"""BUG-0010 — pruning one non-significant harmonic pair silently kills the WHOLE MEG
sweep, and `describe_formal_tests` then reports a clean bill of health.

The MEG asks, frequency by frequency: is the seasonality at f deterministic or
stochastic? Its null model IS the deterministic harmonic at f, so `_check_reformulable`
(correctly) refuses to run at a frequency whose cos/sin are absent.

But `meg()` validates ALL requested frequencies up-front:

    for f in frequencies:            # f = 1 … s//2
        _check_reformulable(model, f, s)

so ONE unreformulable frequency raises before any frequency is computed — and
`describe_formal_tests` wraps the call in `_try(..., [])`, which swallows the
ValueError and returns an empty result list. `_meg_suitable()` is still True (the model
does have cos/sin), so the "MEG no aplica" branch never fires either. Net effect: the
MEG section vanishes without a word, and the report closes with

    "Los contrastes formales no detectan problemas. El modelo es adecuado."

Underneath the plumbing there is a methodological point, which is what makes the
silence expensive: a LOW t-ratio on the harmonic pair at f is evidence FOR stochastic
seasonality at f, not against seasonality at f. A fixed-coefficient harmonic fitted to
a frequency whose amplitude wanders averages toward zero. So pruning by t-ratio removes
exactly the frequencies the MEG most needs to examine, and it does so under the very
hypothesis (deterministic) that the MEG exists to test.

IPC_ES (INE Spanish CPI, 2002-01..2019-12, n=216, lam=0, d=1, D=0, AR(1) + mu) shows
both halves at once. f=5 has the least significant harmonics in the model (|t| = 0.29
and 1.27) AND the second-highest MEG statistic (LR = 1.77 against a 2.07 critical
value) — the closest to stochastic after f=3. Meanwhile f=3, whose harmonics are
significant (|t| = 5.4 and 2.1), is the one the MEG declares STOCHASTIC. Significance
of the harmonic and the deterministic/stochastic verdict are close to orthogonal.

Run:  python repro.py
"""
import os

import fue

from art.describe import describe_formal_tests
from art.formal_tests import meg
from art.full_report import _meg_suitable

HERE = os.path.dirname(os.path.abspath(__file__))

MODELS = [
    ("FULL    5 harmonic pairs + Nyquist (pre-MEG baseline)", "IPC_ES_m10.pre"),
    ("PRUNED  f=5 dropped for |t| < 2, everything else identical", "IPC_ES_m10_podado.pre"),
]


def load(fname):
    _, m = fue.inp.load(os.path.join(HERE, fname))
    m.fit()
    return m


def harmonics_present(model):
    return sorted({int(itv.harmonic) for itv in (model.interventions or [])
                   if itv.type in ("cos", "sin")})


print("PART 1 — the symptom: dropping f=5 removes every MEG verdict, not just f=5's")
print()
for label, fname in MODELS:
    m = load(fname)
    print(f"{label}")
    print(f"    cos/sin harmonics present: f = {harmonics_present(m)}"
          f"        _meg_suitable = {_meg_suitable(m)}")
    d = describe_formal_tests(m, run_meg=True)
    has_meg = "MEG" in d.summary
    print(f"    describe_formal_tests -> MEG section present: {has_meg}")
    if has_meg:
        for line in d.summary.splitlines():
            if line.startswith("- freq="):
                print(f"      {line}")
    print(f"    recommendation: {d.recommendation.strip().splitlines()[0]}")
    print()

print("PART 2 — the mechanism: the up-front validation loop is all-or-nothing")
print()
m = load("IPC_ES_m10_podado.pre")
try:
    meg(m)
    print("  meg(model)                 -> returned normally")
except ValueError as e:
    print(f"  meg(model)                 -> ValueError: {str(e)[:72]}...")
print("     (describe_formal_tests calls this inside _try(..., []): the exception")
print("      is swallowed and the empty list is indistinguishable from 'not run')")

ok = meg(m, frequencies=[1, 2, 3, 4, 6])
print()
print("  meg(model, frequencies=[1,2,3,4,6])  -> the testable frequencies alone:")
for r in ok:
    verdict = "stochastic" if r.stochastic else "deterministic"
    print(f"      freq={r.freq}  LR={r.lr:7.3f}   {verdict}")
print()
print("  f=3 is STOCHASTIC and it is reported only when f=5 is excluded by hand.")
print("  On the pruned model the analyst is told the model is adequate instead.")
