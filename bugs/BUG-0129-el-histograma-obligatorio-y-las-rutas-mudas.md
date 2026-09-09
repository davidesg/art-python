---
id: BUG-0129
title: estimate_and_diagnose mandaba el histograma siempre y no decía ninguna ruta — tres sitios y tres respuestas sobre si el histograma es opcional
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
  - BUG-0113
  - BUG-0122
  - BUG-0126
---

## Summary

La misma pregunta —¿el histograma de residuos forma parte de la diagnosis?—
contestada de tres maneras distintas en tres sitios:

| | qué hace | qué dice |
|---|---|---|
| `confirm_and_estimate` | `include_histogram: bool = False` | *«default False — saves tokens»* |
| `model_histogram` | herramienta aparte, **0 llamadas** en 1.114 | *«the histogram is not part of the basic diagnostic module — request it explicitly»* |
| **`estimate_and_diagnose`** | **lo mandaba SIEMPRE**, sin parámetro | — |

Dos de los tres dicen que es opcional y el tercero lo impone: **34 KB por
iteración** que nadie pidió, en la herramienta que compone su sobre a mano.

Y en la misma llamada, un segundo defecto: **no decía ninguna ruta**. Los dos
ficheros se escribían y el analista no sabía dónde. El BUG-0113 —«di dónde está
la figura»— cubrió el carril guiado y `_result`; esta vía no pasa por ninguno.

Síntoma que delata el camino: las dos figuras salían con el nombre de la
**herramienta**, `art_estimate_and_diagnose_<huella>.png`, en vez del de la
figura. Dos imágenes de la misma llamada con la misma etiqueta.

## Impact

**Bajo, pero en el sitio de más tráfico.** `estimate_and_diagnose` es una de las
vías por las que se cierra una iteración, y el gasto es por llamada.

Se encontró en el censo de figuras, al lanzar la figura 6 —la de diagnosis, la
piedra angular del método— y ver que llegaban dos imágenes cuando el docstring
de la otra herramienta dice que no debería.

## Reproduction

`estimate_and_diagnose(inp_path=<un .inp estimable>)`: devuelve **dos**
`ImageContent` y el texto no contiene la palabra «Figura».

## Root cause

La herramienta construye su lista de `Content` a mano, así que cada propiedad
transversal —el histograma opcional, la nota con la ruta, la etiqueta del
fichero— tiene que estar implementada aquí otra vez. Ninguna de las tres lo
estaba.

Es el mecanismo que la revisión de arquitectura llama **M2, la propiedad atada
al envoltorio y no al acto**: mientras haya 24 sitios que componen su salida, una
propiedad nueva hay que acordarse de ponerla 24 veces.

## Fix

`include_histogram: bool = False` en la firma, como en `confirm_and_estimate`; y
las rutas se dicen con `_nota_figura` / `_con_nota_figura`, que ya existen. Las
figuras se etiquetan por lo que **son** —`diagnosis`, `histograma`— y no por
quién las pide.

## Validation

```
por defecto      imágenes: 1   ¿dice la ruta?: True
con histograma   imágenes: 2   ¿dice la ruta?: True
ficheros: art_diagnosis_<huella>.png · art_histograma_<huella>.png
```

**Lo que este defecto deja dicho** es más que el arreglo: es el tercer caso del
censo en que una herramienta que compone su sobre a mano se salta una propiedad
que las demás sí tienen (0122 escribir, 0126 la ventana, 0129 la ruta y el
histograma). Refuerza el paso 2.1 de `ORDEN.md`: **un solo `render`**, y estas
tres preguntas dejan de poder contestarse de tres maneras.
