---
id: BUG-0186
title: La lista de objetivos se sigue reformulando con BUG-0183 dentro — el protocolo no basta, porque la pregunta se hace con la herramienta del cliente antes de llamar a art
status: open
severity: medium
component: protocolo
found_in: 0.2.1 @7d59ae1
fixed_in:
reported: 2026-09-12
reporter: David — run 9 de IPC_ES (Claude, Linux)
tags:
  - objetivo
  - protocolo
  - multivariante
references:
  - BUG-0183
  - BUG-0180
---

## Summary

BUG-0183 cerró dos de las tres vías por las que se perdía el objetivo:
`objetivo` viaja como enum en el esquema y lo desconocido se rechaza en vez de
caer en «univariante». La tercera —**que el asistente presente las tres opciones
tal cual**— se confió al protocolo: *«PRESÉNTALAS TAL CUAL: LAS TRES, CON ESOS
NOMBRES»*.

No se sostiene:

    run7 (0.2.1 @c9a2b02)   UNIVARIANTE · MULTIVARIANTE · ESTRUCTURAL      ✓ tal cual
    run9 (0.2.1 @7d59ae1)   Predicción · Análisis estructural · Ambos / docencia   ✗

Mismo protocolo y mismo LLM, y en run9 **desaparece otra vez multivariante**, que
es la única opción que veta algo.

## Root cause

La pregunta no la hace art. La compone el asistente con la herramienta de
preguntas **del cliente** (`AskUserQuestion` en Claude Code), **antes de cualquier
llamada a art**, a partir de la prosa del protocolo. El enum del esquema protege
el valor que art recibe, pero no lo que se le ofrece al usuario: una lista mal
compuesta deja fuera la opción antes de que art intervenga.

Es la enfermedad de siempre: una propiedad que se sostiene porque el asistente se
acuerda de copiar un texto es una costumbre, no una propiedad del sistema.

## Impact

Un usuario que necesita el modelo para un sistema (VECM, transferencia, VARMA)
no ve la opción. Puede escribirla a mano en «Otro», pero sólo si ya sabe que
existe. La consecuencia es la de BUG-0183: estacionalidad estocástica en un
modelo que tenía que ser comparable.

Decisión del analista, 12-sep: **para 0.3**. La 0.2.1 sale con el enum y el
rechazo, que evitan el daño silencioso en art; queda el de la lista.

## Fix propuesto (0.3)

Que la pregunta la genere **art** y no el protocolo:

- una herramienta —o la salida de la primera que se llame, `load_data` /
  `preview_data`— que devuelva la pregunta con las tres opciones exactas, en la
  forma que el cliente pinta tal cual;
- y que las herramientas del nodo estacional **exijan** `objetivo` en el carril
  autónomo, en vez de tomar «univariante» por defecto: si falta, que lo digan
  y pidan preguntarlo.

## Validation propuesta

Un test sobre la salida de esa herramienta —las tres opciones, con sus valores—,
y un run sin enunciado donde la lista salga tal cual en varias sesiones, no en
una.
