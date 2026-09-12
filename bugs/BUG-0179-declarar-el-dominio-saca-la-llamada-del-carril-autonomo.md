---
id: BUG-0179
title: Declarar `domain` saca la llamada del carril AUTÓNOMO — la salida toma forma de turno guiado, termina en ⏸ y el asistente deja de iterar y pregunta
status: fixed
severity: high
component: pipeline
found_in: 0.2.0.dev0
fixed_in: 0.2.1
reported: 2026-09-12
reporter: David — run 4 automático de IPC_ES, observado en vivo
tags:
  - autonomo
  - carriles
  - regresion
references:
  - BUG-0015
  - BUG-0094
  - BUG-0178
---

## Summary

En `build_model`, el carril lo decide una línea:

```python
if domain:  overrides["domain"] = domain
guided = bool(overrides)
```

`domain` **no es una decisión de especificación**: es un dato sobre qué clase de
serie es ésta. El propio docstring de la herramienta lo dice al enumerar lo que
dispara el carril guiado —`lam`, `d`, `D`, `p`, `q`, `n_harmonics`,
`estimate_mu`, `decision`— y `domain` no está en esa lista.

Pero iba en el mismo diccionario. Declararlo volvía «guiada» la llamada, la
salida tomaba la forma del turno guiado y terminaba en `FIN_DE_TURNO_GUIADO`:

    ⏸ **Tu decisión.** No sigo hasta que me digas.

El asistente lee la marca —tiene instrucción explícita de no escribir nada
después de ella— para, y pregunta. **El carril autónomo deja de ser autónomo.**

## Reproduction

Misma serie, mismo código, lo único que cambia es `domain`:

    build_model(...)                          → «· autónomo»                  ⏸ no
    build_model(..., domain="price_index")    → «· guiado (spec confirmada)»  ⏸ SÍ

## Es una regresión, y tiene fecha

La bifurcación es vieja: `domain` entra en `overrides` desde **12-ago**
(`f8ee98e`). Durante tres semanas no pasó nada, porque la salida de
`build_model` no tenía forma de turno.

Lo que la activó fue **06-sep**, `9cc69fe` — la revisión de arquitectura, que
unificó la salida en `envuelve_iteracion`. Medido sobre los dos árboles:

    build_model ANTES de 9cc69fe   →  0 apariciones de ⏸
    build_model DESPUÉS            →  pasa por envuelve_iteracion, que lo emite

Un cambio correcto —dar la misma forma a todas las iteraciones, BUG-0094— hizo
visible una bifurcación equivocada que llevaba semanas dormida. Por eso las
corridas automáticas anteriores en la misma carpeta, con dos LLM distintos, se
comportaban bien: **son de antes del 6 de septiembre.**

## Impact

Un run desatendido se queda esperando una decisión que nadie va a dar. Y uno
atendido tampoco es comparable: lo que corre no es el carril autónomo, es el
guiado disfrazado — que es justo lo que el ejercicio guiado/auto existe para
comparar.

*Una puerta queda cerrada a su uso normal.* Entra, y el analista lo pide
explícitamente para 0.2.1: «el modo automático funcional debe ir en 0.2.1».

## Fix

Separar la decisión del dato. `overrides` se cierra con las decisiones de
especificación, se calcula `guided` **ahí**, y el dominio entra después:

```python
guided = bool(overrides)          # sólo DECISIONES
dom_decl = dominio_declarado(domain)   # BUG-0178
if dom_decl: overrides["domain"] = dom_decl
decision_policy = policy.ClaudePolicy(**overrides) if overrides else None
```

La política sigue recibiendo el dominio —declarado gana a inferido, que es lo
que BUG-0080 arregló y no se toca—; lo que ya no hace es cambiar el carril.

Nótese `if overrides` y no `if guided` en la última línea: con sólo el dominio
declarado hay que construir la política igualmente, o el dato se perdería. Ese
es el error fácil al arreglar esto.

## Validation

`tests/test_bugs_0178_0179_el_carril_autonomo.py`:

- sin nada declarado: «· autónomo» y **sin ⏸** — un autónomo que para no es
  autónomo;
- con `domain="price_index"`: sigue siendo autónomo y sigue sin ⏸;
- con `d=1` —una DECISIÓN— vuelve a ser guiado y sí termina en ⏸: lo contrario
  tiene que seguir valiendo;
- y el dominio declarado **sigue llegando a la política**: λ sale log. No basta
  con no cambiar de carril; el dato tiene que aplicarse.
