---
id: BUG-0157
title: El aviso «la explicación no concuerda con el contraste» se da sobre un episodio que EXCLUYE la vuelta, así que «permanente» sale por construcción
status: open
severity: high
component: interventions
found_in: 0.2.0
fixed_in:
reported: 2026-09-11
reporter: David — corrida guiada de ITCER
tags:
  - intervenciones
  - episodios
references:
  - BUG-0155
  - BUG-0136
---

## Summary

Cuando el analista declara `evento_naturaleza="transitorio"` y el contraste de
ganancia da ω(1) ≠ 0, la herramienta avisa de que **la explicación
extramuestral no concuerda con el contraste** — y trata eso como razón para
subir de peldaño.

En ITCER el aviso se dio sobre un episodio acotado a **un período**, que excluye
el rebote de 2009Q2–Q4. Con la vuelta fuera del modelo, **«permanente» sale por
construcción**: no hay nada en la especificación que pueda devolver el nivel.

El aviso desautoriza la información del analista con un contraste que **no puede
ver el suceso que el analista está describiendo**.

## Root cause

Tres piezas que encajan mal:

1. `decide_episodios` agrupa extremos contiguos. La caída de 2008 y el rebote de
   2009 están separados por trimestres tranquilos, así que son episodios
   distintos.
2. `incident_configurations` extiende el arranque **hacia atrás** por el
   mecanismo —un impulso de nivel en T da +ω en T y −ω en T+1— y no tiene forma
   de extender hacia **delante** para alcanzar una vuelta diferida.
3. El contraste ω(1)=0 se calcula sobre la intervención construida, que por (1)
   y (2) sólo cubre la caída.

Y la escalera tampoco ofrece la forma: `1b` —impulso de nivel— fuerza la vuelta
en T+1, y el dato la tiene cuatro trimestres después. **No hay forma en el
catálogo para un transitorio de vuelta diferida.**

## Impact

Alto, y de método. El nodo de intervención existe para incorporar lo que el
analista sabe y los datos no dicen; éste es el único sitio de `art` donde eso
entra. Un aviso que declara «no concuerda» cuando la discrepancia la produce la
propia delimitación **enseña al analista a desconfiar de su información**, que
es lo contrario de lo que el nodo pretende.

Además sugiere `incident_configurations` «para revisar la delimitación», y ese
instrumento no puede delimitar un episodio cuya otra mitad está después.

## Fix propuesto

Por orden de coste:

1. **Que el aviso diga su propia precondición.** Si el episodio no alcanza a la
   vuelta que el analista describe, el contraste no puede verla, y el aviso
   tiene que decir eso en vez de afirmar una discrepancia. Es texto, y quita el
   daño principal.
2. **Extender la delimitación hacia delante** cuando el analista declara
   transitorio: buscar una vuelta dentro de una ventana, y ofrecer la forma de
   dos tramos.
3. **El contraste de la ganancia NETA** de un episodio repartido en dos
   intervenciones. Hoy `test_interventions` contrasta cada ganancia por separado
   y rotula la de 2008 «PERMANENTE» sin mirar el rebote. Calculado a mano por el
   analista: −13,8 con t=−3,1, que es una recuperación parcial y no un
   permanente.

## Validation

Un episodio con vuelta diferida: el aviso no puede afirmar discrepancia si la
especificación contrastada no incluye la vuelta; y `test_interventions` debe
poder dar la ganancia neta de dos intervenciones del mismo suceso.
