---
id: BUG-0229
title: El primer modelo estimado cierra el nodo `ordenes` con su orden, aunque sea uno de varios candidatos empatados; la decisión final aparece como «corrección» del analista y el mapa dice «decisión sin modelo estimado detrás»
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
  - empate
references:
  - src/art/mcp_server.py (confirm_and_estimate: cierre del nodo ordenes)
  - src/art/guion.py (guion_map: recuento de nodos sin modelo)
  - BUG-0207
  - bugs/BUG-0225-repro/repro.py
---

## Summary

IPC_ES: el paso 4 declara «empate genuino» entre MA(1) y AR(1) y dice «estima ambos». Al
estimar el MA(1): «◆ guion n5: **ordenes = ARMA(0,1)** — coincide con la propuesta». Se estima el
AR(1) (parent=5), se adopta, y se registra la decisión con `guion_node('ordenes', 'AR(1) (m02)',
criterio='dominio', parent=7)`. `guion_map`: «el analista corrigió 2: n3 d, n9 ordenes» y «1
decisión sin modelo estimado detrás: n9 ordenes (AR(1) (m02))» — su modelo es v7, el adoptado.

## Impact

El guion cuenta la historia al revés: el nodo de órdenes queda fijado en el candidato que se descartó, la decisión real figura como corrección, y el aviso de «decisión sin modelo» es falso.

## Reproduction

`ART_NO_VIEWER=1 python bugs/BUG-0225-repro/repro.py` (recorre el carril guiado de `IPC_ES.inp`, 2002:01-2019:12, desestacionalizado, en un directorio temporal), bloque **0229**. Guion real del caso: `02-practicas/P02-gtkfue-inp-out/solucion_guiada/IPC_ES/IPC_ES_guion.json` del repositorio del curso.

## Root cause

`confirm_and_estimate(guion_path=…)` cierra el nodo `ordenes` pendiente con el orden de la primera estimación, sin mirar si el paso 4 declaró empate. El recuento de «sin modelo detrás» sólo mira descendientes, no el padre (el nodo cuelga del modelo que decide).

## Fix

Con empate declarado, dejar el nodo `ordenes` pendiente hasta `guion_adopt` (o hasta un `guion_node('ordenes')` explícito), y cerrarlo entonces con el orden adoptado y su criterio. Un nodo cuyo padre es un modelo estimado no es una «decisión sin modelo».

## Validation

Repro, bloque 0229: n5 sigue pendiente tras m01; el mapa no cuenta n9 como corrección ni como decisión sin modelo.

## Resolution (2026-10-08)

- Step 4 marks the pending `ordenes` node with the tie (`empate`: the tied candidates). With a tie, `confirm_and_estimate` does NOT close it ("ordenes sigue pendiente — empate declarado…").
- `guion_adopt` closes a pending `ordenes` node with the adopted model's orders and the `why`; choosing ANY tied candidate counts as matching the proposal.
- `guion_node` on a node that is pending CLOSES it instead of appending a second one (same rule for any node); with a tie and no explicit `coincide`, a decision among the tied candidates matches.
- `guion.especificadas_sin_estimar`: a node with `criterio` hanging from an estimated model chooses among estimated models; it is no longer "una decisión sin modelo estimado detrás".

Repro: `bugs/BUG-0225-repro/repro.py`. Tests: `tests/test_bug_0225_0231_guiado_ipc_es.py`.
