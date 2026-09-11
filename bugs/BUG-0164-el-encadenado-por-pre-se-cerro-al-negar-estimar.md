---
id: BUG-0164
title: Las cuatro puertas del carril guiado rechazaban un `.pre` — BUG-0159 cerró `estimar` y ellas seguían llamándola sin necesitarla
status: fixed
severity: high
component: mcp-tools
found_in: 0.2.1
fixed_in: 0.2.1
reported: 2026-09-11
reporter: Claude (al probar BUG-0162)
tags:
  - contrato-de-ficheros
  - regresion
  - intervenciones
references:
  - BUG-0090
  - BUG-0150
  - BUG-0159
  - BUG-0162
---

## Summary

**Regresión introducida en esta misma sesión.** BUG-0159 hizo que `estimar()`
RECHAZARA un `.pre` — correcto, y sigue siéndolo. Lo que no se revisó entonces
es quién llamaba a `estimar` **sin necesitarla**, y cuatro de las que lo hacían
son las puertas del carril guiado:

| herramienta | qué saca del modelo que carga |
|---|---|
| `guided_intervention` | estructura y residuos; las SE que publica son de los **candidatos**, estimados aparte |
| `suggest_intervention_form` | estructura; las SE son las del modelo **nuevo**, reestimado desde su propio `.inp` |
| `incident_configurations` | el **base** sobre el que se estima cada configuración |
| `guided_identification` | residuos, μ y los órdenes del base — **ninguna razón t** |

La última tiene el parámetro llamado **`pre_path`**.

Resultado: encadenar por `.pre` —que es el modo NORMAL del nodo, el que
`base_pre_path` nombra— devolvía

    ⛔ **No se puede hacer eso con este fichero.**

La negativa estaba bien escrita y era la equivocada.

## Por qué la suite no lo vio

**Ninguna prueba encadenaba desde un `.pre`.** El arreglo de BUG-0159 tocó 15
sitios de prueba y todos se repararon apuntando al `.inp` hermano — que es lo
correcto para las que estiman, y borró de paso el único camino que habría
enseñado esto. La suite quedó en verde midiendo un flujo que el analista no usa.

Lo destapó ejercitar BUG-0162 de punta a punta: al construir la cadena
`m00.pre → m10 → rehacer` la segunda llamada murió con un `FileNotFoundError`
sobre un `.pre` que nunca se escribió, porque la herramienta había devuelto la
negativa en vez de estimar.

Es la lección de BUG-0158 otra vez, del otro lado: **un arreglo que sólo se
comprueba donde ya se miraba no se ha comprobado.**

## Fix

Las cuatro pasan a `_mirar`, con la razón escrita en cada sitio. Y la regla, que
ya estaba enunciada en BUG-0159, queda dicha en su forma operativa:

> Quien imprime **las desviaciones típicas DEL MODELO QUE CARGA** necesita
> `estimar`. Quien sólo toma de él la estructura, la serie o los residuos
> —porque las SE que publica son de **otro** modelo, estimado después— necesita
> `mirar`.

`test_interventions`, `model_equation_display`, `formal_tests`,
`ar_factorization`, `estimate_and_diagnose`, `confirm_and_estimate`,
`overparameterization_analysis`, `full_report` y `get_out_report` siguen
estimando, que es lo que les toca.

## Validation

`tests/test_bug_0162_rehacer_no_solo_anadir.py`, sección de BUG-0164: las tres
puertas del nodo y `guided_identification` aceptan un `.pre` sin devolver la
negativa; y —la otra mitad— `test_interventions` sigue negándose, porque publica
razones t del modelo que carga. La prueba construye la cadena real
`m00.pre → m10.pre → rehacer`, que es el hueco de cobertura que dejó pasar esto.
