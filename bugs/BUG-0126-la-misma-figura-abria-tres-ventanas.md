---
id: BUG-0126
title: La misma figura abría tres ventanas — escribir y enseñar eran la misma función, y el arreglo del 0122 añadió dos llamadas más
status: fixed
severity: medium
component: mcp-tools
found_in: 0.2.1
fixed_in: 0.2.2
reported: 2026-09-09
reporter: David
tags:
  - figuras
  - visor
  - mcp
  - regresion
references:
  - BUG-0078
  - BUG-0121
  - BUG-0122
---

## Summary

`_show_fig` hacía dos cosas: **escribir** la figura y **abrirla**. Escribir es
idempotente y se pide tantas veces como haga falta; abrir una ventana no. Con las
dos pegadas, cada sitio que necesitaba la RUTA abría además una ventana.

Para una figura que sale por la vía genérica, eso son **tres**:

```
1) boxcox_analysis:1961  -> _show_fig     la herramienta pide la ruta para decirla (BUG-0113)
2) _result:921           -> _show_fig     la nota la vuelve a pedir              (BUG-0122)
3) _imagen:901           -> _show_fig     el constructor de la salida            (BUG-0122)
```

Antes del BUG-0122 abría **una**. Las otras dos las añadí al arreglarlo: la
figura ya no se perdía, pero se enseñaba tres veces.

## Impact

**Medio, y de los que cansan.** Lo reportó el analista a la segunda figura de un
recorrido de quince: *«Es correcta pero ha saltado 3 veces»*. En una sesión
guiada normal —doce figuras— son treinta y seis ventanas.

Y es la **tercera vez en dos días** que la misma propiedad se rompe por vivir en
más sitios de los que el arreglo tocó: 0111 → 0121 (el visor apagado de más),
0122 (quince herramientas sin escribir), y ahora 0126 (tres ventanas por
figura). Las tres veces el arreglo era correcto para lo que medía.

**Por qué ninguna prueba lo vio:** las 1.617 comprueban que el **fichero** se
escribe. **Ninguna cuenta ventanas**, porque bajo pytest el visor no se abre
—con razón, abriría cientos— y nadie separó «no abrir en la suite» de «poder
contar cuántas abriría».

## Reproduction

`bugs/BUG-0126-repro/repro.py`, determinista y sintético: sustituye
`_abrir_visor` por un contador y compara **ventanas abiertas** contra **imágenes
devueltas**. Antes del arreglo:

```
boxcox_analysis            imágenes: 1   VENTANAS: 3
identification_analysis    imágenes: 1   VENTANAS: 3
model_histogram            imágenes: 1   VENTANAS: 1
```

## Root cause

Una función con dos responsabilidades. Es la forma de defecto que este proyecto
ya tiene nombrada —**decidir, actuar y presentar en la misma función**— y cuya
solución también: el 0078 separó `_abrir_visor` de `_show_fig`, el 0121 separó
`_visor_procede` de `_abrir_visor`, y el 0122 dejó un solo constructor de
`ImageContent`. Faltaba el corte de en medio.

## Fix

`_escribe_fig(b64, etiqueta)` escribe, registra y devuelve la ruta. **No abre
nada.** `_show_fig` pasa a ser `_escribe_fig` **más** la ventana, y dentro del
servidor lo llama **sólo `_imagen`** — es decir, una ventana por imagen
devuelta, ni más ni menos. Las 21 llamadas directas de las herramientas pasan a
`_escribe_fig`.

`_show_fig` conserva nombre y semántica porque fuera del servidor —cuadernos,
guiones, la biblioteca— «enseñar una figura» es exactamente lo que se quiere
pedir.

## Validation

Medido sobre las herramientas, no sobre el fuente:

```
herramienta                   imágenes  ventanas
boxcox_analysis                      1         1  OK
identification_analysis              1         1  OK
model_histogram                      1         1  OK
unit_root_analysis                   1         1  OK
residual_outlier_scan                1         1  OK
```

Y en `tests/test_frontera_del_servidor_mcp.py`, sección BUG-0126: un **censo**
—`_show_fig` sólo se llama desde `_imagen`— y una prueba que **cuenta ventanas**
sustituyendo `_abrir_visor`, que es la clase de prueba que faltaba. Es el patrón
del censo del 0122: afirmar la propiedad sobre toda la superficie, no un caso
sobre una herramienta.
