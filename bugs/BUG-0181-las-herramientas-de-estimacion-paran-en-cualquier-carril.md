---
id: BUG-0181
title: `confirm_and_estimate` y `estimate_and_diagnose` llevan el carril «guiado» fijo — en AUTÓNOMO cada estimación termina en ⏸ y le ordena al LLM parar a esperar a un analista que no existe
status: fixed
severity: high
component: mcp-tools
found_in: 0.2.0
fixed_in: 0.2.1
reported: 2026-09-12
reporter: David — run 4 automático y run 5 de IPC_ES
tags:
  - autonomo
  - carriles
  - regresion
references:
  - BUG-0094
  - BUG-0179
  - BUG-0180
---

## Summary

El 06-sep, `ce89c8b` —*«En guiado decide el analista: la salida termina en una
pregunta»*— fijó `modo="guiado"` en `confirm_and_estimate` y en
`estimate_and_diagnose`. El comentario lo justificaba así:

> *«ESTA ES LA HERRAMIENTA DEL CARRIL GUIADO —el nombre lo dice: se llama cuando
> **el analista** ha confirmado la especificación—»*

Eso da por hecho que **quien confirma es siempre un humano**. En el carril
autónomo quien confirma es el LLM haciendo de analista, con estas mismas
herramientas —así lo hicieron las 31 series del estudio de 0.1.x (BUG-0180)—. Desde
el 06-sep, cada llamada suya terminaba en

    ⏸ **Tu decisión.** No sigo hasta que me digas.

y el protocolo le dice qué hacer con esa marca: *«TU TURNO TERMINA EN ESA MARCA.
[…] NO LLAMES A NINGUNA HERRAMIENTA MÁS hasta que el analista conteste.»*

## Es una regresión, y tiene fecha

    art-v0.1.12   ⏸ en el fuente: 0   confirm_and_estimate guiado: no
    art-v0.2.0    ⏸ en el fuente: 3   confirm_and_estimate guiado: sí
    HEAD          ⏸ en el fuente: 4   confirm_and_estimate guiado: sí

En 0.1.12 no había ni un ⏸. Los enunciados del estudio funcionaban porque ninguna
herramienta le mandaba parar al LLM.

BUG-0179 cerró el mismo agujero en `build_model` —allí lo abría el `domain`—; aquí
quedaba en las dos herramientas por las que pasa cualquier recorrido nodo a nodo.

## Reproduction

**run4/auto**, transcripción:

    build_model(...)           ← «· guiado (spec confirmada)»  ⏸
       🤖 «Se paró en ⏸ tras la etapa 1, y según tus instrucciones ahí acabo mi turno.»
    confirm_and_estimate(...)  ← «· guiado»  ⏸
       🤖 «Me paro otra vez…»
    build_model(...)           ← «· guiado (spec confirmada)»  ⏸
       🤖 «Me paro otra vez…»
    👤 «para aquí y registra. en modo automático no deberías preguntar»

**run5**, el analista eligió AUTÓNOMO y en la etapa 2:

    estimate_and_diagnose(...)  ← «· guiado»  ⏸
    estimate_and_diagnose(...)  ← «· guiado»  ⏸

Sintético, en la suite: las tres herramientas en los dos carriles.

## Impact

Sin esto el carril que BUG-0180 consolida no puede existir: el protocolo le diría
al LLM que decide él, y cada herramienta que lo parase. Un run desatendido se queda
esperando; uno atendido convierte cada estimación en una pregunta que el analista
no debería tener que contestar.

*Una puerta queda cerrada a su uso normal.* Entra, y el analista lo pide para
0.2.1: «el modo automático funcional debe ir en 0.2.1».

## Fix

**El carril lo declara quien llama.** `_Modo = Literal["guiado", "autonomo"]` —en
el esquema, como `_Naturaleza` (BUG-0155), para que no se pueda escribir mal— y un
parámetro `modo` en las tres herramientas que emiten el sobre:

- `confirm_and_estimate` y `estimate_and_diagnose`: `modo="guiado"` por defecto;
  con `"autonomo"` la salida toma la forma del registro —especificación,
  estimación, diagnosis, **reformulación**— y no para.
- `build_model`: separa dos preguntas que compartían variable. `guided` —hay spec
  declarada— sigue decidiendo la política del motor; que la salida PARE depende de
  si hay un humano esperando, o sea de `modo`.

**Por qué parámetro y no estado del servidor.** Guardar el carril como global de
sesión es el canal que BUG-0081 ya demostró equivocado, y además falla hacia el
lado peligroso: un «autónomo» que se quedase puesto dejaría de parar en un guiado
posterior y el LLM decidiría por el analista. Con parámetro y **por defecto
guiado**, olvidarse cuesta una pregunta, no una decisión usurpada. Y el protocolo
cubre el olvido en autónomo: *«si te llega un ⏸, repite la llamada con
modo="autonomo"; no preguntes al usuario»*.

Lo que arregló `ce89c8b` **no se toca**: en guiado decide el analista y la salida
sigue terminando en la pregunta.

## Validation

`tests/test_bugs_0180_0181_el_autonomo_es_el_analista.py`:

- las tres herramientas con `modo="autonomo"`: sin ⏸, «autónomo» en la cabecera;
- las tres con `modo="guiado"`: el ⏸ sigue ahí;
- sin declarar, `confirm_and_estimate` y `estimate_and_diagnose` paran — el
  defecto es el lado seguro;
- el carril viaja como enum en el esquema MCP;
- **guardián**: ninguna llamada a `envuelve_iteracion` fija «guiado» a mano, para
  que la próxima herramienta con sobre no repita el supuesto.

## Anotado aparte, no arreglado

`estimate_and_diagnose` añade *«Guardado: …»* y *«guion: …»* **detrás** del ⏸
—`_con_nota_figura` sólo recoloca la nota de la figura—. Viene de antes de este
arreglo; el LLM para igual, así que es presentación y no carril, y por la tabla de
la congelación no entra.
