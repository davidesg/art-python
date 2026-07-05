# SF_MEG — Monte-Carlo critical values for the DCD_f / MEG boundary LR test

These scripts **derive** the finite-sample critical values that ART hardcodes in
`src/art/formal_tests.py` (`_DCD_CRIT_MA_F_TABLE`, `_DCD_CRIT_MA`, `_DCD_CRIT_MA_F_ASYMP`).
The DCD_f / MEG boundary LR is non-standard — a pile-up atom at 0 plus a non-χ² tail — so
its critical values are obtained by simulating the null distribution, not from a table.

## Reproduce (seed=0, 20 000 reps/frequency)

1. Simulate the null draws for each sample size:
   ```
   for n in 120 240 480 960; do python dcd_mc.py --n $n --freqs 0,1,2,3,4,5,6; done
   ```
   → writes `out/table_n{n}.npz` (gitignored; regenerable).
2. Pool, quantile (+ bootstrap SE) and emit the versioned provenance artifact:
   ```
   python final_table.py --emit-json crit_table.json
   ```

## Files
- `dcd_mc.py` — MC null of the DCD_f LR (seed=0). Second-order fixed-frequency witness at
  the interior frequencies f=1..5; first-order (1±rB) at the Nyquist f=6 and trend f=0.
- `final_table.py` — pools f1..5 (complex-pair regime) and f0/f6 (real-root regime),
  computes the 10/5/1 % quantiles with bootstrap SE + a homogeneity check; `--emit-json`
  writes `crit_table.json`.
- `crit_table.json` — **versioned provenance**: the exact numbers ART uses.
- `shinfuller_*.py`, `aggregate*.py`, `power_*.py`, `deterministic_effect.py`,
  `run_det_pooled.py` — companion derivations (Shin-Fuller AR_f law, power/pile-up studies).
- `out/` — MC draws (gitignored; regenerate with `dcd_mc.py`).

## Mapping to the ART constants (`art.formal_tests`)
| crit_table.json | ART constant | what |
|---|---|---|
| `complex_by_n` | `_DCD_CRIT_MA_F_TABLE` | interior f=1..5, pooled, by sample size n |
| `asymptotic_complex` | `_DCD_CRIT_MA_F_ASYMP` | large-n limit of the complex regime |
| `real_root` | `_DCD_CRIT_MA` | Davis–Dunsmuir MA(1) anchor (f=0 trend, f=6 Nyquist) |

`tests/test_dcd_crit_provenance.py` pins that the ART constants still equal this table — so a
constant cannot drift from its Monte-Carlo source without a test failure.
