---
id: BUG-0264
title: El protocolo del carril autónomo no manda el nodo de intervenciones a la propuesta de art ni dice que las formas van en niveles
status: fixed
severity: medium
component: mcp
found_in: 0.2.6
fixed_in: 0.2.7
reported: 2026-11-25
reporter: David / Claude — rodaje autónomo de sima (VAR monetario de EE. UU., univariantes en art con art_brief)
tags:
  - mcp
  - carril-autonomo
  - intervenciones
references:
  - src/art/mcp_server.py _INSTRUCTIONS («EL CARRIL AUTÓNOMO — TÚ ERES EL ANALISTA», nodo 7)
  - bugs/BUG-0264-repro/repro.py
---

## Summary

El nodo 7 del protocolo autónomo decía solo «intervenciones si los anómalos
distorsionan la identificación, ANTES de (p,q). Una cada vez». No mandaba
pedir la forma a `suggest_intervention_form` ni decía que fue especifica las
intervenciones en NIVELES. Un agente que lee el residuo en diferencias ve un
pico y escribe un impulso, cuando en el nivel es un escalón; o fija a mano
una intervención que art no propuso.

## Impact

En el rodaje autónomo de sima (2026-11-25) el agente del IPC fijó a mano un
segundo escalón (11/2005) sin propuesta de art. A juicio del analista, art
acierta casi siempre en la especificación (a veces sobreparametriza, un error
menor); usar un impulso donde va un escalón es el error grave, y es el que el
protocolo no prevenía. art ya hace bien la traducción a niveles: faltaba
mandar al agente allí.

## Reproduction

`python3 bugs/BUG-0264-repro/repro.py` sale con 1 mientras el nodo 7 no
nombre `suggest_intervention_form`, no diga NIVELES y el escalón, y no limite
el apartarse a una razón escrita.

## Root cause

El nodo 7 del protocolo (en `_INSTRUCTIONS`, servido también por
`protocolo_autonomo()`) no recogía la regla: la regla general «la
recomendación de art es evidencia, no una orden» deja al agente apartarse,
pero nada le obligaba a pedir antes la propuesta.

## Fix

Cambio mínimo, solo de texto, en el nodo 7: la forma la propone
`suggest_intervention_form`, que especifica en niveles; no se traduce a mano
la forma del residuo (un pico aislado en las diferencias es un escalón en el
nivel); el agente puede apartarse con su razón escrita en el guion, nunca sin
haberla pedido. Las herramientas no cambian.

## Validation

El repro pasa a 0. Las pruebas del servidor y del protocolo autónomo
(BUG-0263) siguen pasando.
