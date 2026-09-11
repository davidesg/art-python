---
id: BUG-0172
title: La regla de Treadway lee los residuos DESPLAZADOS cuando hay raíces estacionales integradas — publica «2 de 4 pasan» donde pasan las cuatro
status: open
severity: high
component: interventions
found_in: 0.1.0
fixed_in:
reported: 2026-09-11
reporter: David — run 3 de SF_MEG, incidencia C-21
tags:
  - intervenciones
  - treadway
  - numero-incorrecto
references:
  - BUG-0030
  - BUG-0089
  - BUG-0140
---

## Summary

`check_intervention_fit` mapea la fecha de una intervención al índice de los
residuos con:

```python
desfase = int(model.d) + int(model.D) * freq
ini = int(itv.at) + 1 - desfase
```

**Cuenta `d` y `D`, y no cuenta `ifadf`.** Cada raíz estacional estocástica
consume observaciones: un factor de frecuencia interior `(1 − 2cos(ω)B + B²)`
consume **2**, el de Nyquist `(1 + B)` consume **1**.

Sobre `B_m11` del run 3, con **dos** frecuencias reformuladas (f=2 y f=3), son
**4 observaciones**, y Treadway lee los residuos **4 meses después** de las
fechas intervenidas.

## Impact — publica un VEREDICTO incorrecto

No es una etiqueta mal puesta: es la regla que decide si una intervención
funcionó. Publicado:

    2 de 4 pasan la regla de Treadway
    3/2022  +0.81  −0.29  **−2.91**  +0.09   ← NO absorbido
    9/2021  +1.09  +1.70                      ← NO absorbido

Los z reales, leídos del `.out` con su fecha:

    3–6/2022   −0.46  −0.70  −0.09  +0.74
    9–10/2021  −0.48  −0.15
    1–2/2021   +0.64  +1.10
    12/2021    +0.51

**Las cuatro pasan.** Y los publicados coinciden exactamente con `t+4`: el −2.91
es el residuo de **09/2022**, no el de 03/2022.

La consecuencia es la que el nodo entero existe para evitar: un vecino anómalo
falso es «evidencia de que la representación elegida es errónea», así que empuja
a cambiar la forma de una intervención que está bien puesta — o a añadir otra.

Es la familia de las fechas desplazadas en figuras (C-10, C-11c del run)
convertida en veredicto.

## Repro

Un modelo con `ifadf` activo en una o dos frecuencias y una intervención de
fecha conocida: los `fechas` que devuelve `check_intervention_fit` apuntan
`sum(consumo por ifadf)` observaciones más allá de la intervenida.

    consumo = Σ (2 si f interior, 1 si f == s/2)  sobre las f con ifadf[f] == 1

## Fix propuesto

Sumar al `desfase` el consumo de `ifadf`. La cuenta ya existe en el proyecto —el
convenio de `ornsop` de `fug` la hace para el eje de las figuras— así que es
llevarla a un solo sitio en vez de tenerla en dos.

Y conviene revisar los demás sitios que hacen `at → índice de residuo` con el
mismo `d + D·s`: si Treadway lo tenía mal, es probable que no sea el único.

## Validation

Con `ifadf` activo, los residuos que Treadway lee en una fecha intervenida tienen
que ser los de esa fecha — comprobado contra el `.out`, que los trae fechados. Y
sin `ifadf` nada cambia.
