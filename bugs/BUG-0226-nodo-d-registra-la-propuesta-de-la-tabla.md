---
id: BUG-0226
title: Nodo d: el texto recomienda d=1 pero el guion registra «propuesta: 0» (la de la tabla ADF+KPSS que el propio texto descarta), y al confirmar d=1 el mapa dice «✎ el analista corrigió»
status: fixed
severity: medium
component: guion
found_in: 0.2.3.dev0 @088933d
fixed_in: 0.2.3.dev0
reported: 2026-10-08
reporter: David / Claude — análisis GUIADO del IPC de España (P02, Econometría Aplicada UCM)
tags:
  - guion
  - nodos
  - orden-de-integracion
  - regresion
references:
  - src/art/mcp_server.py:6676-6690 (pendiente), :6734 (corrige la propuesta)
  - BUG-0207 (nodos de la identificación), BUG-0217 (coincide)
  - bugs/BUG-0225-repro/repro.py
---

## Summary

Paso 2 de `guided_identification` con IPC_ES: el texto dice «⚠ Punto de partida: d = 1… la
tabla, sola, apuntaría a d=0: es apoyo, no veredicto» y la línea del guion dice «◆ guion n3: **d**
pendiente (propuesta: 0)». Al confirmar d=1: «d = 1 — **corrige la propuesta** (0)», y
`guion_map` cuenta «el analista corrigió 2» (n3 entre ellas).

## Impact

El recuento «el analista corrigió N de M» es la medida docente del carril guiado, y sale falsa en la decisión más común (d=1 sobre un índice de precios con ADF/KPSS ambiguos).

## Reproduction

`ART_NO_VIEWER=1 python bugs/BUG-0225-repro/repro.py` (recorre el carril guiado de `IPC_ES.inp`, 2002:01-2019:12, desestacionalizado, en un directorio temporal), bloque **0226**. Guion real del caso: `02-practicas/P02-gtkfue-inp-out/solucion_guiada/IPC_ES/IPC_ES_guion.json` del repositorio del curso.

## Root cause

La propuesta del nodo se toma de `recommended_d` de la tabla ADF+KPSS, no de la recomendación final del paso (que la sobreescribe con la regla de tendencia).

## Fix

Registrar como propuesta el valor que el texto recomienda (la misma variable que imprime «Recomendación: d = …»).

## Validation

Repro, bloque 0226: «pendiente (propuesta: 1)» y, al confirmar d=1, «coincide con la propuesta».

## Resolution (2026-10-08)

Step 2 records the d the text RECOMMENDS (`recommended_d_policy`), not the raw ADF+KPSS row: IPC_ES now reads "d pendiente (propuesta: 1)" and, on confirming d=1, "coincide con la propuesta". Part of the one-step rule below (BUG-0227).

Repro: `bugs/BUG-0225-repro/repro.py`. Tests: `tests/test_bug_0225_0231_guiado_ipc_es.py`.
