---
id: BUG-0042
title: the state footer was a THIRD adequacy predicate — it reported "diagnosis limpia" and "etapa: contrastes formales" on models whose verdict was REVISAR and which formal_tests blocked
status: fixed
severity: medium
component: mcp-tools
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-28
reporter: David / réplica TFM Bolivia — hallado por el experimento del chat limpio
tags:
  - diagnosis
  - contradictory-output
  - incomplete-fix
references:
  - src/art/mcp_server.py (_state_footer)
  - bugs/BUG-0036-two-adequacy-verdicts-with-the-same-name.md
  - tests/test_bug_0042_state_footer_predicate.py
---

## Summary

BUG-0036 encontró **dos** predicados de adecuación con el mismo nombre y los
unificó: el que publica el veredicto (`DiagnosisResult.residuals_ok` / `.clean`)
y el de la guarda de `formal_tests`. Quedó un **tercero** sin tocar.

`_state_footer` construía su propia lista:

```python
q_ok  = not any(pv <= 0.05 for pv in (diag_result.q_pvalues or []))
jb_ok = diag_result.jb_pvalue > 0.05
n_ext = len(diag_result.extreme or [])
...
limpio = q_ok and jb_ok and not n_ext
```

Q, JB y extremos. **Ni la media residual ni la estacionalidad**, que sí están en
`.clean`.

## Lo que producía

Del experimento del chat limpio, con sus palabras:

> ITCER m05: «Veredicto: REVISAR ✗», media residual t=−2.17 — pero el pie dice
> «falta: nada — diagnosis limpia».
>
> RATIO m05: veredicto REVISAR ✗ por estacionalidad residual y pie «falta: nada
> — diagnosis limpia · etapa: contrastes formales». En este segundo caso
> `formal_tests` sí bloqueó por ese motivo, así que el pie es el que está mal.

El pie de estado existe para decirle a quien lee **dónde está y qué le falta**.
Diciendo que no falta nada sobre un modelo que el resto del sistema rechaza, hace
lo contrario de aquello para lo que se escribió.

## Fix

`limpio` se construye de los **mismos componentes que `.clean`**: ruido blanco,
normalidad, media centrada y ausencia de estacionalidad residual. Y `falta` los
nombra todos.

### Y una segunda incoherencia, del propio arreglo

Al unificarlo apareció otra: `limpio` excluye los extremos —correctamente, igual
que `residuals_ok`, porque una intervención arregla un residuo que se porta mal y
no una media que falta— pero la lista `falta` **sí** los incluía. Un modelo
limpio con un residuo grande salía diciendo a la vez «falta: 1 anómalo» y
«etapa: contrastes formales».

Los extremos pasan a una línea propia:

```
   falta   : nada — diagnosis limpia
   nota    : 1 anómalo (obs 9, z=+3.06)
   etapa   : contrastes formales — la diagnosis está limpia, es su etapa
```

Es la misma separación que BUG-0036 introdujo en `formal_tests` —fallos que
bloquean, avisos que se nombran— y ahora los tres sitios la comparten.

## La invariante que fija el test

`"nada — diagnosis limpia"` en el pie ⇔ `diag.clean`. Si divergen, el analista
recibe dos respuestas a una sola pregunta, que es el defecto entero.

## Nota

Es el segundo arreglo de esta serie que se queda corto por la misma razón
(BUG-0040 fue el otro: BUG-0015 añadió el dominio con dos categorías). Cuando un
concepto está triplicado en el código, unificar dos deja el tercero convertido en
la próxima sorpresa. Aquí, además, el tercero era el que más se lee.
