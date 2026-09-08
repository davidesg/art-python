---
id: BUG-0113
title: El carril guiado descarta la ruta que devuelve _show_fig y nunca llama a _nota_figura — si el cliente no renderiza, el analista se queda sin figura y sin ruta
status: fixed
severity: high
component: mcp-tools
found_in: 0.2.0
fixed_in: 0.2.1
reported: 2026-09-08
reporter: David
tags:
  - figuras
  - guiado
references:
  - BUG-0078
  - BUG-0081
  - BUG-0111
---

## Summary

`_show_fig` **devuelve la ruta** del `.png` que acaba de escribir. Es la mitad
del arreglo del BUG-0078, y su propio docstring lo dice: *«Devolver la ruta es
la mitad del arreglo: quien llama puede decirla, y cuando el visor no aparece
el analista tiene el fichero.»* La nota se compone en `_nota_figura` y la
inserta `_result()`.

`guided_identification` **no pasa por `_result()`**: compone su texto a mano y
llama a `_show_fig` en cinco puntos, **descartando el valor devuelto en los
cinco**. Su salida no cita ninguna ruta.

Mientras el cliente renderice el `ImageContent`, no se nota. En cuanto no
renderiza —o el visor del escritorio no abre— el analista se queda **sin figura
y sin fichero al que ir**, y la herramienta ha reportado éxito. Es exactamente
el síntoma que el BUG-0078 venía a cerrar, sobreviviendo por una rendija
distinta.

## Impact

**Alto, y concentrado donde más duele.** El carril guiado es el que produce
casi todas las figuras de una sesión —Box-Cox, serie en nivel, serie
diferenciada, estacionalidad, identificación— y es el carril en el que las
figuras son la mitad del trabajo: el analista decide λ, d, D y los órdenes
*mirándolas*.

El caso se dio de verdad, no es hipotético. En Windows 11 con Claude Code
2.1.260:

* el visor del escritorio **no abre** (el `.png` está asociado a Fotos/UWP y
  `ShellExecuteW` delega y devuelve éxito sin arrancar proceso — prueba 3 de
  `PRUEBA_WINDOWS/RESULTADOS.md`);
* el panel de Code **no renderiza** las imágenes que vienen en un resultado de
  herramienta;
* y la salida guiada **no cita la ruta**.

Tres capas y ninguna red. La sesión avanzó a ciegas hasta que se localizaron
los ficheros a mano.

**Y se agrava con el arreglo de BUG-0111.** Ese informe propone no abrir el
visor cuando se corre como servidor MCP, que es lo correcto — pero entonces la
ruta pasa a ser la única red de seguridad que queda. Los dos arreglos deben
entrar juntos.

## Reproduction

    cd bugs/BUG-0113-repro
    python repro.py

No estima nada: usa los nodos baratos del guiado. Salida observada
(art 0.2.0, Python 3.12.10):

    1 · Llamadas a _show_fig en guided_identification
      con el retorno DESCARTADO : 5
      con el retorno USADO      : 0

    2 · _nota_figura se llama desde…
      txt += _nota_figura(_ruta)
      -> sólo desde _result(), por donde el carril guiado no pasa.

    3 · Contraste: quien cita la ruta y quien no
      boxcox_analysis  (pasa por _result)        cita la ruta: SI
      guided_identification  nodo Box-Cox        cita la ruta: NO
      guided_identification  nodo d=0            cita la ruta: NO

      .png realmente escritos en ART_FIG_DIR: 2
          art_boxcox_f6e1d599e817.png
          art_series_d0_ef2e716689f8.png

La última línea es la que cierra el argumento: **las figuras se escriben en los
dos casos**. No es que el guiado no produzca fichero; es que no dice dónde lo
dejó.

## Root cause

`src/art/mcp_server.py`, dentro de `guided_identification` — cinco llamadas
como sentencia suelta, el retorno al vacío:

    _show_fig(bc.figure_b64, "boxcox")
    _show_fig(b64, "series_d0")
    _show_fig(b64, f"series_d{d}")
    _show_fig(sea.figure_b64, "seasonality")
    _show_fig(ident.figure_b64, "identification")

La red del BUG-0078 vive en `_result()`:

    if desc.figure_b64:
        _ruta = _FIGURAS.get(_huella_figura(desc.figure_b64), "")
        if _ruta:
            txt += _nota_figura(_ruta)

y el carril guiado construye su salida a mano —tiene que hacerlo, porque su
formato es el sobre de cuatro secciones del BUG-0094— así que nunca entra ahí.
No es un descuido de una llamada: es que **la red está atada al envoltorio y no
al acto de escribir la figura**.

## Fix

Lo barato y lo correcto coinciden: recoger la ruta y añadir la nota, en los
cinco puntos.

    ruta = _show_fig(bc.figure_b64, "boxcox")
    ...
    partes.append(_nota_figura(ruta))

Mejor todavía, y es la raíz: **mover la red de `_result()` a `_show_fig`**, o
darle a `_show_fig` un acompañante que devuelva ya la línea compuesta, de modo
que quien escriba una figura no pueda olvidarse de decir dónde quedó. Hoy la
propiedad depende de pasar por un envoltorio concreto, y por eso se pierde en
cuanto una herramienta compone su propio texto.

Conviene revisar de paso si hay otras herramientas que compongan texto a mano
y llamen a `_show_fig`; el repro cuenta las llamadas descartadas por función y
sirve para eso.

### Nota sobre el aviso de visor fallido

Relacionado y ya anotado en `PRUEBA_WINDOWS/RESULTADOS.md`: `_nota_figura` sólo
añade el «⚠ no se pudo abrir sola» cuando `_ULTIMO_VISOR_ERROR` tiene algo, y
en Windows `os.startfile` envuelve a `ShellExecuteW`, que devuelve éxito en
cuanto delega. El fallo es indetectable con esa API, así que el aviso nunca
sale. Bajar el listón —decir siempre «si no se abre sola, la tienes en …»— es
una línea y cubre el caso. Con el arreglo de BUG-0111 puesto, además, deja de
haber ventana que esperar y la frase correcta es simplemente dónde está.

## Validation

* `bugs/BUG-0113-repro/repro.py` debe salir con las tres filas del contraste en
  `SI`, y el censo con 0 llamadas descartadas.
* Prueba de regresión sobre la propiedad, no sobre el caso: **toda salida de
  herramienta que lleve un `ImageContent` debe citar también una ruta**. Se
  recorre la superficie, se llama a las que producen figura y se afirma la
  coexistencia. Eso cierra la familia; una prueba por herramienta no.
* Comprobar que la ruta citada **existe** y corresponde a esa figura y no a
  otra: el índice por contenido del BUG-0081 ya lo garantiza, pero conviene
  afirmarlo aquí, que es donde se consume.

---

## Cierre (2026-09-08)

Las cinco llamadas recogen la ruta y la dicen. La prueba lo fija contando:
`llamadas a _show_fig == llamadas cuyo retorno se usa`, más la exigencia de que
`_nota_figura` aparezca. Si mañana se añade una sexta que lo descarte, salta.
