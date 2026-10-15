---
id: BUG-0234
title: guion_map cuenta como «decisión sin modelo estimado detrás» un nodo que concluye sobre modelos ya estimados (nodo d = «ambiguo», colgado del modelo adoptado)
status: fixed
severity: low
component: guion
found_in: 0.2.3.dev0 @088933d (+ arreglos sin commit de BUG-0225…0231)
fixed_in: 0.2.3
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

`python3 bugs/BUG-0234-repro/repro.py` (Salamanca.inp copiado de BUG-0232-repro): AR(4)
y el nodo final `d = ambiguo` colgado de él como conclusión; sale con 1 mientras el bug
siga abierto. Original: `ART_NO_VIEWER=1 python bugs/BUG-0232-repro/repro.py` (Salamanca, precio €/m², 2010:01-2025:08, en un directorio temporal), bloque **0234**. Guion real: `02-practicas/P02-gtkfue-inp-out/solucion_guiada/Salamanca/Salamanca_guion.json` del repositorio del curso.

## Root cause

`especificadas_sin_estimar` sólo exime los nodos con `criterio` que cuelgan de un modelo (BUG-0229); un nodo de especificación (d, ordenes…) colgado de un modelo se lee siempre como reformulación pendiente.

## Fix

La primera de las dos propuestas: la conclusión se DECLARA. La segunda —que el mapa diga
«nodo final sobre v8» para todo nodo de especificación colgado de un modelo y sin nada
debajo— no vale: es exactamente la forma de una reformulación pendiente («d = 2» colgado
de v8, a falta de estimar), que es lo que BUG-0221 quiere que el mapa avise. Por la forma
del árbol las dos son indistinguibles; sólo el analista sabe cuál escribió.

- `guion_node(..., conclusion=True)` (`src/art/mcp_server.py`) guarda `conclusion` en el
  nodo (también al cerrar un nodo pendiente) y lo dice en la respuesta («∎ conclusión
  sobre v8»). Exige que cuelgue de un MODELO: colgada de un nodo o de nada se rechaza con
  la razón, para que la marca no pueda tapar una especificación pendiente.
- `especificadas_sin_estimar` (`src/art/guion.py`) exime, como ya hacía con `criterio`
  (BUG-0229), el nodo con `conclusion` que cuelga de un modelo.
- `guion_map` marca esos nodos con «∎ conclusión».

Sin la marca nada cambia: el bloque 0234 del repro de BUG-0232, que escribe el nodo sin
ella, sigue listándolo, y con razón — el mapa no puede saber que es una conclusión.

Test: `tests/test_bug_0234_nodo_conclusion.py` — con la marca el nodo no cuenta y el mapa
lo dibuja como conclusión; sin ella sigue contando (BUG-0221); colgada de un nodo se
rechaza. Falla sin el arreglo.

## Validation

`python3 bugs/BUG-0234-repro/repro.py` sale con 0: el mapa de Salamanca ya no tiene la
línea «decisión sin modelo estimado detrás».
