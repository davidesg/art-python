---
id: BUG-0121
title: La ventana de la figura, apagada en TODAS las plataformas por un defecto que era del anfitrión de Windows — en un cliente que no pinta el ImageContent el analista se queda sin figura
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
  - regresion
references:
  - BUG-0111
  - BUG-0078
  - BUG-0082
  - BUG-0113
---

## Summary

Regresión introducida por el arreglo del **BUG-0111**, el mismo día.

El 0111 documentó un defecto real y acotado: en Windows, bajo la aplicación de
escritorio, `os.startfile(png)` lo **intercepta el anfitrión** y lo convierte en
un diálogo modal de adjuntar que saca al analista de su panel, una vez por
figura. El arreglo añadió `_BAJO_SERVIDOR` a la guarda de `_show_fig` — es
decir, apagó la ventana **bajo cualquier servidor MCP, en cualquier
plataforma**.

El razonamiento que autorizó esa generalización está escrito en el propio
comentario:

> *«Ahí la figura ya viaja como `ImageContent` —la ventana es un extra, según
> dice el docstring de `_abrir_visor`—, así que pedirle al shell que la abra no
> aporta nada»*

**Es falso en cualquier anfitrión que no pinte el `ImageContent`.** La imagen
llega al modelo —que puede describirla— y no llega al analista. Ahí la ventana
del escritorio no era un extra: era el único canal por el que el analista veía
la figura.

## Impact

**Alto, y justo donde el 0111 decía que el suyo lo era: el carril guiado.** Las
dos valoraciones son la misma frase con el signo cambiado — «las figuras son la
mitad del trabajo»— y por eso el arreglo no podía ser simétrico entre
plataformas.

Observado en vivo: nodo 1 (Box-Cox) del RATIO de la réplica de Bolivia,
`run5_guiado`, 8-sep. La herramienta devolvió su `ImageContent`, el modelo
describió los dos paneles con sus correlaciones, y el analista no vio nada:

> *«no has renderizado el grafico»* · *«ha cambiado. antes renderizabas y lo
> lanzabas y lo veia. porque ha cambaido»*

Agravante: el 0111 estaba **fixed** y con prueba, y su prueba —inspección del
fuente buscando `_BAJO_SERVIDOR` en `_show_fig`— seguía en verde con la
regresión dentro. Una prueba que fija la IMPLEMENTACIÓN no ve un cambio de
alcance.

Atenuante: el **BUG-0113**, del mismo lote, hizo que la ruta se diga siempre
(`*Figura: …*`). La red funcionó y el analista tenía el fichero — pero es un
`.png` con nombre de huella en el temporal del sistema, no una ventana.

## Reproduction

`bugs/BUG-0121-repro/repro.py` — determinista y sintético: no toca red, ni
`fue`, ni datos. Pregunta a la DECISIÓN, no al efecto, qué hará en cada
plataforma. Antes del arreglo:

    FALLA  so=posix  servidor=True  entorno={}                  abre=False (esperado True)
    ok     so=nt     servidor=True  entorno={}                  abre=False (esperado False)
    FALLA  so=nt     servidor=True  entorno={'ART_VIEWER': '1'} abre=False (esperado True)

Después, los siete casos en verde.

## Root cause

`mcp_server.py`, guarda de `_show_fig`:

```python
if (_BAJO_SERVIDOR or os.environ.get("ART_NO_VIEWER")
        or "pytest" in sys.modules):
    return path
```

`_BAJO_SERVIDOR` responde a *«¿corro como servidor?»*. La pregunta que había que
hacer era *«¿este anfitrión intercepta la petición al shell, y pinta él la
figura?»*, y de ella sólo se había medido una respuesta: la de Windows.

Un defecto medido en un anfitrión se arregló en la condición que lo contiene a
él y a todos los demás.

## Fix

La decisión sale de `_show_fig` a una función que decide y no actúa,
`_visor_procede(bajo_servidor, so, entorno, bajo_pytest)` — la misma separación,
y por la misma razón, que ya se le hizo a `_abrir_visor` en el 0078: bajo pytest
`_show_fig` no llega hasta ahí, así que sin separarlas la decisión sólo se podía
probar leyendo el fuente.

La regla, de llave más fuerte a más débil:

| condición | ventana |
|---|---|
| `pytest` o `ART_NO_VIEWER` | **no** — siempre ganan |
| servidor MCP **y** `os.name == "nt"` **y** sin `ART_VIEWER` | **no** — el 0111, conservado |
| resto (POSIX bajo servidor, biblioteca en cualquier sitio) | **sí** |

`ART_VIEWER` es la llave nueva: enciende donde el 0111 apagaría, para el
anfitrión de Windows que no intercepte —o que sí, y aun así prefiera la ventana.

## Validation

`tests/test_frontera_del_servidor_mcp.py`, sección BUG-0121, colocada
**pegada** a las dos del 0111: son una sola regla y leerlas separadas es cómo se
llega a esto. Seis pruebas — la regresión, el 0111 conservado, la biblioteca en
ambas plataformas, las dos llaves de entorno, y una que exige que `_show_fig`
**consulte** la decisión en vez de reimplementarla (la enfermedad recurrente de
este proyecto es el concepto escrito dos veces y la copia que se queda atrás).

Nota para el analista: el servidor MCP hay que **reiniciarlo** para que el
arreglo tenga efecto en una sesión abierta.
