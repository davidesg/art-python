---
id: BUG-0233
title: Paso 4: declara el empate «entre ARIMA(1,1,1) y ARIMA(3,1,0)» —el primero y el segundo de la lista— mientras la ficha del empate compara (1,1,1), (1,1,2) y (2,1,1); la lista no va por similitud ni por AICc
status: open
severity: low
component: identification
found_in: 0.2.3.dev0 @088933d (+ arreglos sin commit de BUG-0225…0231)
fixed_in:
reported: 2026-10-08
reporter: David / Claude — análisis GUIADO de Salamanca (P02, Econometría Aplicada UCM)
tags:
  - identificacion
  - empate
  - texto
references:
  - src/art/describe.py:994 (rec «Decisión ambigua entre»)
  - src/art/describe.py (lista de candidatos y ficha)
  - bugs/BUG-0232-repro/repro.py
---

## Summary

Salamanca, `guided_identification(lam=0, d=1, D=0)`. La lista:
1. (1,1,1) sim 0,914 ΔAICc 0 · 2. (3,1,0) sim 0,868 ΔAICc +8,7 · 3. (1,1,2) sim 0,901 · 4. (2,1,1)
sim 0,901 · 5. (4,1,0) sim 0,866 ΔAICc +4,3.

- El aviso dice «los dos primeros candidatos difieren en sólo 0.047 de similitud» y la
  recomendación «Decisión ambigua entre ARIMA(1,1,1) y ARIMA(3,1,0)».
- La ficha del «empate genuino» (banda de 0,04) compara (1,1,1), (1,1,2) y (2,1,1): el AR(3) no
  está en ella.
- El orden de la lista no es el de la similitud (0,868 por delante de 0,901) ni el del AICc.

## Impact

El alumno estima los dos que nombra la recomendación —(1,1,1) y AR(3)— que no son los empatados; y el AR(4), la lectura de la FAP, sale el último.

## Reproduction

`ART_NO_VIEWER=1 python bugs/BUG-0232-repro/repro.py` (Salamanca, precio €/m², 2010:01-2025:08, en un directorio temporal), bloque **0233**. Guion real: `02-practicas/P02-gtkfue-inp-out/solucion_guiada/Salamanca/Salamanca_guion.json` del repositorio del curso.

## Root cause

La recomendación toma los dos primeros de la lista, y la lista no se ordena con el mismo criterio que la banda del empate.

## Fix

Que la recomendación nombre los candidatos de la banda del empate (los de la ficha) y que la lista diga por qué criterio está ordenada (o se ordene por similitud).

## Validation

Repro, bloque 0233: la recomendación y la ficha nombran los mismos candidatos.
