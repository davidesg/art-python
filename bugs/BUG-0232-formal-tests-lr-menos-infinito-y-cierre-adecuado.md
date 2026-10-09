---
id: BUG-0232
title: formal_tests sobre un AR(4): la subdiferenciación da LR = −inf con θ̂ = 0,659 y lo publica como «testigo NO invertible, con d−1 bastaba», y la salida cierra «El modelo es adecuado» debajo de «el orden de integración NO está fijado»
status: open
severity: high
component: formal-tests
found_in: 0.2.3.dev0 @088933d (+ arreglos sin commit de BUG-0225…0231)
fixed_in:
reported: 2026-10-08
reporter: David / Claude — análisis GUIADO de Salamanca (P02, Econometría Aplicada UCM)
tags:
  - formal-tests
  - dcd
  - subdiferenciacion
  - contradiccion
references:
  - src/art/formal_tests.py:858 (dcd_underdiff_regular)
  - src/art/describe.py:3241 (cierre «no detectan problemas»)
  - BUG-0224 (misma familia: subdiferenciación con AR libre)
  - BUG-0215 (cierre «adecuado» con el par discrepando)
  - bugs/BUG-0232-repro/repro.py
---

## Summary

Salamanca, m01 = AR(4) con μ en ∇ln, `formal_tests(subdiferenciacion=True)`:

- «DCD sub-diferenciación regular … θ̂=+0.6587, **LR=-inf** (crít 5%=1.94) → testigo NO invertible
  (θ→+1) → la ∇ está CANCELADA → con d−1 bastaba ✗». Un θ̂ de 0,66 es invertible, y un LR de −inf
  no es un estadístico: es un fallo numérico (la verosimilitud restringida no puede superar a la
  libre por infinito). Concluir de ahí d−1 = 0 para el ln de un precio es absurdo.
- El par en f=0 dice «⚠ Pero por ABAJO no cierra … El orden de integración NO está fijado» y la
  última línea de la salida es «Los contrastes formales no detectan problemas. El modelo es
  adecuado.»

## Impact

Es el contraste que decide el orden de integración. Un −inf leído como veredicto manda a estimar d−1; el cierre contradictorio lo tapa. Lo vio el analista; un alumno se quedaría con la última línea.

## Reproduction

`ART_NO_VIEWER=1 python bugs/BUG-0232-repro/repro.py` (Salamanca, precio €/m², 2010:01-2025:08, en un directorio temporal), bloque **0232**. Guion real: `02-practicas/P02-gtkfue-inp-out/solucion_guiada/Salamanca/Salamanca_guion.json` del repositorio del curso.

## Root cause

Dos: (1) el veredicto del testigo se decide sólo por el LR (ya señalado en BUG-0224), sin comprobar que el LR sea finito ni mirar θ̂; (2) el cierre de `describe.py:3241` no lee el veredicto del par en f=0 (la misma familia que BUG-0215).

## Fix

(1) Un LR no finito (o negativo) es «contraste no calculable» —se dice así, con θ̂—, nunca un veredicto. El texto «NO invertible» sólo con θ̂ en la frontera. (2) El cierre lee el par: si «por abajo no cierra» o algún lado no es calculable, no dice «adecuado».

## Validation

Repro, bloque 0232: sin «LR=-inf … con d−1 bastaba» y sin «El modelo es adecuado» bajo un par que no cierra.

## Addendum (2026-10-09) — Chamartín

Se reproduce en un segundo distrito: AR(4) con μ en d=1 (`BUG-0232-repro/Chamartin_m02.pre`).
La subdiferenciación da θ̂ = +0,6743 con LR = −inf, y lo publica como «testigo NO invertible
(θ→+1) → la ∇ está CANCELADA → con d−1 bastaba ✗», a la vez que el SF y el DCD de
sobrediferenciación sostienen d ≥ 1. Con un θ̂ de 0,67 el «θ→+1» es falso.
