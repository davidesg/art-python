---
id: BUG-0131
title: El panel de contribución de la PACF omitía las observaciones ANTERIORES a los anómalos — un off-by-one que hacía parecer que los anómalos no tocaban la PACF
status: fixed
severity: high
component: describe
found_in: 0.2.1
fixed_in: 0.2.2
reported: 2026-09-09
reporter: David
tags:
  - identificacion
  - figuras
  - off-by-one
references:
  - BUG-0028
  - BUG-0130
---

## Summary

El tercer panel del escaneo —«PACF, decide el orden AR · rojo = parte debida al
outlier»— dibujaba la contribución calculada como *observada menos calibrada*,
omitiendo los anómalos. Pero omitía **los índices equivocados**:

```python
outliers = [(int(i), float(w_std[i]), _idx_to_date(i)) for i in extreme_idx]
                 ^^^^^^ ya es 0-based
...
om = {int(i) - 1 for i, _z, _d in outliers}      # ← y aquí se le resta uno
```

Sobre `RATIO_m10`, con anómalos en las observaciones 18 y 64 (0-based), omitía
las **17 y 63**: dos observaciones perfectamente normales. La «contribución del
anómalo» que dibujaba era el efecto de quitar dos datos cualesquiera.

| retardo | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| **dibujado** (omitiendo 17 y 63) | +0,006 | +0,006 | +0,004 | +0,008 | +0,006 | **+0,016** |
| **correcto** (omitiendo 18 y 64) | −0,049 | −0,110 | −0,104 | −0,127 | +0,047 | **−0,108** |

Dos órdenes de magnitud y el signo cambiado.

## Impact

**Alto, y en el nodo que decide el orden AR.**

La figura decía, visualmente, que **los anómalos no tocan la PACF**: las barras
rojas eran hilos junto al cero mientras las de la ACF eran bloques. Un analista
que mire ese panel concluye que puede identificar el orden AR sobre el
correlograma observado sin intervenir — que es exactamente la conclusión
contraria a la correcta. Sobre `RATIO_m10`, la PACF del retardo 6 pasa de −0,242
a −0,135 al quitar los anómalos: **sale de banda**, y el veredicto de la
calibración es que la señal AR la **fabricaba** el anómalo.

Y el instrumento se contradecía a sí mismo en la misma pantalla: la **tabla** de
calibración daba −0,2424 → −0,1348 y el **panel** decía +0,016.

**Lo encontró el analista comparando las dos figuras a ojo**, en el censo:
*«parece que la segunda calibra mejor la pacf o hay un bug en la primera en las
calibraciones de la pacf»*.

## Reproduction

```python
from art.calibracion import _acf_pacf
_, pf = _acf_pacf(w, 12)
_, pc_mal   = _acf_pacf(w, 12, omitir={17, 63})   # lo que hacía el código
_, pc_bien  = _acf_pacf(w, 12, omitir={18, 64})   # los anómalos de verdad
```

Sobre `bugs/BUG-0126-repro/caso/RATIO_m10.inp` con umbral 3, `pf - pc_mal`
reproduce dígito a dígito lo que la figura dibujaba.

## Root cause

Un `-1` de más, escrito para convertir de 1-based a 0-based sobre una lista que
ya era 0-based. Sobrevivió porque **el panel no se comparaba con nada**: la tabla
de calibración vive en otra función (`calibracion.py`) y calcula lo mismo bien,
pero las dos salidas no se cruzaban en ninguna prueba.

Es la enfermedad de siempre en su forma numérica: **el mismo cálculo hecho dos
veces, en dos módulos, y sólo uno correcto** — y nada que los obligue a coincidir.

## Fix

`om = {int(i) for i, _z, _d in outliers}`.

## Validation

Interceptando lo que `Axes.bar` dibuja de verdad —no leyendo el fuente— la
contribución de la PACF pasa a ser `[-0.049, -0.110, -0.104, -0.127, +0.047,
-0.108, …]`, que coincide con la tabla de calibración en el retardo 6:
−0,2424 → −0,1348, diferencia **−0,1076**.

**La prueba que hay que añadir, y que es la lección**: que el panel y la tabla
den el mismo número. Un contraste entre las dos implementaciones del mismo
cálculo, que es lo que no existía.
