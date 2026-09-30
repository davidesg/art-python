---
id: BUG-0197
title: El nodo 3 recomienda d=2 y d=1 en la misma salida — «Considera d=2», «Punto de partida recomendado d=1, no 2» y «La evidencia apunta a d=2. Reentra con d=2» salen de tres sitios distintos del código
status: fixed
severity: medium
component: identification
found_in: 0.2.3.dev0
fixed_in: 0.2.3.dev0
reported: 2026-09-29
reporter: David / Claude — análisis guiado de la rata almizclera (Jenkins y Alavi 1981)
tags:
  - differencing
  - guided
  - contradiction
references:
  - src/art/describe.py (~l. 375, «Considera d=2»; ~l. 503, «Punto de partida recomendado: d = …, no …»)
  - src/art/mcp_server.py::guided_identification (~l. 5121, «La evidencia apunta a d=… Reentra con …»)
---

## Summary

Sobre ∇ln de la rata almizclera (ADF p=0.14 no rechaza, KPSS p=0.10 acepta;
d=2 estacionaria por los dos), el paso 3 de `guided_identification` emite en la
MISMA salida tres recomendaciones sobre d:

1. «⚠ Los tests de raíz unitaria sugieren que ∇log(y) puede no ser
   estacionaria. **Considera d=2**.»
2. «⚠ **Punto de partida recomendado: d = 1, no 2.** Un paso cada vez…»
3. «→ La evidencia apunta a **d=2**. **Reentra** con
   `guided_identification(inp_path, lam=0.0, d=2)`.»

y termina con la llamada siguiente con d=1. El analista no sabe cuál manda.

## Impact

Medio. La política documentada es la 2 (un paso cada vez; el contraste de
verdad sobre d es Shin-Fuller y el DCD de sobrediferenciación sobre el modelo
estimado), pero la 3 lleva una LLAMADA concreta a d=2, y un asistente o un
alumno que siga la última instrucción ejecutable sobrediferencia. En esta
serie (anual, con un ciclo de ~10 años que resta potencia al ADF) d=2 es
precisamente el error: Jenkins y Alavi la modelan con d=1.

## Reproduction

```python
from art.mcp_server import guided_identification
out = guided_identification(
    inp_path=".../ART/Data/cases/MINK_MUSKRAT/MUSKRAT.inp",
    lam=0.0, d=1, objetivo="multivariante")
# «Considera d=2» · «Punto de partida recomendado: d = 1, no 2» ·
# «La evidencia apunta a d=2. Reentra con … d=2»
```

## Root cause

Tres bloques escriben sobre d sin coordinarse: `describe.py` (~375) añade
«Considera d=2» cuando el ADF no rechaza sobre ∇; `describe.py` (~503) aplica
la política de un paso («d = 1, no 2»); `mcp_server.py` (~5121) añade la
invitación a reentrar con el d de la tabla ADF+KPSS (`_rec2`).

## Fix

Una sola decisión, la de la política (un paso cada vez), publicada una vez:
la tabla ADF+KPSS se presenta como evidencia, la recomendación es la de la
política, y la invitación a reentrar con d+1 sólo aparece cuando la política
la respalda. Si la evidencia pide más diferencias de las que la política
aconseja, se dice como salvedad («los contrastes piden d=2; se empieza en d=1
y lo decide Shin-Fuller sobre el modelo»), no como otra instrucción.

## Validation

- MUSKRAT, paso 3: una sola recomendación sobre d, y la llamada siguiente
  coherente con ella.
- Una serie I(2) (IPC de Chile de la tesis): la salvedad aparece y el flujo
  llega a d=2 por el contraste final, como hoy (test_thesis_i2_chile_colombia).

## Resolution (2026-09-30)

One decision about d, the policy's, said once:

- `describe_unit_root(..., current_d=)`: the «starting point» advice
  («d = 1, no 2… desde d=0») answers the question asked FROM THE LEVEL and is
  only written when `current_d == 0`. Node 3 passes `current_d=d`.
- `describe_seasonality`: «Considera d=2» becomes evidence — the ADF on ∇
  does not reject, the question of one more difference stays open and is
  answered with ADF+KPSS at d+1 and Shin-Fuller on the model.
- Node 3's verdict: another difference is invited (with the call) only when
  BOTH tests at the current d see a unit root. When they disagree — the
  muskrat: ADF p = 0.14, KPSS accepts — it says «se sigue con d=1», with the
  caveat that Shin-Fuller and the DCD decide on the estimated model; no call
  to re-enter with d = 2.

**Validation:** `tests/test_bug_0196_0197_datos_anuales_y_d.py`: on the
muskrat, node 3 carries neither «Considera d=2», nor «Punto de partida
recomendado», nor «Reentra con», and says «Se sigue con d=1».
