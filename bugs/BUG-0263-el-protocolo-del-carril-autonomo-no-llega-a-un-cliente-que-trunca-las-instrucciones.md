---
id: BUG-0263
title: El protocolo del carril autónomo no llega a un cliente que trunca las instrucciones del servidor, y ninguna herramienta lo sirve
status: open
severity: high
component: mcp
found_in: 0.2.6
fixed_in:
reported: 2026-11-22
reporter: David / Claude — medición del coste de un univariante autónomo para la ruta V de sima (IPC y WTI de EE. UU.)
tags:
  - mcp
  - carril-autonomo
  - instrucciones
references:
  - src/art/mcp_server.py _INSTRUCTIONS («EL CARRIL AUTÓNOMO — TÚ ERES EL ANALISTA»)
  - docs/ESTUDIO-carril-autonomo-para-sima.md
  - bugs/BUG-0263-repro/repro.py
---

## Summary

Las instrucciones del servidor miden unos 49.000 caracteres. La sección que
dice cómo se trabaja en el carril autónomo —los nodos en orden,
`modo="autonomo"`, el guion, las reglas— empieza hacia el carácter 19.000. Un
cliente que solo entrega al modelo los primeros miles de caracteres (medido:
unos 4.000 el 2026-11-22) le da la pregunta inicial y la frase «sigue "EL
CARRIL AUTÓNOMO — TÚ ERES EL ANALISTA", más abajo», y nada de lo de «más
abajo». Tampoco hay herramienta ni recurso que devuelva esa sección.

## Impact

Sin esa sección un agente no sabe el orden de los nodos, ni que el carril se
declara en cada llamada, ni que debe registrar los nodos en el guion. Es el
camino por el que el autónomo se reducía a una llamada a `build_model`
(BUG-0180). En la medición, los dos agentes tuvieron que leer la sección del
código fuente del servidor, que puede no ser el instalado.

## Reproduction

`bugs/BUG-0263-repro/repro.py`. Sale con 1 mientras la sección quede más
allá de lo que el cliente entrega y no haya una herramienta que la sirva y
que se nombre al principio de las instrucciones.

## Fix propuesto

Mínimo, sin tocar la arquitectura de las instrucciones (su reforma está
pendiente): una herramienta `protocolo_autonomo()` que devuelve esa sección
tal cual, y una línea al principio de las instrucciones, junto a la pregunta
inicial, que manda llamarla si no se ve la sección.
