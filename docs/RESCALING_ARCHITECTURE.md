# Rescaling architecture — audit and robust design

Scope: the `refactor` (rescaling) factor across **fue** (estimation, forecast,
reports), **ART** (`_make_model`, `_mu_seed`, `_write_inp`), the `.pre/.inp/.out`
format, and **drtran**. Written after BUG-0004 (fue) and BUG-0006 (ART) traced a class
of scale-inconsistency bugs to a hardcoded ×100 decoupled from the model's `refactor`.

---

## 1. What the rescale is (and why)

`refactor` is a **single per-model scale factor** applied to the transformed series for
**numerical conditioning**: log-differences of a price index are `O(0.002)`, which the
C optimizer (`qnewtopt`/BFGS + finite-difference gradients, step `≈6e-6`) handles poorly;
`×100` lifts them to `O(0.2)`, the range the optimizer works in.

**The contract:** everything transformed lives in the `refactor · BoxCox(data)` space —
the estimation series (`DataMat`), the estimated parameters, the mean `μ`, the residuals,
and what is stored in the `.pre`. The **level** is recovered by `÷refactor` at the very
end (forecast integration, reports). It is ONE quantity, and its value travels in
`model.refactor` (in memory) ↔ the "reescaling factor" field of the `.pre/.inp` ↔ `.out`.

**Corollary (the design intent):** a sample statistic computed on the *already-rescaled*
series is automatically in the rescaled space. So the seed for `μ` is just the sample
mean of `refactor · ∇BoxCox(data)` — no separate multiplication is needed.

---

## 2. Where the contract holds (the design working) ✓

fue reads `model.refactor` consistently everywhere:

| stage | site | behaviour |
|---|---|---|
| estimation | `cast_us.py` `_boxcox(data, lam, model.refactor)` | `DataMat = refactor · BoxCox` |
| forecast | `forecast.py` `_boxcox` / `_inv_boxcox` | transform `×refactor`; level, std `÷refactor` |
| reports | `plots.py`, `report_forecast.py` | scale by `model.refactor` |
| `.pre` I/O | `inp.py` | reads/writes the reescaling field (`0.0 → 1.0`) |
| **drtran** | `fue_pre_reader.c`, `drtran.c` | reads refactor from `.pre`; `DataMat×refactor`; level `÷refactor` |

So **within a single engine, if `model.refactor` is right, everything is consistent** —
including drtran, which honours the `.pre`'s refactor.

---

## 3. Where the architecture fails ✗

The failure is **not** in the rescale math; it is **hardcoded `100`s in ART decoupled
from `model.refactor`**, plus fue not syncing the fit into the attributes.

| # | site | fault |
|---|---|---|
| 1 | ART `_mu_seed` (`_RESCALE_FACTOR=100`) | seeds `μ0 = 100·drift`, hardcoding 100 instead of deriving the scale from `model.refactor` / the already-rescaled series. |
| 2 | ART `_make_model` | builds the in-memory `fue.Model` with `refactor=1` (the fue default) **but seeds μ in the ×100 space** → the object is internally inconsistent (its `μ0` and its `refactor` disagree). The "×100" lives in `_mu_seed`/`_write_inp`, **not in the Model**. |
| 3 | ART `_write_inp` (`_RESCALE_FACTOR=100`) | writes `refactor=100` hardcoded (ignoring `model.refactor=1`) and writes `μ` from the **stale attribute**. Emits a `.pre` in the ×100 dialect regardless of the model's actual refactor. |
| 4 | fue `plots.py` (`else 100.0`) | falls back to `100` when `model.refactor` is unset — another hardcoded leak. |
| 5 | fue `Model.fit()` | does **not** sync `_result.params` back into `self.ar/ar_s/ma/ma_s/μ0`; the attributes keep the seeds, so every attribute-consumer reads a seed, not the fit. |

### Consequences (the propagation)

- **BUG-0004:** `forecast_fuf` (in-memory model, `refactor=1`) reads the stale `μ0` (×100)
  → level explodes. (Fixed: forecast now reads `_result`.)
- `_write_inp` writes the **seed** `μ0` (×100), not the fit — masked only because for `μ`
  the sample-mean seed ≈ the MLE.
- **Two `.pre` dialects** coexist (`refactor=1`/raw vs `refactor=100`/×100); a tool that
  assumes one misreads the other.
- The optimizer's `x0` starts 100× off in `μ` (a bad seed; on multimodal surfaces it can
  steer the basin — cf. BUG-0006).
- Any code reading `m.μ0` as "the drift" gets 100×.

### The architectural smell, in one line

