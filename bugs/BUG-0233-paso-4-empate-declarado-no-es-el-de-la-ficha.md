---
id: BUG-0233
title: Paso 4: declara el empate «entre ARIMA(1,1,1) y ARIMA(3,1,0)» —el primero y el segundo de la lista— mientras la ficha del empate compara (1,1,1), (1,1,2) y (2,1,1); la lista no va por similitud ni por AICc
status: fixed
severity: low
component: identification
found_in: 0.2.3.dev0 @088933d (+ arreglos sin commit de BUG-0225…0231)
fixed_in: 0.2.3.dev0
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

`python3 bugs/BUG-0233-repro/repro.py` — Salamanca con el `.inp` de BUG-0232-repro;
sale con 1 mientras la recomendación y la ficha nombren candidatos distintos.

`ART_NO_VIEWER=1 python bugs/BUG-0232-repro/repro.py` (Salamanca, precio €/m², 2010:01-2025:08, en un directorio temporal), bloque **0233**. Guion real: `02-practicas/P02-gtkfue-inp-out/solucion_guiada/Salamanca/Salamanca_guion.json` del repositorio del curso.

## Root cause

La recomendación toma los dos primeros de la lista, y la lista no se ordena con el mismo criterio que la banda del empate.

## Fix

El orden de la lista no es un error: es `_nested_parsimony` (BUG-0198), que
recorre bandas de 0,04 de similitud y en cada una pone primero el de menos
parámetros, y a igualdad el puro. En Salamanca, tras sacar el (1,1,1), la banda
siguiente (la del 0,901) recoge también el (3,1,0) y el (4,1,0), y el AR(3), puro
y de tres parámetros, va delante de los mixtos de tres. Lo que estaba mal es que
el aviso y la recomendación leían «los dos primeros», que pueden ser de bandas
distintas, y además con otro umbral (0,05).

En `describe_identification` (`src/art/describe.py`):

- la ambigüedad es la **banda del primer puesto** (los candidatos con
  `tied`, la misma que alimenta la ficha), no la diferencia entre el 1.º y el 2.º;
- el aviso nombra esos candidatos y su diferencia máxima de similitud;
- la recomendación nombra los de la ficha (o los de la banda si no hay ficha):
  «Decisión ambigua entre ARIMA(1,1,1), ARIMA(1,1,2) y ARIMA(2,1,1)»;
- la lista dice su criterio: «por parsimonia dentro de bandas de 0,04 de
  similitud… no por similitud ni por AICc»;
- sin banda de empate: «El patrón favorece el modelo 1: ningún otro candidato
  queda en su banda de empate» (antes, «claramente», con un gap medido contra
  un 2.º que podía ser de otra banda).

`data["ambiguous"]` y `data["top_gap"]` siguen, con el nuevo sentido.

Test: `tests/test_bug_0233_empate_es_el_de_la_ficha.py` — Salamanca: la
recomendación y el aviso nombran (1,1,1), (1,1,2) y (2,1,1), los de la ficha, y
no el (3,1,0); la lista declara su criterio. Fallan sin el arreglo.

## Validation

El repro sale con 0: recomendación y ficha nombran los mismos tres candidatos.
Antes del arreglo salía con 1 («entre ARIMA(1,1,1) y ARIMA(3,1,0)»).
