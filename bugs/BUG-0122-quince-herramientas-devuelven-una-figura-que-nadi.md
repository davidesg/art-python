---
id: BUG-0122
title: Quince de las veintiocho herramientas que devuelven figura no la escriben — viaja sólo como imagen en la respuesta MCP, sin fichero, sin ventana y sin ruta, y la herramienta reporta éxito
status: fixed
severity: high
component: mcp-tools
found_in: 0.2.1
fixed_in: 0.2.2
reported: 2026-09-08
reporter: David
tags:
  - figuras
  - visor
  - mcp
references:
  - BUG-0078
  - BUG-0081
  - BUG-0111
  - BUG-0113
  - BUG-0119
  - BUG-0121
---

## Summary

Una figura sale del servidor por dos vías: `_result(desc)`, la genérica, y un
`ImageContent` construido a mano. Ninguna de las dos **escribía** la figura.

`_show_fig` es quien escribe el `.png`, lo apunta en `_FIGURAS` y abre la
ventana. `_result` no la llama: **busca** la huella en `_FIGURAS` por si otro la
escribió, y si nadie lo hizo se calla y no cita ninguna ruta. Los veintitrés
sitios que construían el `ImageContent` a mano tampoco la llamaban.

Resultado, medido sobre las herramientas que pueden devolver figura:

| | |
|---|---|
| herramientas que devuelven figura | **28** |
| escriben el fichero | 13 |
| **no lo escriben en ninguna rama** | **15** |

Para esas quince la figura viajaba **sólo** como imagen en la respuesta MCP: sin
fichero en disco, sin ventana del escritorio y sin ruta que citar — con la
herramienta reportando éxito. En un anfitrión que no pinta el `ImageContent`,
eso es una figura que no existe para el analista.

Las quince: `ar_factorization`, `batch_build`, `build_model`,
`compare_versions`, `guion_evidencia`, `incident_configurations`,
`intervention_analysis`, `meg_frequency`, `meg_reformulate`, `model_histogram`,
`overparameterization_analysis`, `preliminary_outlier_scan`, `record_version`,
`seasonal_param_analysis`, `test_seasonal_simplification`.

## Impact

**Alto, y concentrado justo donde duele.** No es una lista de herramientas
menores: están el histograma, el MEG en sus dos formas, la factorización del AR,
la sobreparametrización, la evidencia del guion y el escaneo previo de anómalos.
Son las figuras de los puntos de decisión.

Visto en vivo, y por eso se levanta: en el `m00` de RATIO (réplica de Bolivia,
`run5_guiado`, 8-sep) la salida trajo **dos** figuras. La de diagnosis abrió su
ventana y se pudo archivar. La del escaneo de anómalos —el panel de tres
cuadros que descompone la ACF y la PACF en «parte debida al outlier», que es la
evidencia calibrada del punto de decisión— llegó sin ventana, sin fichero y sin
ruta, en el momento exacto en que el analista tenía que decidir si intervenir
antes de identificar el ARMA.

Emparentado con toda la familia 0078 · 0081 · 0111 · 0113 · 0119 · 0121, que es
siempre la misma pregunta —¿llega la figura al analista?—. Los seis anteriores
arreglaron el CAMINO; ninguno se preguntó **quién entra en él**.

## Reproduction

`bugs/BUG-0122-repro/repro.py` — determinista y sintético: una `Description` con
un PNG de un píxel, por las dos vías. Antes del arreglo:

    FALLA  _result escribe la figura que devuelve
    FALLA  _imagen escribe la figura que devuelve  (no existe: los 23 sitios la construían a mano)
    FALLA  el ImageContent nace en UN sitio (23 fuera de _imagen)

Y en salida real, sobre el propio caso RATIO:

    preliminary_outlier_scan       figs=1 con fichero=0  ** SIN FICHERO **
    model_histogram                figs=1 con fichero=0  ** SIN FICHERO **
    guion_evidencia                figs=2 con fichero=0  ** SIN FICHERO **
    overparameterization_analysis  figs=1 con fichero=0  ** SIN FICHERO **
    residual_outlier_scan          figs=1 con fichero=1  OK
    identification_analysis        figs=1 con fichero=1  OK

## Root cause

El `ImageContent` se construía en **veintitrés sitios**, y en cada uno había que
acordarse de llamar antes a `_show_fig`. Quince herramientas no se acordaron.

Es otra vez la enfermedad recurrente de este proyecto —un concepto escrito más
de una vez y las copias que se quedan atrás—, en su forma más cara: aquí no
estaba escrito dos veces, sino veintitrés, y lo que faltaba en quince de ellas
era justo la mitad que produce el efecto visible.

`_result` agravaba el diagnóstico en vez de salvarlo, porque su comentario
declara la degradación como intención: *«la ruta se busca por el CONTENIDO de
esta figura… Si esta figura no se escribió, no se cita ninguna: mejor ninguna
nota que una que apunta al fichero de otra serie»* (BUG-0081). La conclusión es
correcta y la premisa no se cuestionó: **que la figura no se escribiera no era
un caso a tolerar, era el defecto**.

## Fix

Un solo constructor, `_imagen(b64, etiqueta)`, que devuelve el `ImageContent`
**y escribe**. Es ahora el único sitio del módulo donde nace un `ImageContent`,
de modo que olvidarse de escribir deja de ser posible. Los veintitrés sitios
pasan por él.

Y `_result` **escribe** antes de citar, en vez de sólo buscar:

```python
_ruta = _show_fig(desc.figure_b64) or _FIGURAS.get(
    _huella_figura(desc.figure_b64), "")
```

Llamar de más no duplica nada: `_show_fig` discrimina por CONTENIDO desde el
BUG-0081, así que la misma figura da el mismo fichero y la ventana se reemplaza
en vez de multiplicarse.

## Validation

Cuatro pruebas en `tests/test_frontera_del_servidor_mcp.py`, sección BUG-0122:
que `_result` escribe y no sólo busca; que el `ImageContent` nace en un solo
sitio; que `_imagen` escribe **de verdad** (con `ART_FIG_DIR` a un temporal, no
por inspección del fuente); y el **censo**, que recorre el AST y falla si
cualquier herramienta futura construye un `ImageContent` sin pasar por
`_imagen` — que es la medida que encontró el defecto, convertida en guarda.

Comprobado además en salida real: las seis herramientas medidas arriba pasan a
`con fichero = figs`.
