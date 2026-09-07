---
id: BUG-0110
title: decided_by registra el CARRIL y no quién decidió cada nodo — no se puede saber dónde el analista corrigió al asistente, que es la información que el guion existe para conservar
status: open
severity: medium
component: guion
found_in: 0.2.0.dev0
fixed_in:
reported: 2026-09-07
reporter: David — al medir dónde hace falta el ojo entrenado, para Econometría Aplicada
tags:
  - guion
  - registro
  - decided_by
  - contraste-de-carriles
references:
  - src/art/guion.py (GuionEntry.decided_by)
  - bugs/BUG-0110-repro/repro.py
  - "~/Dropbox/Econometria Aplicada GD/05-recursos/donde-hace-falta-el-analista/"
---

## Summary

`GuionEntry.decided_by` se documenta como *«lo que hace comparables dos guiones:
el protocolo es el mismo y los nodos son los mismos; lo único que cambia es quién
decidió cada uno»*.

**No cumple lo que promete.** Medido sobre el corpus:

    guiones con nodos declarados                                   81
      con UN SOLO decisor en todo el guion                         81
      con decisor MIXTO (el analista entra en unos nodos y no otros) 0

Es **constante dentro de cada guion**: 58 guiones enteros marcados `LLM` y 23
enteros `analista+LLM`. Registra el **carril** —guiado o autónomo— y no quién
decidió cada nodo.

Y eso es justo lo que no hace falta, porque el carril ya se sabe: está en el modo
con que se lanzó la sesión.

## Impact

En una sesión guiada el analista **no interviene en todos los nodos**: acepta la
propuesta en unos y la contradice en otros. Esa diferencia es la información con
valor —dónde el ojo entrenado corrige al asistente— y el registro la pierde.

Consecuencia concreta, medida al preparar material docente sobre esta cuestión:
hubo que **inferirla del texto de los razonamientos**, buscando marcas como «EN
CONTRA de la recomendación» o «corrección del analista». Eso encontró 20
entradas, y la propia nota tiene que advertir que la atribución es inferida y no
registrada.

El caso más valioso del corpus —la corrección del capado del AR(6), donde el
asistente propuso invertir la lógica de un contraste y el analista lo paró con
una demostración algebraica— sólo es identificable porque el analista **escribió**
que estaba corrigiendo. Si hubiera escrito su razón sin decir que contradecía,
sería indistinguible de un acuerdo.

## Reproduction

`bugs/BUG-0110-repro/repro.py` — determinista, sin motor. Construye un guion
guiado con tres nodos: en dos el analista contradice y en uno acepta. Los tres
salen `analista+LLM` y no hay ningún campo que los distinga.

    decisores distintos en el guion: {'analista+LLM'}
    campos que registren la propuesta o el acuerdo: NINGUNO

## Root cause

El campo tiene un solo valor por sesión porque se rellena desde el modo, no desde
el nodo. Nunca hubo un sitio donde anotar **qué propuso el asistente** frente a
**qué se decidió**, que es la comparación que da la información.

## Fix

Registrar, por nodo:

  - **lo que el asistente propuso** (`propuesta`), que hoy se pierde en cuanto el
    analista responde;
  - **si lo decidido coincide** con ello (`coincide: bool`), que es lo que
    convierte el guion en medible sin leer prosa.

Con esos dos campos, «¿dónde corrige el analista al asistente?» se contesta
filtrando, y la nota docente pasa de inferida a directa. El carril sigue siendo
recuperable —es constante— así que no se pierde nada.

Conviene además que el carril viva donde le corresponde, en la cabecera del
guion y no repetido en cada entrada.

## Validation

`repro.py` sale 0 cuando un guion guiado puede distinguir un nodo decidido
contra la propuesta de uno decidido de acuerdo con ella.

## Lo que NO arregla

Los 81 guiones ya escritos. Su atribución seguirá siendo inferible sólo del
texto, y las mediciones hechas sobre ellos —incluida la nota docente— siguen
siendo estimaciones con esa advertencia. El arreglo sirve para lo que se registre
a partir de ahora, que es precisamente el material de las sesiones de clase.
