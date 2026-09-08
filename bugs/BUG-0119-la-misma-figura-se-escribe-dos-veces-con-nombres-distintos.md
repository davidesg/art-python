---
id: BUG-0119
title: La misma figura se escribe dos veces con nombres distintos y el mismo SHA — nada delata que son la misma imagen
status: open
severity: low
component: mcp-tools
found_in: 0.2.0
fixed_in:
reported: 2026-09-08
reporter: David / sesión de Windows — observación (b) del informe de defectos
tags:
  - figuras
  - duplicacion
  - presentacion
references:
  - src/art/mcp_server.py (_show_fig → ART_FIG_DIR)
  - src/art/guion.py (figure_path → figs/ del modelo)
---

## Summary

Una sola llamada a `confirm_and_estimate` escribe **la misma imagen dos veces**,
con nombres que no se parecen. Medido:

    c8f8c72b6ae6   art_diagnosis_89c37232f8ad.png   ← ART_FIG_DIR, vía _show_fig
    c8f8c72b6ae6   figs/S_v1.png                    ← el figs/ del guion
    04b6dda3d77d   figs/S_v1_hist.png               (el histograma, distinto)

Mismo SHA-256 en las dos primeras.

**Cada copia tiene su razón** y ninguna sobra:

  · la de `ART_FIG_DIR` es la que `_show_fig` cita por su ruta —la red del
    BUG-0078, para cuando el visor no abre—;
  · la de `figs/` es la del REGISTRO: viaja con el guion, es hermana suya y por
    eso su ruta se guarda relativa (BUG-0098).

Lo que falla no es que existan dos: es que **nada en sus nombres dice que son la
misma imagen**.

## Impact

Bajo, pero real y observado: en la sesión indujo a enviar la figura dos veces a
la conversación, creyendo que eran distintas. Con doce figuras por sesión guiada
eso es doce oportunidades de repetir el error, y en un canal donde cada imagen
cuesta.

## Fix

Ninguna de las dos se quita. Basta con que **se sepan la misma**:

  · nombrar la de `ART_FIG_DIR` con el mismo tallo que la del registro
    (`S_v1__diagnosis.png` en vez de `art_diagnosis_<hash>.png`), o
  · citar las dos rutas juntas en la nota, diciendo que son copias.

La segunda es más barata y más honesta: no esconde que hay dos ficheros.
