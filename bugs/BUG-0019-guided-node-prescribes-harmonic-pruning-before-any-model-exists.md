---
id: BUG-0019
title: The guided seasonality node PRESCRIBES pruning harmonics from a per-frequency HAC test computed before any model exists, and contradicts its own n_harmonics recommendation in the same output
status: fixed
severity: high
component: identification
found_in: 0.1.11
fixed_in: 0.1.12
reported: 2026-08-14
reporter: David / IPC_ES guided re-run
tags:
  - meg
  - seasonality
  - harmonics
  - guidance
  - guided-identification
references:
  - src/art/describe.py:236-239 (`describe_seasonality`: `sig_freqs` filtered at p<0.05)
  - src/art/describe.py:253-255 (printed as "Frecuencias significativas")
  - src/art/describe.py:271 ("D=0, con armónicos cos/sin para cada frecuencia significativa") — introduced 2026-06-13, 8fb7785
  - src/art/mcp_server.py:1907 (`n_harm = max(ts.freq // 2 - 1, 0)` — the full set, ignoring significance)
  - src/art/mcp_server.py:1922-1923 (the `confirm_and_estimate` block printed with n_harmonics=n_harm)
  - src/art/describe.py:2336-2343 (`describe_seasonal_params`: the recommendation that prescribes pruning, post-estimation)
  - fue/bugs/BUG-0013 (the ARMA(0,0) segfault hit while writing the second repro)
  - bugs/BUG-0019-repro/ (two IPC_ES .inp + repro.py; repro_bloque_g.py for the second locus)
  - BUG-0010 (same methodological point; its fix left the recommendation TEXT untouched — see «Second locus»)
---

## Summary

Step 3 of `guided_identification` — the node where the analyst chooses the seasonal
harmonic set, before anything has been estimated — runs the HAC seasonality test on the
differenced series and prints a per-frequency significance list, followed by

> **Decisión B1 — estacionalidad determinista (punto de partida recomendado).**
> - D=0, con armónicos cos/sin **para cada frecuencia significativa**.

That is an instruction to omit the harmonics at the frequencies the HAC did not flag.
On IPC_ES the list is `f=1, f=2, f=3, f=4, f=6` — f=5 is missing (p=0.50) — so read
literally the node prescribes building the model **without** f=5.

Two lines below, in the same output, the `confirm_and_estimate` block recommends
`n_harmonics=5` — the full set — because `mcp_server.py:1907` computes it as
`freq // 2 - 1` with no reference to significance. **One screen, two contradictory
instructions**, and the prose one is both the wrong one and the one an assistant or a
novice reads as the reasoning.

## Impact

**High.** This is BUG-0010's methodological point arriving one stage earlier, where
none of BUG-0010's fixes can reach it.

BUG-0010 established that pruning a harmonic pair by t-ratio pre-judges the MEG's
hypothesis: the MEG's null model **is** the deterministic harmonic at f, and a low
t-ratio at f is evidence **for** stochastic seasonality there, not evidence that f is
absent. Its fixes put that warning in three places — the over-parametrisation note in
`describe_diagnosis`, the `seasonal_param_analysis` / `test_seasonal_simplification`
docstrings, and ETAPA 4 of `_INSTRUCTIONS`. **All three are downstream of estimation.**
They protect the analyst who prunes an estimated model. They say nothing to the analyst
who never adds the harmonic in the first place, which is what this node prescribes.

