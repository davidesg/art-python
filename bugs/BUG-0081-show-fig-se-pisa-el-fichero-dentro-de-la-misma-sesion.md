---
id: BUG-0081
title: `_show_fig` se pisa el fichero dentro de la MISMA sesión — el discriminante de BUG-0078 es `os.getpid()` y el servidor MCP es un solo proceso; y `_result` publica la ruta de `_ULTIMA_FIGURA`, una global mutable, no la de su propia figura
status: fixed
severity: medium
component: mcp-tools
found_in: 0.1.12
fixed_in: 0.1.12
reported: 2026-09-04
reporter: David / sesión guiada FOOD_UEM — dos series por los mismos nodos
tags: [presentation, figures, race]
references:
  - src/art/mcp_server.py:670 (_show_fig), :692 (la ruta), :581 (_result)
  - bugs/BUG-0081-repro/repro.py
  - BUG-0078 (introdujo el discriminante)
---

## Summary

BUG-0078 se cerró añadiendo un discriminante *«para que dos herramientas con la
misma etiqueta no se pisen la figura»*:

```python
path = os.path.join(tempfile.gettempdir(), f"art_{etq}_{os.getpid()}.png")
```

El discriminante es **el proceso**, y el servidor MCP es **un único proceso**
durante toda la sesión. Dentro de una sesión, por tanto, no discrimina nada: dos
llamadas con la misma etiqueta siguen escribiendo el mismo fichero. Es
exactamente el defecto que BUG-0078 decía arreglar, con un discriminante que sólo
separa sesiones distintas —que ya estaban separadas por el reloj—.

Y hay un segundo, del mismo bloque: `_result()` publica la ruta leyendo la global
`_ULTIMA_FIGURA` (mcp_server.py:581), no la ruta de la figura que esa llamada
está devolviendo. Con llamadas intercaladas, la respuesta de una herramienta cita
el fichero de otra.

## Impact

El caso real: dos series (HICP alimentos y HICP servicios) recorriendo los mismos
nodos guiados. Las dos escriben `art_boxcox_<pid>.png`, `art_series_d1_<pid>.png`,
`art_seasonality_<pid>.png`. El analista abre el fichero que la salida le nombra
y ve el diagrama de la OTRA serie, mientras lee los números de ésta. No hay aviso
de nada: las dos llamadas reportan éxito.

Agravante: la nota con la ruta se añadió en BUG-0078 precisamente para que
«cuando la ventana no aparece el analista tenga el fichero». Con la global, esa
nota puede apuntar a un fichero que no es el suyo — es decir, la red de seguridad
falla de la misma forma que aquello que venía a cubrir.

## Reproduction

`bugs/BUG-0081-repro/repro.py` — determinista, sin ventanas (`ART_NO_VIEWER`):

```
figura de la serie 1 -> /tmp/art_boxcox_338879.png
figura de la serie 2 -> /tmp/art_boxcox_338879.png
MISMA RUTA: True

_ULTIMA_FIGURA tras una tercera llamada: /tmp/art_identificacion_338879.png
...y _result() publica ESA, no la de la Description que recibe
COLISION: el contenido de la serie 1 quedo sobrescrito por el de la 2.
```

## Fix (propuesto)

1. Discriminante **por llamada**, no por proceso: un contador de sesión o
   `uuid4().hex[:8]` en el nombre. Si se quiere conservar la propiedad de que la
   ventana se reemplace en vez de multiplicarse, que el discriminante sea
   (etiqueta, serie), no (etiqueta, proceso).
2. `_show_fig` ya **devuelve** la ruta: que `_result` reciba y publique ESA, en
   vez de leer `_ULTIMA_FIGURA`. La global puede quedarse para otros usos, pero
   no debe ser la fuente de la nota.

---

## Fix (aplicado, 2026-09-04)

**1. El discriminante es el CONTENIDO de la figura**, no el proceso:

```python
path = os.path.join(dest, f"art_{etq}_{_huella_figura(b64)}.png")
```

El reporte proponía (etiqueta, serie). La huella del contenido es **más fuerte**
—no colisiona nunca, ni entre series ni entre reestimaciones de la misma— y
además conserva sola la propiedad que se quería: una figura idéntica da la misma
huella, así que la ventana se reemplaza en vez de multiplicarse. Y no obliga a
tocar las ~40 llamadas para pasarles el nombre de la serie.

**2. `_result` cita SU figura.** Un registro de sesión `huella → ruta`, poblado
por `_show_fig` y consultado por `_result` a partir del `figure_b64` que recibe.
Es lo único que identifica a la figura sin cambiar todas las llamadas: `_result`
no tiene más que el b64.

Y si esa figura no se escribió, **no se cita ninguna ruta**. Mejor ninguna nota
que una que apunta al fichero de otra serie: la nota existe justamente para
cuando la ventana no aparece, así que una nota que miente hace fallar la red de
seguridad de la misma forma que aquello que venía a cubrir.

El registro está acotado (`_FIGURAS_TOPE = 256`, se expulsa la más antigua): una
sesión larga no puede acumular una entrada por figura para siempre.

`_ULTIMA_FIGURA` se conserva —hay otros usos— pero deja de ser la fuente de la
nota.

## Validation — resultado

`bugs/BUG-0081-repro/repro.py` sale 0. Se reescribió para que ejerza el código
real en vez de describirlo: comprueba (A) que dos series por el mismo nodo
conservan cada una su fichero **y su contenido**, (B) que la misma figura vuelve
al mismo fichero, y (C) lo que `_result` acaba publicando.

```
== A. Dos series por el mismo nodo
  serie 1 -> /tmp/art_boxcox_0c5fd49514fb.png
  serie 2 -> /tmp/art_boxcox_f785dec3ecc5.png
  cada serie conserva su fichero: OK
== B. la misma figura vuelve al mismo fichero: OK
== C. _result cita /tmp/art_boxcox_f785dec3ecc5.png -> la suya: OK
```

`tests/test_bug_0081_0082_figuras.py`, 11 pruebas (compartidas con BUG-0082).

**Y una prueba de BUG-0078 hubo que cambiarla**, porque fijaba el defecto:
`assert str(os.getpid()) in p, "la ruta discrimina por proceso"`. Ese aserto
era la afirmación equivocada —el pid sólo separa sesiones, que ya estaban
separadas por el reloj— así que se sustituye por la propiedad que de verdad hace
falta: dos figuras distintas con la misma etiqueta no comparten fichero **ni
contenido**.
