---
id: BUG-0148
title: Dos reglas de la cabecera se debilitaron al acortarla —la pregunta inicial y el idioma— y las pruebas que las guardaban siguieron en verde
status: fixed
severity: high
component: mcp-tools
found_in: 0.2.2
fixed_in: 0.2.2
reported: 2026-09-10
reporter: David — al ver que el asistente no preguntaba el modo
tags:
  - semaforo
  - fase-1
references:
  - BUG-0116
  - ORDEN.md fase 1.1
---

## Summary

El protocolo abre con una pregunta obligatoria —guiado o autónomo— porque es la
única decisión que hay que tomar **antes de ver datos** y gobierna todo lo que
sigue. Al acortar `_INSTRUCTIONS` de 35.941 a 1.991 caracteres en ORDEN 1.1,
quedó así:

    ANTES   PREGUNTA INICIAL OBLIGATORIA
            Al iniciar cualquier análisis, SIEMPRE pregunta primero al usuario:
            "¿Cómo deseas proceder? 1) GUIADO … 2) AUTÓNOMO …"

    DESPUÉS PREGUNTA PRIMERO, antes de tocar datos:
              1) GUIADO    paso a paso, con confirmación en cada nodo.
              2) AUTÓNOMO  pipeline completo.

Se perdieron **«OBLIGATORIA»**, **«SIEMPRE»** y la pregunta literal. «Pregunta
primero» se lee como una recomendación, y una recomendación dentro de un texto
de 2.000 caracteres compite con todo lo demás.

**Y funcionó como cabía esperar: el asistente no preguntó.** Lo detectó el
analista al arrancar la corrida de evaluación, antes de la primera llamada.

## Por qué ninguna prueba lo cazó — y esto es lo importante

`tests/test_carril_guiado_pregunta.py` y
`tests/test_bug_0046_objetivo_en_el_lote.py` guardaban exactamente esto. Los dos
**siguieron en verde**.

La causa está en el propio arreglo de la fase 1. Al mover la doctrina de
`_INSTRUCTIONS` a `_PROTOCOLO`, esas pruebas se repuntaron al sitio nuevo. El
repunte convirtió, sin que nadie lo dijera,

    «esto tiene que EMPUJARSE al modelo»   en   «esto tiene que EXISTIR»

Para casi toda la doctrina da igual: se pide cuando hace falta, que es el
propósito entero de la fase. **Para una clase de reglas no da igual: las que
gobiernan el momento ANTERIOR a que el modelo pueda pedir nada.** La pregunta
inicial es el caso puro — ocurre antes del primer `art://` posible. Si sólo está
en el recurso, no está.

La prueba pasaba porque el texto viejo sigue **entero** en `_PROTOCOLO`, que es
justo lo que la fase 1 quería. El defecto no es que la doctrina se perdiera: es
que se movió a un canal que no sirve **para esta regla en concreto**, y la
prueba dejó de distinguir los dos canales.

## La segunda, encontrada cinco minutos después: el IDIOMA

Mismo mecanismo, y bastaron tres palabras:

    ANTES    Responde SIEMPRE en el idioma del usuario (inglés por defecto SI ES AMBIGUO)
    DESPUÉS  Responde SIEMPRE en el idioma del usuario (inglés por defecto)

Son dos reglas distintas. La primera dice «el idioma lo pone el usuario; sólo si
no se sabe, inglés». La segunda se lee como **«por defecto, inglés»**. Y así se
comportó: el asistente contestaba en inglés a un analista que escribía en
español.

Es de la misma clase que la pregunta inicial —se decide en la primera frase,
antes de que quepa pedir nada— y por eso entra en el mismo contrato.

Restaurada como `IDIOMA: responde SIEMPRE en el idioma DEL USUARIO; inglés sólo
si es ambiguo`, con el «tradúcelas» de las salidas.

## Fix

Dos cosas, y la segunda es la que impide la reincidencia.

**1 · Restaurar la obligación en la cabecera.**

    PREGUNTA INICIAL OBLIGATORIA. SIEMPRE, antes de tocar datos, aunque creas
    saber la respuesta: «¿Cómo deseas proceder? 1) GUIADO, paso a paso con
    confirmación en cada nodo · 2) AUTÓNOMO, pipeline completo».

El «aunque creas saber la respuesta» no es adorno: el caso que lo destapó es
exactamente ése — el modo estaba dicho en la conversación y el asistente lo dio
por sabido.

Cupo recortando en otro sitio; la cabecera queda en **1.996** caracteres.

**2 · Fijar QUÉ no puede salir de la cabecera**, que es lo que faltaba.
`tests/test_bug_0148_lo_que_va_en_la_cabecera.py` enumera las cinco cosas que
gobiernan el momento anterior a poder pedir:

    el idioma, y que el inglés es el caso ambiguo y no el defecto
    la pregunta inicial, y que es obligatoria
    el objetivo, en el carril autónomo
    las dos puertas
    el convenio de ficheros, con `get_out_report` para que sea accionable
    cómo pedir más — sin esto, la fase 1 sólo habría borrado doctrina

y cierra con las dos que impiden resolverlo por los extremos: que todo eso
**quepa en 2.000**, y que la cabecera **no vuelva a ser** el protocolo entero.

## Validation

`tests/test_bug_0148_lo_que_va_en_la_cabecera.py` — 8 pruebas. Usa `dice()` de
`tests/_texto.py`, que compara colapsando blancos: si no, el ajuste de línea
volvería a partir las frases y la prueba mediría maquetación.
