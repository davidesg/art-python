---
id: BUG-0196
title: La estacionalidad se contrasta en datos anuales — con freq=1 no hay frecuencias estacionales, y el nodo 3 publica un F(0,60)=0, p=1, una figura vacía y las rutas B1/B2
status: fixed
severity: medium
component: identification
found_in: 0.2.3.dev0
fixed_in: 0.2.3.dev0
reported: 2026-09-29
reporter: David / Claude — análisis guiado de la rata almizclera (Jenkins y Alavi 1981), camino a sima
tags:
  - seasonality
  - annual
  - guided
  - presentation
references:
  - src/art/mcp_server.py::guided_identification (paso 3, ~l. 5092: `if d > 0: sea = describe_seasonality(ts)`)
  - src/art/pipeline.py::run_full (~l. 1650: `seas = describe_seasonality(ts)`)
  - src/art/seasonal_detection.py::detect_seasonality
  - src/art/describe.py (~l. 732: `if D == 0: seasonal_note = "Añade armónicos cos/sin (n_harmonics=freq//2)…"`)
---

## Summary

Con una serie ANUAL (freq=1) el nodo 3 de `guided_identification` (paso d>0)
ejecuta igualmente el contraste HAC de estacionalidad y publica:

- «F-test HAC conjunto: **F=0.00**, p=1.0000» y «Estacionalidad detectada:
  **No**» — un F con **0 grados de libertad en el numerador**: no contrasta
  nada, porque con s=1 no hay ningún armónico estacional;
- una figura vacía, «Seasonal pattern (not detected) — HAC F(0, 60) = 0.000,
  p = 1.0000», con una única barra «P1 0.00 %» (y matplotlib avisa de límites
  del eje Y idénticos);
- el guion del nodo para datos estacionales: «¿Estacionalidad? (picos en
  ACF/PACF a lags s, 2s, 3s…)», «Picos regulares/estables → B1», «Picos muy
  dominantes o irregulares → B2».

## Impact

Medio. La conclusión (D=0, sin armónicos, «Decisión A») es la correcta, así que
no cambia el modelo. Pero la salida aparenta un contraste que no existe y pide
al analista buscar picos en retardos estacionales que en datos anuales no
tienen sentido; para un alumno es confuso —parece que se ha comprobado algo—, y
el ciclo de ~10 años de una serie anual (poblacional, de periodo no fijo) puede
leerse como «estacional» cuando se modela con la parte AR.

## Related symptom: the residual Q in annual data

The diagnosis Q takes its lag count from the seasonal convention (9 lags for
s=1, the «3f+3» rule), so in annual data it has almost no degrees of freedom
left once the ARMA is fitted. MUSKRAT_m03, ARIMA(6,1,1) with 7 parameters:
Q(9 lags, 2 d.f.) — a test with no power, reported as «decide». For s=1 the
lag count should follow n (e.g. min(n/4, 20)), not s.

Decided 2026-09-30 (sima and drvarma already apply it): a residual
portmanteau keeps at least 2 lags beyond the parameters, K = max(K of the
legacy rule, npar + 2) — Q with at least 2 d.f., a pair's P with at least 8.
fue's `default_lags` and art's Q should take the same floor.

## Related symptom: the identification listing recommends harmonics in annual data

Found 2026-09-30 in the guided analysis of weekly SPDR ETFs loaded with
freq=1 (a TFM analysis, XLRE_F / XLV_F), and still present after reconnecting
the server. Every identification listing (`identification_analysis`, and
node 4 of `guided_identification`) ends with

