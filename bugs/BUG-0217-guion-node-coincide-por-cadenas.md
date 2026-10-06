---
id: BUG-0217
title: guion_node: `coincide` se deduce comparando cadenas («λ=0» frente a «0 (logaritmos)» ⇒ «el analista la CORRIGIÓ»), no admite «parcial», y parent=-1 cuelga el nodo de una versión abandonada
status: fixed
severity: medium
component: guion
found_in: 0.2.3.dev0 @a33b893
fixed_in: 0.2.3.dev0
reported: 2026-10-06
reporter: David / Claude — resolución de la P02 de Econometría Aplicada (UCM) con art en modo autónomo, 15 series y cuatro analistas
tags:
  - guion
  - nodos
  - linaje
references:
  - src/art/mcp_server.py (guion_node)
  - bugs/BUG-0208-repro/repro.py
  - BUG-0207
---

## Summary

- `propuesta="λ=0"`, `decidido="0 (logaritmos)"` ⇒ el mapa dice que el analista corrigió la
  propuesta: falso, es la misma decisión.
- `coincide="parcial"` ⇒ «❌ Error: `coincide` es «sí» o «no»».
- `parent=-1` cuelga el nodo de la última entrada aunque esté abandonada (Salamanca: n15 bajo la
  v14 abandonada).

## Impact

El recuento «el analista corrigió N de M» —que es justo lo que interesa en docencia— sale inflado; y el árbol queda mal.

## Reproduction

`bugs/BUG-0208-repro/repro.py`, bloque 0217.

## Root cause

`coincide` vacío se calcula por igualdad de texto; `parent=-1` no salta las entradas abandonadas.

## Fix

Normalizar antes de comparar (o pedir `coincide` explícito), admitir un tercer valor «parcial», y que -1 apunte a la última entrada viva.

## Validation

Repro, bloque 0217.

## Resolution (2026-10-06)

**Fix.** Tres cosas:

- `coincide` vacío ya no se deduce por igualdad de cadenas: `guion.mismo_valor`
  quita el prefijo `nombre=` y el comentario final entre paréntesis, traduce los
  sinónimos de λ (log, logaritmos ⇒ 0; niveles, identidad ⇒ 1), compara números
  como números y textos sin espacios. Mismo esqueleto con otras cifras
  (ARMA(1,1)/ARMA(1,2), B1/B2) es una corrección; lo que no se puede comparar
  queda sin constar (None) y la salida pide `coincide` explícito, en vez de contar
  una corrección que no hubo.
- `coincide="parcial"` se admite; el mapa lo marca ≈ y lo cuenta aparte.
- `parent=-1` (y todo padre inferido) cuelga de la última entrada VIVA: se sube
  desde la última por sus padres hasta el primer lugar seguro.

El bloque 0217 del repro imprime ahora «λ=0 — el analista la tomó» y acepta
«parcial».

**Validation:** `tests/test_bug_0217_coincide_y_parent.py`.