Never adding it is the worse of the two paths. A pruned model still leaves a trace the
MEG sweep can report (`⚠ sin contrastar`, BUG-0010's fix). A model built without the
harmonic is simply a model in which that frequency was never a question.

**And the criterion is not even available at this node.** Nothing has been estimated.
The only model that exists here is m00 — harmonics alone, no ARMA, no μ — which is not
adequate: its residuals carry the entire regular AR(1), so every harmonic standard
error is inflated by the unmodelled dynamics. On IPC_ES, σ̂² falls from 0.0989 (m00) to
0.0627 once the AR(1) and μ are in (37 % absorbed), and one harmonic changes verdict:

| | m00 (no ARMA, INADEQUATE) | m10 (adequate) | |
|---|---|---|---|
| sin3 | t = −1.59 → **prune** | t = −2.10 → **keep** | **flips** |

`sin3` is half the pair at **f=3 — the frequency the MEG declares STOCHASTIC on this
series** (LR = 2.304 against a 2.07 critical value at n=216), and the only
non-deterministic frequency in the case. So the significance filter this node
volunteers deletes half the pair at the one frequency the whole procedure exists to
find, and deletes f=5 outright — which carries the second-highest MEG statistic
(LR = 1.759). Both deletions remove the MEG's null before the MEG runs.

The failure mode is not exotic. It is what the tool tells you to do, at the node where
it tells you to do it, and it was reached in an ordinary guided re-run of the pilot
case.

## Arreglado — 14-ago-2026

Los dos focos, y **sin prohibir la poda**: lo que estaba mal era el orden y la
falta de condición, no que se pudiera podar.

* **Nodo guiado** (`describe.py:270`): «armónicos cos/sin en **TODAS** las
  frecuencias, f=1..s/2», más el porqué —la lista del HAC es descriptiva, no una
  regla de selección; el modelo nulo del MEG en f **es** el armónico en f; y en
  ese punto no hay nada estimado—. Deja de contradecir al `n_harmonics=freq//2-1`
  que se imprime dos líneas más abajo.

* **Recomendación tras estimar** (`describe.py:2336`): ofrece **los dos caminos
  legítimos**, que es lo que `art` hacía antes:
  **(a)** si se va a contrastar el MEG, todavía no se poda, y lo que salga
  estocástico se reformula con `ifadf[f]=1`;
  **(b)** si el analista **fija la estacionalidad como determinista y renuncia
  al MEG**, entonces **procede simplificar ahora** — el RV conjunto del Bloque H.
  Y en un modelo mixto ya resuelto, podar los deterministas que quedan es el paso
  final y también procede.

  Un texto que sólo dijera «no podes» sería tan defectuoso como el que decía
  «poda»: dejaría sin salida al analista que ya decidió.

`tests/test_bug_0019_no_pruning_before_meg.py` (7 pruebas) fija el texto, porque
**el texto es el comportamiento**: quien lo lee —analista o asistente— hace lo
que dice. Y `tests/test_pipeline_regression.py` añade la matriz de casos con
verdad conocida para que esto no vuelva por otra puerta.

## Second locus, found 2026-08-14: the same prescription AFTER estimation

BUG-0010 is marked fixed, and its fix put the warning in **three places: the
over-parametrisation note, two tool docstrings, and ETAPA 4 of the
instructions**. None of them is the `recommendation` field of
`describe_seasonal_params` (`describe.py:2336-2343`) — the sentence printed
under the chart, which is what the analyst and the assistant actually read:

> Los armónicos k=4, k=6 tienen |t| ≤ 2 en ambos componentes. **Considera
> eliminarlos** con un test RV conjunto (Bloque H) antes de simplificar.

It never mentions the MEG, and it is emitted on **any fitted model**, with no
condition that the model be adequate. So the docstring of the tool warns and the
output of the tool prescribes the opposite — and between the two, the output
wins, because it is what gets read.

`bugs/BUG-0019-repro/repro_bloque_g.py` builds a series whose seasonality is
**mixed by construction** — deterministic at f=1, stochastic at f=2 — fits the
initial specification, and gets:

```
   droppable_k = [4, 6]
   "Los armónicos k=4, k=6 … Considera eliminarlos …"
   ✗ the recommendation never mentions the MEG
   ✗ it does not require the model to be adequate
```

on a model that is **not adequate**: the stochastic seasonality at f=2 is
unmodelled and sits in the residuals, inflating every standard error — the same
mechanism as PART 2 above, now downstream instead of upstream.

**This is why "an older bug that keeps getting worse" is the right reading.** The
methodological point is BUG-0010's; its fixes went to the places a reader
consults *before* acting, and left untouched the one sentence that tells the
reader what to do.

⚠ Writing this repro hit a second defect, in the engine: the natural
specification here — harmonics and white noise, ARMA(0,0) — **segfaults the C
engine** when built through the Python API. See `fue/bugs/BUG-0013`. The repro
carries an AR(1) to get around it, which is itself a distortion of the case it
means to show.

## Reproduction

`bugs/BUG-0019-repro/` — IPC_ES (INE Spanish CPI, 2002-01…2019-12, n=216, λ=0, d=1,
D=0), two self-contained `.inp`: `IPC_ES_m00` (11 harmonics, no ARMA, no μ) and
`IPC_ES_m10` (same harmonics + AR(1) + μ, the adequate model).

```
$ cd bugs/BUG-0019-repro && python repro.py

PART 1 -- what the guided node prints, with nothing estimated
    - F-test HAC conjunto: **F=90.16**, p=0.0000
    - Frecuencias significativas: f=1 (χ²=12.1, p=0.0024), f=2 (χ²=564.9, p=0.0000),
      f=3 (χ²=24.5, p=0.0000), f=4 (χ²=21.9, p=0.0000), f=6 (χ²=330.7, p=0.0000)
    - D=0, con armónicos cos/sin para cada frecuencia significativa.

    -> f=5 is absent from the list, and the line below it says to put a
       harmonic on each SIGNIFICANT frequency. Read literally: drop f=5.
    -> the code block in the same output says n_harmonics=5 (mcp_server.py:1907,
       `freq // 2 - 1`), which contradicts it. Nothing has been estimated yet.

PART 2 -- the criterion is not stable: inadequate model vs adequate model
    cos1         t=  -2.75 (keep )   t=  -2.84 (keep )
    sin1         t=  -2.87 (keep )   t=  -2.96 (keep )
    cos2         t=   9.56 (keep )   t=  10.69 (keep )
    sin2         t= -19.05 (keep )   t= -21.76 (keep )
    cos3         t=   4.04 (keep )   t=   5.29 (keep )
    sin3         t=  -1.59 (PRUNE)   t=  -2.10 (keep )   <<< VERDICT FLIPS
    cos4         t=   3.37 (keep )   t=   4.87 (keep )
    sin4         t=  -1.02 (PRUNE)   t=  -1.55 (prune)
    cos5         t=  -0.13 (PRUNE)   t=  -0.27 (prune)
    sin5         t=   0.72 (PRUNE)   t=   1.18 (prune)
    alter(f=6)   t=  10.75 (keep )   t=  18.46 (keep )

    sigma^2:  m00 = 0.0989   m10 = 0.0627   (37 % absorbed by the AR(1))

PART 3 -- what the prescribed prune costs, on this series
    sin3 (frequency f=3): |t| = 1.59 on the inadequate model
    -> PRUNE, but 2.10 on the adequate one -> keep.
```

⚠ The repro estimates from the `.inp`, never from a `.pre`. Starting at the optimum
leaves the optimizer no path and the accumulated covariance comes out mis-scaled — on
this same model the harmonic standard errors inflate by up to ×4.4 (cos3: 0.0163 →
0.0722), which would make every t-ratio in PART 2 wrong. Point estimates and the
likelihood are unaffected. This is a known engine property, not part of this bug, but it
is a live trap for anyone writing a repro in this area.

## Root cause

Three lines, in two files, that were written independently and never read together.

1. **`describe.py:236-239`** builds the list by filtering the per-frequency HAC at
   p<0.05:

   ```python
   sig_freqs = [
       f"f={fr.freq_idx} (χ²={fr.wald_stat:.1f}, p={fr.p_value:.4f})"
       for fr in freqs if fr.p_value < 0.05
   ]
   ```

   Computed on the differenced series. There is no model, adequate or otherwise.

2. **`describe.py:271`** turns that list into a modelling instruction:

   ```python
   "- D=0, con armónicos cos/sin para cada frecuencia significativa.",
   ```

   Introduced 2026-06-13 (`8fb7785`), i.e. it predates the whole MEG guidance effort —
   which is why BUG-0010's sweep never revised it.

3. **`mcp_server.py:1907`** independently computes the recommendation the analyst
   actually executes:

   ```python
   n_harm = max(ts.freq // 2 - 1, 0)      # 5 for monthly — the FULL set
   ```

   and prints it in the `confirm_and_estimate` block at 1922-1923. This one is correct.
   Nothing reconciles it with the prose above it.

The mitigating line — *"MEG (etapa 3, tras estimar) validará si alguna frecuencia es
estocástica"* — is present at `describe.py:273`, but it reads as a promise that the MEG
will check later, not as a warning that pruning now **prevents** that check.

## Fix

The instruction must be inverted, not softened: at this node the full harmonic set is
not one defensible option among several, it is the only one that keeps the MEG
answerable.

1. **`describe.py:271`** — replace "para cada frecuencia significativa" with the full
   set, and say why:

   ```
   - D=0, con armónicos cos/sin en TODAS las frecuencias estacionales (f=1…s/2).
   - NO podes las no significativas aquí: el armónico determinista en f ES la
     hipótesis nula del MEG, así que quitarlo deja f sin contrastar. Además, una
     amplitud baja en f es lo que produce la estacionalidad ESTOCÁSTICA en f — es
     evidencia a favor, no en contra. La poda, si procede, va DESPUÉS del MEG.
   ```

2. **`describe.py:253-255`** — the per-frequency list is legitimate as description of
   the seasonal pattern, but must not read as a selection rule. Relabel it (e.g.
   "Perfil por frecuencia (HAC, descriptivo)") and attach the same one-line caveat that
   it is not a criterion for choosing harmonics.

3. **Reconcile the two recommendations.** `n_harm` at `mcp_server.py:1907` is right;
   make the prose derive from the same quantity so the two cannot drift apart again.

4. Consider having `describe_seasonality` state explicitly that nothing has been
   estimated yet, so no statement about harmonic significance is available at this node
   — the same "the criterion is not available here" note the ETAPA 4 guidance already
   makes for the post-estimation case.

## Validation

Regression test asserting that `describe_seasonality(ts).summary` for a series with a
non-significant frequency (the IPC_ES repro series, f=5 at p=0.50):

* does **not** contain a string instructing harmonics only at the significant
  frequencies;
* does contain the full-set instruction plus the "prune after the MEG" reason;
* agrees with `mcp_server`'s `n_harm` for the same series.

Plus the numeric invariant from PART 2, which is what makes the case concrete: on
`IPC_ES_m00.inp` the f=3 sine harmonic has |t| < 2 and on `IPC_ES_m10.inp` it has
|t| > 2, so any guidance keyed to harmonic significance is unstable across the ARMA
step. Both `.inp` are ~4.6 KB and self-contained, so they can be promoted into `tests/`
directly.

Related: BUG-0010 (same methodological point, fixed downstream of estimation — this
report is the upstream half its fixes cannot reach); BUG-0016 (the neighbouring node in
the same guided output, where a detected seasonality was likewise ignored by a
criterion that had no business deciding).
