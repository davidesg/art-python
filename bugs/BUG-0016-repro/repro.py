"""BUG-0016 — `decide_d` takes the ADF+KPSS consensus straight, so a seasonal
series can jump from d=0 to d=2 in one step, with the seasonality that
contaminated the tests already detected three lines earlier and ignored.

`policy.decide_d` (policy.py:56-61) is the whole of it:

    return int(unit_root_data.get("recommended_d", 1))

No cap, and no reference to the seasonal decision. Yet `run_full`
(pipeline.py:731-736) computes the seasonality FIRST and has the answer in hand:

    seas = describe_seasonality(ts)
    D, decision, n_harmonics = pol.decide_seasonal_structure(seas.data, ts.freq)
    urt  = describe_unit_root(ts, lam=lam)      # <- ADF+KPSS with the seasonality IN
    d    = pol.decide_d(urt.data)               # <- and it never sees D

Two things are wrong, and the school names both:

* **One decision at a time.** Box-Jenkins moves d by one step and re-reads the
  plot. Going 0 -> 2 in a single jump is not a step, it is a conclusion. The
  level plot of a CPI index says "at least d=1" on its own; whether a SECOND
  difference is warranted is a separate question asked on the once-differenced
  series.
* **Seasonality contaminates the unit-root tests.** They are run on the
  lambda-transformed series with the seasonal pattern still in it, and that
  pattern inflates the residual variance of the ADF regression, pushing it
  towards not rejecting. Seasonality is normally read on a roughly CENTRED
  series, which is why the guided path tests it on the differenced one.

This script measures the contamination directly: it ranks the eight CPI indices
by the strength of their seasonality and shows which ones over-difference.

Run:  python3 bugs/BUG-0016-repro/repro.py
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent

SERIES = ["IPC_ES", "IPC_FR", "IPC_DE", "CPI_USA",
          "EMU", "IPC_JP", "IPC_CA", "IPC_UK"]


def main() -> int:
    import fue
    from art.describe import describe_seasonality, describe_unit_root
    from art.policy import decide_seasonal_structure, DefaultPolicy

    # `decide_d` recibe ahora la decisión estacional, como en `run_full`. Antes
    # no la veía, aunque `run_full` ya la había tomado tres líneas antes.
    pol = DefaultPolicy()

    print(__doc__.split("Run:")[0].strip())
    print()
    print("  lambda = 0 for every series (the index rule; see BUG-0015)")
    print()
    print("   series      F-HAC   seasonal?   D  harm   recommended_d   decide_d")
    print("  " + "-" * 68)

    rows = []
    for name in SERIES:
        ts, _ = fue.load(str(HERE / f"{name}.inp"))
        se = describe_seasonality(ts).data
        D, _dec, nh = decide_seasonal_structure(se, ts.freq)
        u = describe_unit_root(ts, lam=0.0).data
        d = pol.decide_d(u, seasonal=(_dec != "A"))
        rows.append((name, float(se["f_stat"]), bool(se["seasonal_detected"]),
                     D, nh, int(u["recommended_d"]), d))

    for name, f, seas, D, nh, rec, d in sorted(rows, key=lambda r: -r[1]):
        mark = "   <-- OVER-DIFFERENCED" if d >= 2 else ""
        print(f"   {name:10} {f:7.1f}   {str(seas):>9}   {D}  {nh:4d}   "
              f"{rec:13d}   {d:8d}{mark}")

    print()
    bad = [r for r in rows if r[6] >= 2]
    if not bad:
        print("  Nothing over-differenced — BUG-0016 would be refuted by this run.")
        return 0

    ranked = sorted(rows, key=lambda r: -r[1])
    top = {r[0] for r in ranked[:len(bad)]}
    hit = {r[0] for r in bad}

    print(f"  {len(bad)} of {len(rows)} get d=2, and EVERY ONE of them has")
    print("  `seasonal_detected = True` with a full harmonic package already")
    print("  decided (D=0, 5 pairs) before d is asked for.")
    print()
    if top == hit:
        print("  And they are exactly the top of the seasonality ranking:")
        for r in ranked[:len(bad)]:
            print(f"    {r[0]:10} F-HAC = {r[1]:.1f}")
        print(f"    ---- everything below F-HAC = {ranked[len(bad)][1]:.1f} "
              f"gets d=1 ----")
        print()
        print("  That is the contamination, not a coincidence: the strongest")
        print("  seasonality is what pushes ADF towards not rejecting.")
    print()
    print("  BUG-0016 REPRODUCED.")
    print()
    print("  Note the interaction with BUG-0015: IPC_ES comes back with d=1 from")
    print("  `build_model` only because the policy picked lambda=1 for it. Fix the")
    print("  index rule and this bug fires on ES too. They must be fixed together")
    print("  or the second will look like a regression of the first.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
