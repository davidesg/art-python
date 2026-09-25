---
id: BUG-0191
title: Lo que art usa no está en sus dependencias — las tres herramientas de previsión fallan en toda instalación limpia (falta jinja2), y pandas y openpyxl llegan de rebote por pyfug
status: fixed
severity: critical
component: packaging
found_in: 0.2.1
fixed_in: 0.2.2
reported: 2026-09-25
reporter: David — prueba de las ruedas en un entorno limpio antes de publicar
tags:
  - packaging
  - dependencias
  - entorno-limpio
references:
  - fue/pyproject.toml, extra `report` (jinja2)
  - docs/PUBLISHING.md, «Probar en un entorno limpio»
  - tests/test_bug_0191_dependencias_declaradas.py
---

## Summary

Instaladas las ruedas en un entorno virtual limpio —como las recibe un usuario—,
`generate_forecast`, `update_and_forecast` y `sps_dashboard` fallan:

    ImportError: write_forecast_report requires jinja2 — pip install jinja2

art escribe el informe de previsión con `fue.report_forecast.write_forecast_report`,
que necesita jinja2. En fue, jinja2 es el extra opcional `report`
(`pip install "fue[report]"`), y art dependía de `fue` a secas.

Al mirar, dos más del mismo tipo: art importa **pandas** (`load_data`,
`preview_data`, `create_inp` leen Excel y CSV con él) y necesita **openpyxl** (el
motor que pandas carga para `.xlsx`, sin que ningún import lo nombre), y no
declara ninguno de los dos: llegan porque pyfug los trae.

## Impact

**Crítico, y publicado.** Los metadatos de la 0.2.1 en PyPI declaran `fue>=0.1.14`,
`pyfug`, `numpy`, `matplotlib`, `scipy`, `statsmodels` y `mcp`: cualquiera que la
instale hoy tiene rotas las tres herramientas de previsión. Lo de pandas/openpyxl
es latente: funciona mientras pyfug los traiga, y el TODO de la 0.3 ya propone
aligerar pyfug.

## Reproduction

    python -m venv env && env/bin/pip install art-tseries==0.2.1
    env/bin/python -c "import jinja2"        # ModuleNotFoundError

y `generate_forecast` sobre cualquier `.pre` devuelve el ImportError.

## Root cause

**Los entornos de desarrollo tenían todo instalado por otra vía**, así que ni la
suite ni el uso diario podían verlo. El smoke test del CI instala la rueda en un
entorno limpio, pero sólo comprueba que el servidor arranca y expone sus
herramientas; no llama a ninguna que escriba un informe.

## Fix

* `pyproject.toml`: `fue[report]>=0.1.14`, `pandas>=2.0` y `openpyxl>=3.1`, con el
  porqué comentado como los demás pines.
* `tests/test_bug_0191_dependencias_declaradas.py`: todo módulo de terceros que
  art importa —también dentro de funciones— está en `[project] dependencies`; lo
  que se carga en ejecución sin import (openpyxl) también; y si art usa el
  informe de fue, la dependencia es `fue[report]`.
* `docs/PUBLISHING.md`: probar en un entorno limpio con las suites, antes de
  etiquetar.

## Validation

Las tres pruebas fallan con el `pyproject.toml` anterior. Y la prueba de verdad:
reconstruir las ruedas, instalarlas en un entorno limpio y correr la suite.
