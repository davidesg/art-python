---
id: BUG-0134
title: La figura de episodios no añadía nada al gráfico de calibración más que una franja, y su eje iba sin fechas
status: fixed
severity: low
component: episodes
found_in: 0.2.1
fixed_in: 0.2.2
reported: 2026-09-09
reporter: David
tags:
  - figuras
  - intervenciones
references:
  - BUG-0133
  - BUG-0127
---

## Summary

`describe_episodios` devolvía un panel con los residuos tipificados y los
episodios sombreados en naranja, etiquetados `E1`, `E2`.

Veredicto del analista en el censo de figuras: *«no añade nada al residuos +
ACF/PACF canónico más que una franja»*. Y es literal — el gráfico de calibración
de distorsiones dibuja **los mismos residuos**, marca **el mismo tramo** desde el
BUG-0133, y además lleva:

| | episodios | gráfico de calibración |
|---|---|---|
| residuos tipificados | ✓ | ✓ |
| tramo del suceso sombreado | ✓ | ✓ (BUG-0133) |
| **fechas** | ✗ — «observación 19» | ✓ — «Q4/2008» |
| ACF con la contribución del anómalo | ✗ | ✓ |
| PACF con la contribución | ✗ | ✓ |
| Q observada y efecto de omitir | ✗ | ✓ |

## Defecto propio

Su eje iba en **«espacio de RESIDUOS»**, sin fechas: decía `observación 19` y
`observación 65` donde el resto del nodo dice `Q4/2008` y `Q2/2020`. Era la única
figura del nodo que obligaba al analista a traducir contando.

## Fix

Se retira la figura. **La tabla se conserva entera**, y es el valor de la
herramienta: el tramo, la duración **en el nivel** (que no es la de los
residuos), la cohesión y —sobre todo— **la forma general que le corresponde a
cada episodio**:

> Un episodio de duración **L** se especifica como **L+1 escalones en el nivel**
> desde su inicio. Con ganancia ω(1)=0 equivalen a L impulsos —efecto
> transitorio—; con ganancia distinta de cero, a un cambio de nivel permanente.
> Cuál de las dos cosas lo dice el contraste, no la forma del grupo.

Eso es doctrina que no está en ninguna otra salida y no necesita dibujo.

## Validation

`residual_episodes` devuelve **0 imágenes**, y el texto conserva la tabla
(`dur. nivel`, `forma general`) y la regla de los `L+1 escalones`.

Cuarta baja del censo de figuras —tras 0127, 0128 y la fusión del 0133— y por la
misma regla:

> Una figura se justifica cuando enseña algo que **no cabe en una tabla**, y que
> no esté ya en otra figura del mismo nodo.