> «Confirma SARIMA(0,0,0)(0,0,0)_1 como punto de partida. … **Añade armónicos
> cos/sin (n_harmonics=freq//2) en confirm_and_estimate.**»

With freq=1 that is n_harmonics=0 — the advice is empty at best and
misleading at worst: it tells the analyst to add seasonal harmonics to an
annual series. It also appears for monthly/quarterly series in which the HAC
test did NOT detect seasonality (Decisión A), contradicting node 3.

Root cause: `describe.py` ~l. 732 chooses the note from `D` alone —
`if D == 0: seasonal_note = "Añade armónicos…"` — without looking at `freq`
nor at the outcome of the seasonality test. The fix proposed below for
`guided_identification` and `run_full` does not touch this site, so this
symptom would survive it.

## Reproduction

```python
from art.mcp_server import guided_identification
out = guided_identification(
    inp_path=".../ART/Data/cases/MINK_MUSKRAT/MUSKRAT.inp",   # anual, 1850-1911
    lam=0.0, d=1, objetivo="multivariante")
# «F-test HAC conjunto: F=0.00, p=1.0000» · figura vacía · rutas B1/B2
```

El `.inp` sale de `load_data(mink_muskrat.csv, column="muskrat", freq=1,
start_year=1850)`; los datos, en
`atsw-gui/engines/drvec/datasets/mauricio/mink_muskrat.csv`.

## Root cause

`guided_identification`, paso 3, llama a `describe_seasonality(ts)` siempre
que `d > 0`, sin mirar `ts.freq`; `run_full` la llama sin condición. Con s=1,
`detect_seasonality` no tiene armónicos que contrastar y devuelve un F de
dimensión cero; `plot_seasonality` dibuja una sola barra vacía.

## Fix

- Con `freq == 1`: no ejecutar el contraste ni dibujar la figura; decir en su
  lugar «datos anuales: no hay frecuencias estacionales; D=0 por
  construcción» y pasar a la identificación ARMA.
- Quitar del texto del nodo 3 las rutas B1/B2 y la búsqueda de picos en s, 2s,
  3s cuando freq=1.
- Lo mismo en `run_full` (carril autónomo).
- `describe.py` (~l. 732): no sugerir armónicos cuando `freq == 1`, ni cuando
  D=0 porque el contraste HAC NO detectó estacionalidad (Decisión A). La nota
  debe depender de `freq` y del resultado del nodo 3, no sólo de `D`.
- Si hay un ciclo, decir que en datos anuales es no estacional y se modela con
  la parte AR (raíces complejas), no con diferencias ni armónicos.

## Validation

- MUSKRAT (anual): el nodo 3 no publica ningún F ni figura de estacionalidad y
  dice D=0 por construcción.
- Una serie mensual o trimestral: sin cambios.
- `identification_analysis` sobre una serie anual (p. ej. XLV_F, freq=1): el
  listado no termina en «Añade armónicos cos/sin…».
- Test de regresión con una serie anual en el carril guiado y en `run_full`.

## Resolution (2026-09-30)

- `describe.describe_seasonality`: with freq = 1 it returns at once —
  «datos anuales: no hay frecuencias estacionales; D = 0 por construcción»,
  no figure, `data = {decision: "A", recommended_D: 0, annual: True}`. That
  covers its three callers: node 3 of `guided_identification`, `run_full`
  (the policy reads decision A) and `seasonal_analysis`. A cycle of several
  years is said to be non-seasonal, for the AR and `ar_factorization`.
- Node 3's guide, for annual data, no longer asks for peaks at s, 2s, 3s nor
  offers B1/B2.
- `describe_identification`: the note depends on `freq` — «Datos anuales: sin
  armónicos» and ARIMA, not SARIMA, for freq = 1; for D = 0 in seasonal data
  it says harmonics go with route B1 and not with Decision A, since the
  listing does not know which node 3 took.
- The Q that decides keeps at least `MIN_Q_DF` = 2 degrees of freedom
  (`diagnosis._q_lags_and_df`): if the convention leaves fewer, the lag moves
  up to n_arma + 2 (never beyond n − 2); the residual figure takes the same
  lags (`q_figure_lags`). The same floor as sima and drvarma.

**Validation:** `tests/test_bug_0196_0197_datos_anuales_y_d.py` on the
muskrat: node 3 without an F, a seasonality figure or B1/B2; the listing
without harmonics; an AR(8) on its differenced logs decides at Q(10, 2 g.l.)
instead of Q(9, 1 g.l.).
