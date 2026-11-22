---
id: BUG-0262
title: guided_identification no tiene `modo` — en el carril autónomo sus figuras viajan como imagen en cada llamada
status: open
severity: medium
component: mcp
found_in: 0.2.6
fixed_in:
reported: 2026-11-22
reporter: David / Claude — medición del coste de un univariante autónomo para la ruta V de sima (IPC y WTI de EE. UU.)
tags:
  - mcp
  - carril-autonomo
  - figuras
  - tokens
references:
  - src/art/mcp_server.py guided_identification (sin `modo` ni `con_figuras`)
  - src/art/mcp_server.py _figuras_por_carril / _figuras_del_carril (BUG-0208)
  - docs/ESTUDIO-carril-autonomo-para-sima.md
  - bugs/BUG-0262-repro/repro.py
---

## Summary

Desde BUG-0208, las herramientas con carril (`confirm_and_estimate`,
`estimate_and_diagnose`, `guided_intervention`, `suggest_intervention_form`)
guardan sus figuras junto al modelo cuando se llaman con `modo="autonomo"` y
no las devuelven como imagen. `guided_identification`, la herramienta de los
primeros nodos (λ, d, estacionalidad, órdenes), no tiene `modo`: devuelve sus
figuras siempre, y las deja solo en el directorio temporal.

## Impact

En un análisis autónomo son 4 de unas 20 llamadas, las primeras, así que sus
imágenes se reenvían en todos los turnos siguientes. Medido el 2026-11-22
con un agente en el carril autónomo: el IPC de EE. UU. costó 131.000 tokens y
el WTI, una serie sin estacionalidad y con una sola intervención, 111.000. La
serie fácil cuesta casi lo mismo que la difícil: el coste fijo por serie pesa
más que el análisis, y los dos agentes señalaron esta herramienta como el
mayor coste por llamada.

## Reproduction

`bugs/BUG-0262-repro/repro.py` (con `WTI.inp`). Sale con 1 mientras la
herramienta no acepte `modo`, o mientras en autónomo devuelva imágenes o no
las guarde junto al modelo; con 2 si el carril guiado deja de enseñarlas.

## Fix propuesto

`modo` y `con_figuras` en la firma, y el decorador `_figuras_por_carril` que
ya llevan las otras. Aquí el carril solo decide si las figuras viajan: la
herramienta no cambia nada más.