> The in-memory model produced by `_make_model` is a **broken intermediate** that is only
> made consistent by the round-trip through `_write_inp` (which force-writes
> `refactor=100 + μ×100`, a consistent pair) and reloading. The **in-memory path** and the
> **`.pre` round-trip path** do not agree.

---

## 4. Robust design

Four principles; the fixes follow from them.

**P1 — Single source of truth.** The rescale factor is ONE value, owned by
`model.refactor`. **No file and no function hardcodes `100`.** Wherever a scale is needed,
read `model.refactor` (or the `.pre` field it was written to).

**P2 — Rescale applied once, undone once.** The transform (`refactor · BoxCox`) applies it;
level recovery (`÷refactor`) undoes it. Everything in between — params, seeds, residuals,
the `.pre` — lives in the rescaled space. (fue already does this internally; the job is to
stop ART from breaking it.)

**P3 — Seeds are computed on the rescaled series.** `μ`-seed = sample mean of the
`refactor · ∇BoxCox(data)` differenced series (and, for residual-based seeds, of the
rescaled residuals). It is then automatically in the model's scale — no `×100` constant.

**P4 — The model object is always internally consistent.** `_make_model` sets
`model.refactor` to the intended value; its `μ0`/`ar`/… seeds are in that same space. There
is no state that is correct only after a write+load cycle.

### Concrete changes

**ART**
1. `_make_model` sets `refactor=REFACTOR` on the `fue.Model` (fresh path *and* the
   `base_pre_path` path, which already forwards `m_base.refactor`). `REFACTOR` is the one
   named constant (today `100.0`); everything else derives from `model.refactor`.
2. `_mu_seed` computes the mean of the **rescaled** differenced series
   (`refactor · ∇BoxCox`), i.e. it takes `refactor` as an argument (from the model), not
   the global constant. Equivalent value today, but sourced from the model.
3. `_write_inp` writes `model.refactor` and `μ` from the **fit** (`_result.params`, once
   fue syncs — see below), never a hardcoded constant nor a stale attribute.

**fue**
4. `Model.fit()` **syncs** `_result.params` (invertible-normalised) back into
   `self.ar/ar_s/ma/ma_s/μ0` and the interventions, in the same rescaled space — so *every*
   attribute-consumer (forecast, `_write_inp`, reports) sees the fit. With P1–P4 there is no
   ×100 conversion in the sync (single scale), so it is a plain copy. The point-fix in
   `eval_at_params` (read `_result` when present) stays as belt-and-suspenders.
5. `plots.py` fallback `else 100.0` → `else 1.0` (or read `model.refactor`); no hardcoded
   `100` as a scale (the `100·x/refactor` percent-unit conversions are display-only and
   stay).

### The invariant to enforce (and test)

> **In-memory ≡ round-trip.** For any model,
> `build → fit → forecast` (in memory) must equal
> `build → fit → write .pre → load → forecast`.
> And `M.refactor` must be consistent with the scale of `M.μ0`, `M.ar`, …, and with the
> reescaling factor written to `M`'s `.pre`.

A single test asserting this equality closes the whole class: it fails today (the two paths
disagree) and passes under the robust design.

### On the value of `refactor`

Orthogonal to the above. Today it is a fixed `100` (good for log price indices). A more
robust choice is data-driven — e.g. `refactor ≈ 1/std(∇BoxCox)` so the differenced series
is `O(1)` for any series — but that is a refinement of P1's *value*, not of the
architecture. The architecture is about **consistency**, not the specific number.

---

## 5. Status

**P1–P4 IMPLEMENTED (2026-07-22).** The invariant `in-memory forecast == .pre round-trip
forecast` now holds (`tests/test_rescaling_invariant.py`); fue suite 651 passed, ART suite
466 passed (no golden shift — the pipeline already wrote/loaded `refactor=100`).

- **fue** (`fix(fit)`, `23cc9c3…`): `Model.fit()` calls `sync_params_to_attrs` — the model
  IS the fit after fitting (P4). `eval_at_params` reads `_result` as a belt-and-suspenders
  (BUG-0004, `2fd96ee…`).
- **ART** (`fix(pipeline)`, `f076982…`): `_make_model` sets `model.refactor` (P1/P4);
  `_mu_seed` takes the model's refactor and seeds on the rescaled series (P3);
  `_build_arma_on_model` forwards the base refactor; `_write_inp` writes `model.refactor`
  (P1). Plus ART BUG-0006 seed-on-de-harmonized-noise (`0afe3c4…`).
- **Remaining (minor):** fue `plots.py` fallback `else 100.0` → `else 1.0` — display-only,
  now near-dead code since `refactor` is always set; low priority.
- **Related, independent:** fue BUG-0005 (optimizer robustness on multimodal surfaces)
  shares the "bad seed → wrong basin" failure mode but is orthogonal to the rescale.
