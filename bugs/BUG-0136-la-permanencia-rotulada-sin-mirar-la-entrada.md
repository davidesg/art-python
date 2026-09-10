---
id: BUG-0136
title: El bloque del operador rotulaba «PERMANENTE» sin mirar la entrada — con impulso el efecto permanente es cero por construcción, y el mismo programa lo decía tres líneas más abajo
status: fixed
severity: high
component: ltf
found_in: 0.2.1
fixed_in: 0.2.2
reported: 2026-09-09
reporter: David
tags:
  - intervenciones
  - doctrina
references:
  - BUG-0071
  - BUG-0072
  - BUG-0076
  - BUG-0086
---

## Summary

El bloque «el operador, y lo que hace en el NIVEL» —el que se imprime en
**todas** las salidas del nodo de intervención— cerraba con:

```
  ganancia ν(1) = ω(1)/δ(1)      : -1.2063   → el nivel se queda desplazado (PERMANENTE)
```

y lo decidía por el mero hecho de que `ν(1) ≠ 0`, **sin mirar qué entrada
tiene la intervención**.

**Con entrada de IMPULSO el efecto permanente es CERO POR CONSTRUCCIÓN**: la
entrada no persiste, así que el nivel vuelve sea cual sea ω. `ν(1)` es entonces
el **área acumulada** de la respuesta, no un desplazamiento.

Y el programa ya lo sabía: `interventions.py` tiene la propiedad
`efecto_permanente` desde el BUG-0076, con este comentario:

> *«Con input escalón es la ganancia. Con impulso es **cero exacto**, y no por
> estimación sino por construcción de la entrada: no persiste.»*

De modo que la misma pantalla decía las dos cosas:

```
  ganancia ν(1) = -1.2063   → el nivel se queda desplazado (PERMANENTE)
  ...
  efecto permanente en el nivel: 0 por construcción (la entrada no persiste)
```

## Impact

**Alto en el nodo de intervención, y es doctrina.** Separar permanente de
transitorio es la decisión que el contraste de ganancia existe para tomar
(BUG-0071/0072), y el rótulo la contradecía **en el sitio de más lectura**: el
bloque del operador aparece en `intervention_plot`, en `test_interventions` y
dentro de cada llamada 3 de `guided_intervention`.

Observado tres veces en un solo análisis —la réplica del TFM de Bolivia,
`run5_guiado`, 8-sep— sin llegar a levantarse:

* en `m20`, con el escalón ×3 de Q2/2020: Wald p=0,874 —no rechaza ganancia
  nula, o sea transitorio— y el bloque rotulando PERMANENTE;
* en `m30`, con el escalón ×5 de Q4/2008: ahí acertaba, pero por casualidad;
* en `m41`, con el impulso restringido: `ν(1) = +27,65` y «PERMANENTE», cuando
  el impulso es transitorio **por definición de la entrada**.

## Root cause

`operador_en_palabras` no recibía `entrada`. El dato existe en el llamador —la
herramienta lo tiene como parámetro, y una intervención ajustada lleva su
`type`— y se perdía al cruzar la frontera de la función.

Es el mismo mecanismo que el censo de figuras ha encontrado seis veces hoy: **el
criterio no viaja**. Aquí el que se perdía era el que decide qué SIGNIFICA el
número que se imprime.

## Fix

`operador_en_palabras(..., entrada=...)` y `describe_ltf(..., entrada=...)`, con
los tres llamadores propagándolo: la herramienta pasa el suyo, y las dos vías
que parten de un modelo ajustado lo derivan del `type` de la intervención
(`pulse`/`impulse`/`compimp` ⇒ impulso).

Con impulso, el bloque dice:

```
  ganancia ν(1) = ω(1)/δ(1)      : +27.6529   → área acumulada; el efecto
  permanente es 0 POR CONSTRUCCIÓN (la entrada no persiste)
```

y la lectura de `describe_ltf`:

> **TRANSITORIO POR CONSTRUCCIÓN** — la entrada es un impulso y no persiste, así
> que el nivel vuelve sea cual sea ω. El **+12,8395** es el ÁREA acumulada de la
> respuesta, no un desplazamiento del nivel.

## Validation

```
intervention_plot  impulso  : → área acumulada; el efecto permanente es 0 POR CONSTRUCCIÓN
intervention_plot  escalon  : → el nivel se queda desplazado (PERMANENTE)
test_interventions (m41)    : → área acumulada; el efecto permanente es 0 POR CONSTRUCCIÓN
```

`m41` es el modelo final de RATIO con el impulso restringido: el caso donde el
rótulo mentía en el análisis real.
