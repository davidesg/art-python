---
id: BUG-0137
title: Las dos figuras que se dibujaban dentro del servidor, retiradas — un heatmap y seis paneles que no cambiaban ninguna decisión, con 1 llamada entre las dos
status: fixed
severity: low
component: mcp-tools
found_in: 0.2.1
fixed_in: 0.2.2
reported: 2026-09-09
reporter: David
tags:
  - figuras
  - contexto
references:
  - BUG-0127
  - BUG-0128
  - BUG-0134
---

## Summary

`mcp_server.py` era el único módulo que dibujaba fuera de `describe.py` y sus
compañeros: **dos funciones con su `plt.subplots` dentro**, y son justamente las
dos menos usadas del sistema.

| | líneas | llamadas en 1.114 | tamaño de su figura |
|---|---|---|---|
| `overparameterization_analysis` | 212 | **1** | 624 × 526 px, 29 KB |
| `compare_versions` | 274 | **0** | **1515 × 1076 px, 106 KB** |

Las dos se retiran por el mismo criterio del analista:

> *«No es necesaria. La tabla hace su trabajo y avisa. Esto es sobre-elaborar.»*

## El heatmap de correlaciones

Un mapa de calor de la matriz de correlación de parámetros, con recuadro en el
bloque ARMA+μ y borde dorado en los pares marcados.

Argumenté conservarlo —un heatmap enseña que la colinealidad forma un bloque
compacto, cosa que una lista de pares no muestra—. El analista lo desestima, y
tiene razón: **la tabla ya da los pares, su `r` y su diagnóstico** («FLT (ω,δ):
estructural, sin acción»), que es lo que se hace con ellos. Yo argumentaba desde
*qué se puede ver* y no desde *qué hace falta para decidir*.

## Los seis paneles de la comparación

Residuos, ACF y PACF de cada modelo, lado a lado. No servía en ninguno de los
dos casos posibles:

* **cuando los modelos se parecen**, los seis paneles son indistinguibles —
  comparando `m41` y `m31` de RATIO, que difieren en σ_a en **0,0012**, las dos
  columnas se superponen;
* **cuando difieren**, dos paneles con la misma escala obligan a ir y venir con
  la vista.

Y lo que decide una comparación de versiones está entero en la tabla que la
misma salida ya imprime:

```
loglik  -234.714  -234.692  +0.021
AIC      483.43    485.38   +1.96
BIC      500.36    504.74   +4.38
npar          7         8       +1
Modelos no anidados — test LR no aplicable.
```

Cuatro números y una advertencia.

## Fix

Las dos devuelven `b64 = None`. Se conservan enteras las tablas, los
diagnósticos por par, el bloque de cambios (`+step(Q2/2020), −impulse(Q2/2020)`)
y el aviso de anidamiento.

Con esto **`mcp_server.py` deja de dibujar**: las 15 figuras del sistema quedan
todas en los módulos de la biblioteca, que es el paso 2.6 de la revisión de
arquitectura, hecho por la vía de eliminar en vez de mover.

## Lo que queda anotado y NO se arregla aquí

Las **etiquetas de parámetro no distinguen dos parámetros distintos**: sobre
`RATIO_m31`, `ω(S)` aparece **dos veces** —una por intervención, la de 2020 y la
de 2008— con el mismo nombre. Afecta a la TABLA, que se conserva, así que sigue
vivo: deberían llevar la fecha, `ω(S,Q2/2020)`.

Y en la ecuación de cabecera de `compare_versions`, los dos modelos salen con la
misma línea —`I_t(2 itvs)` en ambos— porque no dice cuáles. La línea de cambios
sí lo dice, así que el defecto es sólo de la ecuación.
