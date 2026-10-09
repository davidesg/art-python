---
id: BUG-0234
title: guion_map cuenta como «decisión sin modelo estimado detrás» un nodo que concluye sobre modelos ya estimados (nodo d = «ambiguo», colgado del modelo adoptado)
status: open
severity: low
component: guion
found_in: 0.2.3.dev0 @088933d (+ arreglos sin commit de BUG-0225…0231)
fixed_in:
reported: 2026-10-08
reporter: David / Claude — análisis GUIADO de Salamanca (P02, Econometría Aplicada UCM)
tags:
  - guion
  - mapa
  - nodos
references:
  - src/art/guion.py (especificadas_sin_estimar)
  - BUG-0221, BUG-0229
  - bugs/BUG-0232-repro/repro.py
---

## Summary

Salamanca: tras adoptar el AR(4) (d=1) y el IMA(1) (d=2), el analista escribe el nodo
`d = ambiguo: I(1) con el AR(4), I(2) con el IMA(1); los dos modelos son adecuados`, colgado de
v8. El mapa: «1 decisión sin modelo estimado detrás: n9 d (ambiguo…)». No especifica nada que
estimar: concluye sobre lo estimado.

## Impact

Ruido en el mapa justo en el nodo que resume el análisis.

## Reproduction

`ART_NO_VIEWER=1 python bugs/BUG-0232-repro/repro.py` (Salamanca, precio €/m², 2010:01-2025:08, en un directorio temporal), bloque **0234**. Guion real: `02-practicas/P02-gtkfue-inp-out/solucion_guiada/Salamanca/Salamanca_guion.json` del repositorio del curso.

## Root cause

`especificadas_sin_estimar` sólo exime los nodos con `criterio` que cuelgan de un modelo (BUG-0229); un nodo de especificación (d, ordenes…) colgado de un modelo se lee siempre como reformulación pendiente.

## Fix

Un nodo que cuelga de un modelo y no tiene descendientes no es necesariamente una reformulación: o se permite marcarlo como conclusión (p. ej. `guion_node(…, conclusion=True)` o `nodo="conclusion"`), o el mapa dice «nodo final sobre v8» en lugar de «decisión sin modelo».

## Validation

Repro, bloque 0234: el nodo final no aparece como decisión sin modelo.
