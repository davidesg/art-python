---
id: BUG-0221
title: guion_map afirma «1 especificada sin estimar» cuando todas las versiones están estimadas
status: fixed
severity: low
component: guion
found_in: 0.2.3.dev0 @a33b893
fixed_in: 0.2.3.dev0
reported: 2026-10-06
reporter: David / Claude — resolución de la P02 de Econometría Aplicada (UCM) con art en modo autónomo, 15 series y cuatro analistas
tags:
  - guion
  - mapa
references:
  - src/art/mcp_server.py (guion_map)
---

## Summary

Moncloa (P02): el mapa dice «1 especificada(s) sin estimar»; no hay ninguna. También en el ES_CPI de la P04.

## Impact

Ruido en el mapa, que es lo que se enseña a leer.

## Reproduction

`guion_map` sobre `02-practicas/P02-gtkfue-inp-out/solucion/Moncloa/Moncloa_guion.json` del repositorio del curso.

## Root cause

Probablemente cuenta un nodo, o una entrada de `record_version` (re-registro), como versión sin estimar.

## Fix

Contar sólo entradas de modelo sin estimación.

## Validation

El mapa de Moncloa sin el aviso.

## Resolution (2026-10-06)

**Fix.** `iteraciones` abre una iteración con cualquier nodo y la cierra con un
modelo, así que un nodo FINAL que no especifica nada —el nodo «prevision» del
guion de la P04— contaba como «especificada sin estimar». El mapa cuenta ahora
sólo las iteraciones abiertas que llevan un nodo de especificación (λ,
estacionalidad, d, órdenes, media, intervenciones, reformulación), y las nombra.
Sobre `ES_CPI_guion_aula.json` el aviso desaparece. No se pudo comprobar
Moncloa (el repositorio del curso no está aquí); la prueba reproduce la forma
del guion de la P04.

**Validation:** `tests/test_bug_0221_especificada_sin_estimar.py`.

**Moncloa (2026-10-06), comprobado sobre el guion real del curso.** El aviso
no era falso: el nodo final n14 (reformulación) deja pendientes tres
intervenciones. Lo engañoso era la frase: «especificada sin estimar» sugería un
modelo escrito y no estimado, y el ARIMA(1,2,2) que describe n14 sí está
estimado (v7, v13). El mapa dice ahora qué queda abierto y lo que se decidió:

    1 decisión sin modelo estimado detrás: n14 reformulacion (vuelvo al nodo d: d=2; ARMA(1,2) en ∇²ln z sin μ — NO está terminado: falta intervenir 2010:08, 2012:05 y 2018:02 (JB)).
