---
id: BUG-0063
title: el bloque de la media decía «deriva de residuos de X.pre» y medía la serie diferenciada — la cifra siempre fue la correcta, la etiqueta desmentía la razón por la que lo es
status: fixed
severity: medium
component: mcp-server
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-29
reporter: carril Claude del RUN 3 — defecto (7) de su informe
tags:
  - presentation
  - mean
references:
  - src/art/mcp_server.py (guided_identification — mu_decision)
  - bugs/BUG-0013-mean-significance-measured-on-residuals.md
  - tests/test_bug_0063_etiqueta_de_la_deriva.py
  - bugs/BUG-0063-repro/repro.py
---

## Summary

`guided_identification` con `pre_path` publica dos cosas con orígenes distintos:

* la **identificación ARMA**, que **sí** se calcula sobre los residuos del `.pre`;
* la decisión de la **media**, que BUG-0013 puso deliberadamente sobre la
  **serie diferenciada**.

Las dos reutilizaban la misma variable `data_label`, que con `pre_path` vale
«residuos de `X.pre`». Correcta para la primera, **falsa para la segunda**.

## Lo irónico, y por qué importa

La etiqueta desmentía exactamente la razón por la que el número es correcto.
BUG-0013 cambió la fuente porque **los residuos de un modelo que ya lleva μ tienen
media cero por construcción**, así que medirlos aconsejaba `estimate_mu=False` en
series con deriva significativa.

Medido en los dos casos que lo destaparon:

| modelo | media de ∇ln y (lo que publica) | media de los residuos |
|---|---|---|
| `PGAS_m03` | +0,0146 | **+0,7015** |
| `ITCER_m02` | −0,0072 | **+0,000001** |

`ITCER_m02` es la demostración: su residuo tiene media cero **porque μ está
dentro del modelo**. Si el bloque midiera lo que su etiqueta decía, contestaría
«sin deriva» sobre una serie cuya deriva es significativa (t = −2,41).

## Fix

El bloque de la media tiene su propia etiqueta —`∇^d∇_s^D y(λ)`— y, cuando hay
`pre_path`, una nota que dice por qué no son los residuos y remite a BUG-0013.

La etiqueta de la identificación ARMA **no se toca**: ahí «residuos de `X.pre`»
es cierto. El test lo fija en las dos direcciones, porque pasarse de frenada
habría sido el error simétrico.

Sin `pre_path` no se añade nada: no hay confusión posible que aclarar.

## La familia

Es el noveno de la sesión con la misma forma: **el contenido correcto existía y
la presentación lo contradecía**. Aquí ni siquiera había un número discutible —
la cifra llevaba bien desde BUG-0013— sólo un rótulo heredado de otro bloque.
