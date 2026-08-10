# The suite's files: `.inp`, `.out`, `.pre`

*What each file asserts, which program reads which, and the one trap that will
catch you first.*

---

## The trap, first

**There are TWO different `.inp` formats in this suite.** They share an
extension and nothing else — different structure, different readers, not
interchangeable.

| dialect | read by | contains |
|---|---|---|
| **univariate** | `fue`, `art`, `drtran`/`mtram` | a MODEL SPECIFICATION: Box-Cox, differencing, AR/MA operators, fixed-frequency factors, deterministics, the mean — and the data at the end |
| **multivariate** | `drvarma`/`sima` | a DATA SET: frequency, number of series, names, `λ d D`, and the observations |

The univariate one describes a model of one series. The multivariate one
describes several series and almost nothing about a model. Feeding one to the
other's reader fails; it does not silently misread, which is the one mercy.

The multivariate dialect is specified token by token in
**`drvarma/docs/INP_FORMAT.md`** and is not repeated here — one source of truth
per format. The rest of this page is the univariate family, because that is the
one with a *contract* on top of a syntax.

---

## The univariate family: three extensions, three claims

This is the suite's central convention, and it is what makes the ladder
climbable. `drtran/docs/LADDER_AS_OPTIMISATION.md` argues it; this states it.

| file | written by | asserts |
|---|---|---|
| **`.inp`** | `art`, an analyst, `drtran -W` | a **SPECIFICATION**. Parameter values are SEEDS — a starting point, nothing more |
| **`.out`** | `fue` | the full record of one estimation **and its diagnosis** — everything the next decision needs |
| **`.pre`** | `fue` | that same `.inp` with the estimates as new initial values: **an optimum, in re-runnable form** |

The cycle is a fixed-point iteration with a structural search around it:

```
.inp --(fue estimates)--> .pre --(the analyst reformulates)--> .inp --> ...
```

### The three rules that follow

**1. A `.pre` that is edited becomes an `.inp` again.** Editing the
specification unmakes the claim that these values are its optimum. This is not
bookkeeping etiquette: it is what stops the outer level mistaking a proposal for
a result.

**2. Only the program that performed an estimation may write a `.pre`.** The
file carries no mark of its author, so a fabricated one is indistinguishable
downstream from a certified one — and the ladder climbs by trusting exactly
that. `art` identifies and writes `.inp` with every parameter at `0.000000`; it
does not estimate and does not claim to.

**3. The claim is testable, and this is the load-bearing fact.**

> **Run `fue` on a `.pre` and the numbers do not move.**

Measured:

| file | max change after re-running `fue` |
|---|---|
| a `.pre` written by `fue` | **0.000000** |
| the univariate block `drtran` writes back after a JOINT fit | **13.109261** |

The second is not an arithmetic defect. Those blocks are optimal *with the
transfer in the model*, and the univariate optimum is by definition `fue`'s
separate estimate, so they cannot be a fixed point of the univariate operator.
That is why `drtran` writes `.inp` and not `.pre` — and why it was a real defect
when it did otherwise.

---

## What a univariate `.inp` holds

In file order. The `**` lines are labels for humans; what matters is the order.

```
frequency                         1 (annual), 4 (quarterly), 12 (monthly)
nobs, start date, series name
number of deterministic variables  and, per variable, its ω(B)/δ(B) and
                                   which coefficients are free
regular AR operators               count, orders, coefficients, free/fixed flags
annual AR operators                idem
regular MA operators               idem
annual MA operators                idem
fixed-frequency AR(2) factors      count and frequencies
fixed-frequency MA(2) factors      idem  ← the MEG / HSM witnesses live here
mean (μ)                           value and whether it is free
Box-Cox λ, d, D
ifadf                              freq/2+1 flags: the individual factors of the
                                   annual difference, frequency by frequency
ACF/PACF bands, rescaling factor
the series
```

Three fields deserve a note because they are where mistakes concentrate:

* **`ifadf`** is what makes hybrid seasonality expressible: one flag per
  frequency, so `∇∇₄` can be written as `d=2` plus factors at π/2 and π rather
  than as `D=1`. Those are the SAME operator — `∇∇₄ = (1−B)²(1+B)(1+B²)`,
  because the `(1−B)` inside `∇₄` adds to the regular difference — and any
  program comparing two models must compare the **polynomial**, not the
  `(d, D)` pair. That is not pedantry: `mtram` decides whether a transfer needs
  correcting on exactly this comparison.
* **The rescaling factor** multiplies the transformed series. It exists so the
  variances land in O(10), which is the range the optimiser's finite-difference
  step can work in. Two series compared across models must share it.
* **λ, d, D describe how to make the data stationary — the data itself goes in
  raw.** Do not pre-difference. Every program in the suite applies the operator
  itself, and a pre-differenced series with `d=1` declared is differenced twice.

---

## Which program reads which

```
art     reads  data (CSV/XLSX)          writes  .inp   (specification, seeds at 0)
fue     reads  .inp                     writes  .out + .pre
mtram   reads  .pre  (or .inp)          writes  .inp   (after a joint fit)
sima    reads  its own .inp             writes  reports
```

`mtram` accepting an `.inp` is not a tolerated edge case: by rule 1, an `.inp`
is what a reformulated `.pre` has become, so a specification is the normal input
after any revision. It re-estimates on the way in, so the seeds are only seeds —
and it reports whether what it was handed was an optimum or a specification,
which is a question the suite could not answer before and neither answer is a
problem. Being unable to tell them apart was.
