---
id: BUG-0135
title: La superposición sombreaba sólo el arranque del incidente, su panel de restos no iba tipificado, y las etiquetas mezclaban idiomas
status: fixed
severity: medium
component: ltf
found_in: 0.2.1
fixed_in: 0.2.2
reported: 2026-09-09
reporter: David
tags:
  - figuras
  - intervenciones
references:
  - BUG-0133
  - BUG-0134
---

## Summary

Tres cosas del gráfico de superposición, encontradas en el censo de figuras al
compararlo con la escalera de Ockham.

**1. El sombreado marcaba sólo el arranque.** Era una `axvline` en `sp.at`, así
que con una hipótesis de **dos ω** —la que RATIO tiene estimada— sombreaba **un
solo período** donde la forma abarca dos. Con cinco ω el analista veía marcado un
suceso de uno donde la respuesta dura cinco.

**2. El panel de restos no iba tipificado.** Iba en unidades de la serie, con
líneas a `±3·sd` calculadas a mano. Todas las demás figuras del nodo enseñan
residuos **tipificados con banda de ±2σ** — el escaneo, la escalera, la
canónica— y ésta era la excepción. Y es la que el analista mira para juzgar si
la forma encaja: sin tipificar no se puede decir «ese resto es grande» sin
calcular.

**3. Las etiquetas mezclaban idiomas.** `observado`, `hipótesis`, `nivel`,
`resto`, `observación` conviviendo con `ACF`/`PACF`, que son siglas inglesas y
se usan sin traducir en todo el sistema. Criterio del analista: **las etiquetas
y los nombres de las figuras van en inglés**; la narrativa sigue en el idioma
del usuario.

## Fix

* **El soporte se calcula, no se supone**: `Superposicion.soporte` sale de
  `fin_sop` —la última posición no nula de la respuesta—, así que vale igual
  para dos ω que para cinco, y para formas con denominador. Medido: 2 y 5.
  El sombreado es un `axvspan` de `at−0.5` a `at+soporte−0.5`.
* **El panel de restos, tipificado**, con `±2σ` y `residual (z)` en el eje, y
  con límite mínimo de ±2,4 para que la banda se vea siempre.
* **Etiquetas en inglés**: `observed`, `hypothesis × …`, `level`/`∇`,
  `residual (z)`, `observation`, `Overlay around obs …`.

## Lo que este defecto deja dicho

**Es el papel de esta figura lo que lo hace importante.** Decisión del analista
en el censo:

> *«La superposición lleva la sugerencia y la escalera es el argumento si es
> necesario. El analista pregunta qué forma es la que mejor se adapta a los
> datos; la herramienta le dice una forma. El analista replica con otra forma y
> la herramienta presenta la escalera como argumento. En modo automático la
> escalera es fundamental como información; en modo guiado es más argumental.»*

La superposición **no estima**: acepta la forma que el analista proponga y dice
si encaja, separando **amplitud** de **forma** con dos números. La escalera sólo
compara su propio menú de tres peldaños, y cuesta tres estimaciones. Para la
réplica del analista —«¿y si es otra forma?»— la superposición contesta y la
escalera no.

De ahí la consecuencia de cableado, que se anota aparte: en carril guiado la
escalera debería dispararse **cuando se argumenta**, no siempre.

## Validation

`soporte` = 2 con dos ω y 5 con cinco, calculado desde la respuesta.
