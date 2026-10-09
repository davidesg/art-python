---
id: BUG-0227
title: Paso 3: «la recomendación de la tabla es d=0, POR DEBAJO de la d=1 confirmada» justo debajo de una tabla que dice que el único orden con consenso es d=2
status: fixed
severity: low
component: identification
found_in: 0.2.3.dev0 @088933d
fixed_in: 0.2.3.dev0
reported: 2026-10-08
reporter: David / Claude — análisis GUIADO del IPC de España (P02, Econometría Aplicada UCM)
tags:
  - identificacion
  - orden-de-integracion
  - contradiccion
  - regresion
references:
  - src/art/mcp_server.py:5703-5738 (_rec2)
  - BUG-0210 (fixed)
  - bugs/BUG-0225-repro/repro.py
---

## Summary

IPC_ES, `guided_identification(lam=0, d=1)`: la tabla ADF+KPSS en d=0,1,2 concluye «sin
consenso… el único orden con consenso de los dos contrastes es d=2», y el bloque siguiente
dice «→ No hace falta otra diferencia — pero ojo: la recomendación de la tabla es d=0, POR
DEBAJO de la d=1 confirmada». BUG-0210 se arregló en el resumen del paso 2; el del paso 3 sigue
leyendo otra cosa.

## Impact

Dos lecturas contrarias de la misma tabla, una encima de otra, en el nodo donde se enseña a reconocer la diferencia de más.

## Reproduction

`ART_NO_VIEWER=1 python bugs/BUG-0225-repro/repro.py` (recorre el carril guiado de `IPC_ES.inp`, 2002:01-2019:12, desestacionalizado, en un directorio temporal), bloque **0227**. Guion real del caso: `02-practicas/P02-gtkfue-inp-out/solucion_guiada/IPC_ES/IPC_ES_guion.json` del repositorio del curso.

## Root cause

`_rec2` (`recommended_d` de `unit_root_analysis`) sale 0 cuando ningún orden tiene consenso y se usa como si fuera la recomendación; el resumen de la tabla, en cambio, usa el orden con consenso.

## Fix

Que la rama `_rec2 < d` lea el mismo veredicto que el resumen (orden con consenso, o «sin consenso»), y no diga «recomendación d=0» cuando la tabla no recomienda nada.

## Validation

Repro, bloque 0227: no aparece «recomendación de la tabla es d=0» si la tabla dice «único orden con consenso … d=2».

## Resolution (2026-10-08)

**One step at a time, in one place** (David, 8-oct-2026: "no se puede pasar de d=0 a d=2 en una sola iteración… sólo a partir de d=0 se puede sugerir d=1, y luego de d=1 a d=2. Si hay estacionalidad no tratada los contrastes tienen baja potencia").

- `describe_unit_root(current_d=d)` tabulates only rows d and d+1: rows below the confirmed d are gone, so `recommended_d` can no longer fall below it and the step-3 branch "la recomendación de la tabla es d=0, POR DEBAJO…" is removed with the row that produced it.
- New `policy._un_paso_desde`, used by `decide_d` and `razon_d`: never below `current_d`; from d ≥ 1 the next difference needs BOTH tests to see a unit root at d (the step-3 rule of BUG-0197). The autonomous lane, which took the second step through `recommended_d` (ADF only), now follows the same rule.
- Step 3 with seasonality detected now SAYS why the d→d+1 question is not asked (untreated seasonality takes the power of ADF/KPSS; treat it first). Step 2 says that from d=0 only d=1 is proposed because seasonality has not been tested yet.
- `describe_seasonality`: with the ADF rejecting and only the KPSS dissenting, the row is "ambigua" and no longer "queda abierta la pregunta de una diferencia más"; Decision A no longer says "o d=2 si los tests lo sugieren".

Tests updated to the new contract: `test_bug_0023_…::test_el_tercer_caso…` (no d=0 row in step 3), `test_bug_0210_…::test_ipc_es_nombra…` (rows [1, 2], recommended 1).

Repro: `bugs/BUG-0225-repro/repro.py`. Tests: `tests/test_bug_0225_0231_guiado_ipc_es.py`.
