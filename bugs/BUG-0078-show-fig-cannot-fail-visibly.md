---
id: BUG-0078
title: _show_fig no puede fallar visiblemente — silencia el visor, no comprueba nada, pisa el fichero, nunca dice dónde escribió, y sólo funciona en Linux
status: fixed
severity: medium
component: mcp-tools
found_in: 0.1.12
fixed_in: 0.2.0 (unreleased)
reported: 2026-09-03
reporter: David / run 5 guiado — «no se renderizó»
tags:
  - presentation
  - figures
  - silent-failure
references:
  - src/art/mcp_server.py (_show_fig)
  - tests/test_bug_0078_show_fig.py
  - P13 en replica/run5_guiado/PROBLEMAS.md (la figura que abría ventana era la que sobra)
---

## Summary

```python
def _show_fig(b64, label="art") -> None:
    """Save figure to /tmp and open with xdg-open (non-blocking)."""
    ...
    path = f"/tmp/art_{label...}.png"
    threading.Thread(
        target=lambda: subprocess.Popen(["xdg-open", path],
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL),
        daemon=True,
    ).start()
```

Catorce líneas con cuatro problemas, y los cuatro apuntan al mismo sitio: **la
función no puede fallar de forma visible.**

**Silencia al visor.** `stdout` y `stderr` van a `/dev/null`, así que si el
visor no arranca, no encuentra el display o revienta, el mensaje se pierde.

**No comprueba nada.** El `Popen` va en un hilo daemon del que nadie recoge el
resultado. El código de salida no se mira nunca.

**Pisa el fichero entre herramientas.** La ruta es estable **por etiqueta**, y
la etiqueta la elige cada herramienta a mano. Dos herramientas con la misma
etiqueta se sobrescriben la figura, y el analista se queda mirando la de otra
llamada — que es exactamente lo que pasó con `art_episodios.png`.

**Y nunca dice dónde escribió.** La salida de la herramienta no menciona la
ruta, así que cuando la ventana no aparece no hay nada a lo que agarrarse.

**Y sólo funciona en Linux.** `xdg-open` es de freedesktop: en Windows hace
falta `os.startfile` y en macOS `open`. Además la ruta era `/tmp/...` cableada,
y `/tmp` no existe en Windows.

Lo señaló el analista, y el matiz importa: *«en claude code windows los gráficos
se renderizaban bien»*. Y es cierto — **por la otra vía**. La figura viaja
también como `ImageContent` en la respuesta MCP, y eso lo pinta el cliente en
cualquier sistema. La ventana de escritorio es un extra, y ese extra **no ha
funcionado nunca fuera de Linux** sin que nadie lo supiera, porque el
`FileNotFoundError` se lo tragaba el hilo daemon.

## Repro

Run 5 guiado, ITCER m10. `guided_identification` genera la figura correcta y la
escribe en `/tmp/art_identification.png` (81 KB, verificado). La ventana no
aparece. La herramienta reporta éxito, la salida no menciona ninguna ruta, y no
hay ningún indicio de que algo haya fallado.

El visor por defecto del sistema era `display-im6` (ImageMagick).

## Fix

- El visor se lanza **capturando** su salida y con un `timeout` corto; si falla
  o no existe, se devuelve el motivo en vez de tragárselo.
- `_show_fig` **devuelve la ruta** (o `""`), y quien la llama puede decirla.
- La ruta lleva un **discriminante por proceso** además de la etiqueta, para
  que dos herramientas no se pisen el fichero.
- Y se añade una nota de una línea con la ruta al pie de las salidas que
  emiten figura: cuando la ventana no aparece, el analista tiene el fichero.
- **Multiplataforma**: `os.startfile` en Windows, `open` en macOS, `xdg-open`
  en Linux; y el directorio temporal sale de `tempfile.gettempdir()`.

## La regresión que el arreglo introdujo, y que también se corrige

Hacer el lanzamiento **síncrono** —necesario para poder detectar los fallos del
visor, que es el bug— hizo que **la suite abriera una ventana por cada figura
que genera**: cientos, y las de prueba en blanco. La versión anterior con
`Popen` en hilo daemon fallaba tan deprisa que casi nunca llegaba a abrir nada,
y por eso el problema estaba latente.

Guarda: no se abre ventana bajo `pytest` ni con `ART_NO_VIEWER` en el entorno.
El fichero se escribe igual, que es lo que una prueba comprueba. Y el
lanzamiento vive en `_abrir_visor()` aparte, para poder ejercitar sus caminos
de fallo sin abrir nada.

## Test

`tests/test_bug_0078_show_fig.py`
