---
id: BUG-0130
title: El umbral viaja como número pelado y pierde su criterio — la misma cabecera decía 2.5 o 3.5 sobre la misma serie sin decir por qué; y sin extremos se devolvía una figura vacía
status: fixed
severity: medium
component: describe
found_in: 0.2.1
fixed_in: 0.2.2
reported: 2026-09-09
reporter: David
tags:
  - figuras
  - umbrales
  - politica
references:
  - BUG-0105
  - BUG-0028
  - BUG-0127
---

## Summary

Dos cosas, encontradas al lanzar la figura del escaneo previo en el censo.

**1. El umbral cambia entre llamadas por POLÍTICA, y la salida no lo dice.**
`policy.THRESHOLDS` declara tres criterios con nombre:

| clave | valor | para qué |
|---|---|---|
| `outlier_user` | 3.5 | lo que pide el analista |
| `outlier_autonomous` | 3.0 | el carril autónomo |
| `outlier_autoscan` | 2.5 | el escaneo latente, más sensible **a propósito** |

Está bien pensado. Pero la cabecera imprimía sólo `- Umbral: |z| > 2.5`, así que
el analista veía `2.5` en una llamada y `3.5` en la siguiente, **sobre la misma
serie**, y no tenía forma de saber si eso era política o descuido. Y no es
cosmético: cambia **qué observaciones se marcan**, que es la decisión del nodo.

**2. Sin observaciones extremas se devolvía una figura de un solo panel.** La
serie tipificada sola, dibujada a un umbral que los datos ni se acercan a tocar:
las dos líneas de referencia eran decorado y el mensaje entero era «no hay
nada», que el texto dice en una línea. Y la serie con sus bandas ya está en el
listado de identificación.

Peor: **cambiaba la FORMA de la figura sin avisar**. Con extremos, tres paneles
—serie, ACF y PACF con la contribución del anómalo en rojo, 1406×921 px—; sin
extremos, uno —1405×360—. Quien esperaba tres veía uno y no sabía si es que no
había nada o si la figura había fallado.

**Éste es el «a veces viene en un formato y a veces en otro» que motivó el censo
de figuras**, y tiene una causa concreta: un `if outliers:` en `describe.py`
decidía la forma del lienzo, no sólo su contenido.

## Impact

**Medio.** El primero afecta a la decisión —el analista compara marcados entre
llamadas—; el segundo, a la confianza en la herramienta, que es lo que hace que
se deje de mirar una figura.

## Root cause

**El criterio se pierde en la frontera.** El umbral viaja como un `float`
pelado, así que cuando llega a quien imprime la cabecera ya no queda nada que
diga de dónde salió. Y no se puede reconstruir: **los valores de
`policy.THRESHOLDS` no son únicos** — `intervention_form` vale también 2.5, y
`intervention_autoselect`, `mu_drift` e `intervention_vecino` valen 2.0. Un
número no identifica un criterio.

Es la misma enfermedad que el censo encuentra en todas partes, en otra forma:
información que existe en el origen y no sobrevive al paso por la frontera.

## Fix

`_criterio_umbral(umbral, n)` compone la cabecera y dice, cuando puede:

```
- Umbral: |z| > 2.5  (escaneo latente, más sensible a propósito)  ·  calibrado para n=83: 3.22 (BUG-0105)
```

Con dos honestidades:

* **sólo nombra la familia `outlier_*`**, que es la única unívoca; si el número
  es ambiguo o lo pidió el analista, dice «(pedido)» y no inventa;
* **publica al lado el umbral calibrado por `n`**. El BUG-0105 estableció que un
  umbral fijo deja de significar lo mismo según `n` —con n=500 y umbral 3, tres
  de cada cuatro modelos correctos tendrían «un residuo extremo»— e introdujo
  `umbral_extremo(n)`. **Ninguno de los tres fijos lo usa hoy.** Decirlo al lado
  deja la diferencia a la vista sin cambiar ningún veredicto.

Y sin extremos, **sin figura**: `figure_b64 = None`. La de tres paneles se queda
tal cual — es correcta y de las buenas del sistema.

## Validation

```
figura=NO   |z| > 3.5  (criterio del analista)              · calibrado n=83: 3.22
figura=NO   |z| > 3.0  (criterio del carril autónomo)       · calibrado n=83: 3.22
figura=NO   |z| > 2.5  (escaneo latente, más sensible…)     · calibrado n=83: 3.22
figura=sí   |z| > 2.0  (pedido)                             · calibrado n=83: 3.22
```

## Lo que queda decidido y NO se toca aquí

**Si los tres umbrales fijos deben pasar a `umbral_extremo(n)`** es una decisión
del analista, no un arreglo: cambiaría qué se marca en todos los análisis. Queda
a la vista en cada cabecera —3,5 fijo frente a 3,22 calibrado para n=83— para
que se pueda decidir con el dato delante.
