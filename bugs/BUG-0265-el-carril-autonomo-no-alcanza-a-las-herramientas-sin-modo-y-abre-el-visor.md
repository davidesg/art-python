---
id: BUG-0265
title: El carril autónomo no alcanza a las herramientas sin `modo`, que devuelven sus figuras y abren el visor; y las que tienen `modo` abren el visor igualmente
status: fixed
severity: high
component: mcp
found_in: 0.2.6
fixed_in: 0.2.7
reported: 2026-11-26
reporter: David / Claude — rodaje autónomo de sima (VAR monetario de EE. UU., intervenciones del IPI rehechas en art)
tags:
  - mcp
  - carril-autonomo
  - figuras
  - visor
references:
  - src/art/mcp_server.py _carril_por_carpeta, _aplica_carril_por_carpeta, _VISOR_CALLADO, _show_fig
  - bugs/BUG-0208 (las figuras del autónomo se guardan y no viajan)
  - bugs/BUG-0265-repro/repro.py
---

## Summary

El carril autónomo se declara en cada llamada (`modo="autonomo"`) y solo seis
herramientas lo aceptan (`guided_identification`, `confirm_and_estimate`,
`estimate_and_diagnose`, `guided_intervention`, `suggest_intervention_form`,
`build_model`). Las demás que dibujan —`intervention_analysis`,
`incident_configurations`, `intervention_ladder`, `ar_factorization`,
`overparameterization_analysis`, `residual_outlier_scan`, `meg_frequency`,
`compare_versions` y otras— devolvían su figura como imagen y la abrían en el
escritorio. Y las seis con `modo`, en autónomo, quitaban la imagen de la
respuesta pero abrían el visor igual: `_show_fig` se llama al dibujar, antes
de que el envoltorio la retire.

## Impact

En el rodaje autónomo de sima (2026-11-26), un agente que rehacía las
intervenciones del IPI llamó a `intervention_analysis`: las figuras viajaron
como imágenes (tokens del agente) y se abrieron en el escritorio del analista,
que trabajaba en otra cosa. El analista paró el rodaje.

## Reproduction

`python3 bugs/BUG-0265-repro/repro.py` (sale con 1 mientras esté abierto):
`confirm_and_estimate(modo="autonomo")` sobre una serie y luego
`intervention_analysis` sobre la misma; cuenta imágenes devueltas y ventanas
pedidas (el visor se sustituye por un registro). Comprueba además que una
llamada guiada a la misma serie las sigue mostrando.

## Root cause

El carril vivía en el argumento de la llamada, y solo seis herramientas lo
tenían; el visor se abría en `_show_fig`, sin saber del carril.

## Fix

El carril se recuerda por CARPETA de la serie (`_CARRIL_CARPETA`, en memoria
del servidor). Toda herramienta registrada pasa por `_carril_por_carpeta`:
- si tiene `modo`, fija el carril de las carpetas que nombra, también cuando
  queda en su valor por defecto «guiado»: el carril guiado devuelve la carpeta
  a guiado en su primera llamada a `guided_identification` o
  `confirm_and_estimate`;
- si no lo tiene, sigue el carril de su carpeta;
- en autónomo, la llamada no abre ventanas (`_VISOR_CALLADO`, que consulta
  `_show_fig`) y sus figuras se guardan junto al modelo en vez de viajar, como
  en BUG-0208; `con_figuras=True` las devuelve.
- En guiado no cambia nada.

## Validation

El repro pasa a 0 (autónomo: 0 imágenes y 0 ventanas en las dos llamadas;
guiado: imagen y ventana). La batería de art pasa contra la rama.
