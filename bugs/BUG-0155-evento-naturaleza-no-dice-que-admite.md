---
id: BUG-0155
title: `evento_naturaleza` sólo admite permanente|transitorio y no lo dice — se aprende por el error, y le falta «recuperación parcial»
status: open
severity: medium
component: mcp-tools
found_in: 0.2.0
fixed_in:
reported: 2026-09-11
reporter: David — corrida guiada de ITCER
tags:
  - intervenciones
  - esquema
references:
  - BUG-0116
---

## Summary

Dos cosas, y la segunda es la de fondo.

**1 · No dice qué admite.** `guided_intervention(..., evento_naturaleza=…)`
acepta `"permanente"`, `"transitorio"` o vacío. La descripción de la
herramienta no lo enumera, así que el valor válido se aprende **por el mensaje
de error**. Es un parámetro de ENUM sin su enumeración: la descripción de
`incident_configurations` sí lo dice (`mcp_server.py:2090`), la de la puerta no.

**2 · El enum no cubre lo que el analista tiene que decir.** En ITCER el suceso
de 2008-09 es una caída seguida de una recuperación PARCIAL: el nivel no vuelve
—no es transitorio— y tampoco se queda donde cayó —no es el permanente que el
contraste rotula—. El analista describió «recuperación parcial» y no hay forma
de declararlo.

Consecuencia concreta: el aviso «la explicación extramuestral no concuerda con
el contraste» se dispara comparando lo que el analista dice con un contraste
que sólo tiene dos casillas, y el analista no tenía la suya.

## Impact

`evento_naturaleza` existe para que el registro extramuestral entre en la
decisión — es el único nodo de `art` cuya evidencia no está en los datos. Un
enum que no cubre el caso convierte esa entrada en una elección entre dos
respuestas equivocadas.

## Fix propuesto

1. Enumerar los valores en el esquema (`Field(description=…)`), que es donde no
   se recorta, y no sólo en la prosa de otra herramienta.
2. Decidir si `recuperación parcial` es un tercer valor o si es «permanente de
   menor magnitud» — que **es** lo que el contraste ve— y decirlo así en la
   lectura: «permanente, con recuperación parcial: la ganancia neta es X».
   La segunda no toca el enum y arregla la lectura, que es lo que falla.

Ver también la pareja de este defecto: el contraste de la ganancia NETA de un
episodio repartido en dos intervenciones, que hoy no existe.

## Validation

Llamar con un valor inválido debe decir cuáles son los válidos; y la
descripción publicada debe enumerarlos sin que haga falta el error.
