---
id: BUG-0132
title: El gráfico de calibración de distorsiones no era comparable con la figura canónica de residuos — otros retardos, sin marcas estacionales y sin la Q, que es la pregunta que existe para contestar
status: fixed
severity: medium
component: describe
found_in: 0.2.1
fixed_in: 0.2.2
reported: 2026-09-09
reporter: David
tags:
  - figuras
  - identificacion
  - doctrina
references:
  - BUG-0130
  - BUG-0131
---

## Summary

**Precisión de nomenclatura, del analista, y no es menor.** La figura CANÓNICA
es la de **residuos + ACF/PACF** (`plot_diagnosis`): la compacta que acompaña a
cada modelo estimado, y que ya estaba aprobada. Ésta, la de tres paneles, es
**el gráfico para calibrar distorsiones** — otra cosa, que la acompaña y no la
sustituye.

Decisión de diseño del analista, tomada en el censo de figuras: el gráfico de
calibración de distorsiones es **uno solo** para las dos preguntas del nodo, y
sustituye a la figura de calibración del correlograma como gráfico —la calibración se queda como tabla,
que es donde sirve—. Una sola figura para las dos preguntas, porque al final son
la misma:

> *«Te ayuda a decidir si intervenir antes de ARMA, o ARMA antes de intervenir. Y
> después te ayuda a explicar si las ACF/PACF sucias y con Q demasiado grande es
> por un anómalo o porque falta estructura.»*

Para poder leerse AL LADO de la canónica le faltaban tres cosas, y las tres se arreglan aquí.

**1. Llevaba otros retardos que la figura de diagnosis.** El canónico usa
`_default_lags_fug(n, freq)` = **3s+3** con estacionalidad y 9 sin ella: 15 en
trimestral, **39 en mensual**. El escaneo usaba `min(n//3, max(12, 2s))`, que da
**12** en trimestral y se queda en 24 en mensual. Las dos figuras se leen una al
lado de otra —los residuos y su calibración— y comparar exigía contar barras.

**2. No llevaba las marcas estacionales.** El canónico dibuja líneas verticales y
ticks en `s, 2s, 3s` (o 3/6/9 sin estacionalidad). Sin ellas, en mensual con 39
retardos, encontrar el 12 y el 24 es contar de uno en uno.

**3. No decía la Q, ni observada ni calibrada** — y ésa es literalmente la
pregunta que la figura existe para contestar.

## Impact

**Medio, y en el nodo de más tráfico.** El escaneo sale latente en cada
estimación. Sin la Q calibrada, la pregunta «¿anómalo o falta estructura?» se
contestaba a ojo mirando barras rojas; con ella se contesta con un número.

## Fix

1. `n_lags = min(_default_lags_fug(len(w_std), freq), n-2)` — los del canónico.
2. `_rejilla_estacional(ax, freq, n_lags)`, copiada de
   `fue.plots._draw_acf_panel`, en los dos paneles.
3. **La Q, observada y calibrada**, con su veredicto:

```
- Q(15) = **20.8** observada  ·  **11.1** quitando los anómalos  (+47%)
  → **mixto**: los anómalos explican parte de la Q y queda estructura debajo.
```

Tres bandas, y ninguna se queda callada:

| caída de la Q | qué dice |
|---|---|
| ≥ 50 % | la Q la ponían los anómalos: intervenir antes de tocar el ARMA |
| 20–50 % | mixto: intervén y vuelve a mirar |
| < 20 % | la Q **no** es de los anómalos: falta estructura, y una intervención no la va a arreglar |

## Validation

Sobre `RATIO_m10` —el modelo con armónicos y SAR(1), antes de intervenir— la Q
pasa de **20,8 a 11,1** al quitar los dos anómalos: **mixto**. Y es el
diagnóstico correcto, comprobado contra el análisis real: a ese modelo hubo que
añadirle el SAR(1) **y** las dos intervenciones.

El `Q(15) = 20.8` coincide además con el que imprime la figura canónica de
diagnosis para el mismo modelo — que es la comprobación de que los retardos ya
son los mismos.

## Lo que esto retira

La figura de **calibración del correlograma** deja de hacer falta como gráfico:
su información —observada contra calibrada, y si el retardo cruza la banda— está
ahora en el panel de contribución, que desde el BUG-0131 es correcto. Su tabla se
conserva íntegra: es donde el veredicto por retardo se lee mejor.
