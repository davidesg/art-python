---
id: BUG-0128
title: La figura de parámetros estacionales duplicaba la tabla y la dibujaba peor — paneles con escalas distintas y sin la amplitud, que es lo único con lectura física
status: fixed
severity: low
component: describe
found_in: 0.2.1
fixed_in: 0.2.2
reported: 2026-09-09
reporter: David
tags:
  - figuras
  - contexto
references:
  - BUG-0010
  - BUG-0127
---

## Summary

`describe_seasonal_params` devolvía dos paneles de barras —coeficientes `cos` y
`sin` con sus ±2 SE— junto a la tabla que ya los da con SE, t y amplitud. Tres
problemas, y el segundo es el que la hace peor que no tener nada:

**1. Era la tabla, dibujada.** Los mismos `cos_k`, `sin_k`, SE y t.

**2. Y la dibujaba mal.** Los dos paneles salían con **escalas distintas y sin
cero común**. Sobre `RATIO_m41`, con `cos₁ = +5,11` y `sin₁ = −9,22`, el panel
izquierdo iba de 0 a 8 y el derecho de −12 a 0: el `sin` aparecía como una barra
que ocupaba el panel entero y el `cos` como una pequeña. **Sugería una
dominancia de casi el doble donde los números dicen 5,11 contra 9,22.** Una
figura que hace más difícil leer lo que la tabla dice bien.

**3. Y lo único que justificaría un dibujo no estaba.** La **amplitud**
`A_k = √(cos² + sin²)` es lo que tiene lectura física —cuánto oscila esa
frecuencia— y lo que se compara entre armónicos. Sobre este modelo, A₁ = 10,54 y
A₂ = 7,48. Está en la tabla y en ningún panel.

Síntoma menor que delata el camino: el fichero salía como `art_art_<huella>.png`
—etiqueta `"art"` en vez del nombre de la herramienta—, cuando todas las demás
salen `art_boxcox_…`, `art_seasonality_…`.

## Impact

**Bajo en frecuencia, y ése es parte del diagnóstico.** `seasonal_param_analysis`
tiene **1 llamada en 1.114**, y el analista, al verla en el censo, no la
recordaba: *«este gráfico no debe estar cableado siquiera porque no la
recordaba»*. Una figura que induce a error y que nadie mira.

## Reproduction

`seasonal_param_analysis` sobre un modelo con armónicos en dos frecuencias donde
`cos` y `sin` tengan signos opuestos — `RATIO_m41` sirve.

## Root cause

Un panel por componente, cada uno con su `ax` y su autoescala. Nadie fijó un eje
común porque el dibujo se pensó como «una barra por coeficiente», no como «una
comparación entre coeficientes» — que es para lo que sirve mirarlos juntos.

## Fix

Se retira la figura. La herramienta conserva la tabla y, sobre todo, la
advertencia de su docstring —no podar armónicos por el t-ratio antes del MEG
(BUG-0010)—, que es doctrina cara y no necesita dibujo.

Si algún día se quiere una figura aquí, la que tiene sentido es **un solo panel
con la amplitud por frecuencia y sus bandas**, no dos con las componentes.

## Validation

`describe_seasonal_params(m).figure_b64 is None`; la tabla conserva `cos_k`,
`sin_k`, `A_k` y la recomendación sigue nombrando al MEG.

Segunda baja del censo de figuras, tras el BUG-0127, y por la misma regla:

> Una figura se justifica cuando enseña algo que **no cabe en una tabla**.
