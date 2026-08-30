---
id: BUG-0064
title: guion_map volcaba los cinco campos de texto sin límite y se truncaba a fichero — 52.921 bytes en 56 líneas, y precisamente en la serie con más ramas
status: fixed
severity: medium
component: mcp-server
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-29
reporter: carril Claude del RUN 3 — defecto (8) de su informe
tags:
  - guion
  - presentation
  - output-size
references:
  - src/art/mcp_server.py (guion_map)
  - tests/test_bug_0064_el_mapa_cabe.py
  - bugs/BUG-0064-repro/repro.py
---

## Summary

El mapa imprimía `decidido`, `evidencia`, `razón`, `descartado` y `callejón`
**sin límite**, uno por línea. Con nodos bien razonados eso son ~945 bytes por
línea.

| serie | nodos | antes | después | reducción |
|---|---|---|---|---|
| RATIO | 18 | **52.921 B** | 9.868 B | 81 % |
| PGAS | 16 | 44.030 B | 9.258 B | 79 % |
| ITCER | 13 | 28.577 B | 7.897 B | 72 % |

RATIO se pasaba del límite de salida y se truncaba a fichero — **justo la serie
con más ramas**, o sea donde más información había que ver. El defecto crece con
la calidad de la documentación: cuanto mejor razonados los nodos, antes se
rompe.

## La intención ya estaba escrita

En `_record_to_guion`, sobre por qué esa función devuelve una sola línea:

> *«el registro es interno y la salida no debe crecer por documentar. Quien
> quiera ver lo documentado llama a `export_guion`»*

El mapa es un **mapa**: sirve para orientarse en el laberinto. El texto completo
vive en el guion y se lee con `export_guion`, que además lo deja en HTML
navegable. Lo que faltaba era que `guion_map` se comportara como lo que dice ser.

## Fix

* Los cinco campos se recortan (190 caracteres el titular de la decisión, 150 el
  resto), **cortando por palabra** para no partir una cifra por la mitad.
* El recorte **se anuncia**: «⋯ N textos recortados para que el mapa quepa», con
  las dos formas de ver lo entero. Un recorte silencioso habría sido peor que el
  desbordamiento — el analista creería estar leyendo el razonamiento completo.
* `detalle=True` devuelve el texto intacto, para quien lo quiera.

**Se recorta el TEXTO, no el árbol.** El mapa sigue mostrando todas las
entradas, todas las ramas y todos los callejones: lo que se pierde es la
extensión de cada razón, que es exactamente lo que `export_guion` conserva. Hay
un test que lo fija.
