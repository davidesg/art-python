---
id: BUG-0232
title: formal_tests sobre un AR(4): la subdiferenciación da LR = −inf con θ̂ = 0,659 y lo publica como «testigo NO invertible, con d−1 bastaba», y la salida cierra «El modelo es adecuado» debajo de «el orden de integración NO está fijado»
status: fixed
severity: high
component: formal-tests
found_in: 0.2.3.dev0 @088933d (+ arreglos sin commit de BUG-0225…0231)
fixed_in: 0.2.3
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

(1) La causa del −inf es la de BUG-0224: con θ = 1 el AR(4) libre ponía una
raíz EXACTAMENTE en 1 (0,99999999948 en Chamartín), se cancelaba con el MA
unitario y la verosimilitud restringida se iba a +∞. La cota en ρₘ de
`_frontera_theta_uno` (`src/art/formal_tests.py:973`) la quita: Chamartín da
LR 14,546 y Salamanca 8,739, finitos, «la ∇ es genuina».

Y lo que siga sin ser un estadístico no es un veredicto:
`DCDResult.calculable` (l. 763) exige un LR finito y ≥ −1e−3
(`_TOL_LR`, l. 215); `rejects_*` es falso si no lo es y `summary()` dice «NO
CALCULABLE». En `describe.py` el bloque lo dice («no calculable — motivo») y el
lado no entra en el par (`od_nc`, l. 2713; estado `no_calculable` del lado d−1).

(2) El cierre lee los dos lados (`describe.py:3455`): un DCD de
sobrediferenciación no calculable, un lado d−1 «cancelada», «no concluyente»
o «no calculable» van a `pendientes`, y con pendientes el cierre ya no es
«El modelo es adecuado».

Test: `tests/test_bug_0232_lr_menos_inf.py` — Chamartín da LR finito,
acotado y ≥ crítico; el informe no publica −inf ni «bastaba»; un LR −inf es
`calculable` falso; con −inf simulado el bloque dice «no calculable» y el
cierre no es «adecuado»; con «por ABAJO no cierra» el cierre dice «no
cierran». Falla sin el arreglo (5 de 5).

## Validation

`bugs/BUG-0232-repro/repro.py` sale con 0 (con HEAD, 1). El código de salida es
el de BUG-0232 (Salamanca y Chamartín); los bloques 0233 y 0234 siguen
imprimiendo sin decidir la salida. Salamanca m01: «θ̂=+0.6587, LR=8.739 → la ∇
es genuina», el par en f=0 coincide y por abajo cierra: el «adecuado» final es
coherente con lo que se imprime encima.

## Addendum (2026-10-09) — Chamartín

Se reproduce en un segundo distrito: AR(4) con μ en d=1 (`BUG-0232-repro/Chamartin_m02.pre`).
La subdiferenciación da θ̂ = +0,6743 con LR = −inf, y lo publica como «testigo NO invertible
(θ→+1) → la ∇ está CANCELADA → con d−1 bastaba ✗», a la vez que el SF y el DCD de
sobrediferenciación sostienen d ≥ 1. Con un θ̂ de 0,67 el «θ→+1» es falso.
