---
id: BUG-0147
title: Seis herramientas escriben su figura y no dicen dónde — el otro medio BUG-0122, y sólo se ve cruzando la frontera
status: open
severity: medium
component: mcp-tools
found_in: 0.2.2
fixed_in:
reported: 2026-09-10
reporter: la prueba de frontera de ORDEN 0.1, en su primera ejecución
tags:
  - figuras
  - mcp-tools
  - frontera
references:
  - BUG-0122
  - ORDEN.md fase 2.2
---

## Summary

BUG-0122 arregló la mitad del problema: `_imagen` es hoy el único constructor
de `ImageContent` y **siempre escribe** el fichero. La otra mitad seguía
abierta y no se veía: **la ruta no se dice**.

Sólo `_result` cita la ruta escrita. Las herramientas que componen su sobre a
mano —`items = [TextContent(...)]; items.append(_imagen(...))`— devuelven la
imagen y dejan el fichero en disco sin que nada en el texto diga dónde está.

    herramientas totales                       46
    construyen figura con `_imagen`            13
    pasan por `_result` (y citan la ruta)      15
    llaman a `_imagen` a mano y NO citan ruta   6

Las seis: `preliminary_outlier_scan`, `residual_outlier_scan`,
`model_histogram`, `record_version`, y —ya sin figura desde BUG-0137, o sea
muertas— `overparameterization_analysis` y `compare_versions`. **Cuatro vivas.**

## Impact

El analista ve la figura en el cliente y no puede volver a ella: no sabe el
nombre del fichero. En un cliente que no pinta `ImageContent` —el caso que
motivó BUG-0121— la figura simplemente no llega y tampoco hay ruta que seguir.
Y sobre el escaneo pre-identificación, que es la puerta del nodo de
intervención, eso es la figura más mirada del carril guiado.

## Reproduction

Cruzando la frontera, que es la única forma de verlo:

```python
r = await s.call_tool("preliminary_outlier_scan",
                      {"inp_path": CASO, "d": 1, "D": 0,
                       "lam": 0.0, "threshold": 2.0})
tipos = [type(c).__name__ for c in r.content]     # ['TextContent', 'ImageContent']
texto = "\n".join(c.text for c in r.content if getattr(c, "text", None))
assert ".png" in texto                            # ✗ falla
```

En el proceso de pytest esto **no se distingue**: llamando a la función
directamente se obtiene la misma lista y nadie mira si el texto cita la ruta.
Por eso sobrevivió al censo de figuras entero.

## Root cause

`mcp_server.py`. Dos formas de componer el sobre —`_result`, que cita, y la
lista a mano, que no— y trece sitios que eligen una de las dos. Es M2 de
CABLEADO y la razón de ser del paso 2.1 de `ORDEN.md`.

## Fix

**No se arregla en los seis sitios.** Cae en `ORDEN.md` 2.2, cuando las 46
pasen por `render`: escribir la figura, anotar su ruta y citarla es una sola
operación de la capa de salida, y hacerlo ahora a mano son cuatro sitios más
que recordar cuando llegue `render` — exactamente lo que el plan dice que no se
haga.

Mientras tanto la prueba de frontera lo deja **en rojo documentado**
(`xfail(strict=True)`), con el mismo criterio que `ORDEN` 0.2 aplica al
presupuesto de descripciones. Cuando 2.2 cierre, el `xfail` pasa a `xpass` y
hay que quitarlo: ésa es la señal de que la capa hizo su trabajo.

## Validation

`tests/test_frontera_mcp.py::test_una_herramienta_con_figura_devuelve_imagen_Y_ruta`
