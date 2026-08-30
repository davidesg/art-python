---
id: BUG-0059
title: el Box-Cox imprimía el módulo de la correlación media-dispersión y perdía el signo — con lo que el caso más informativo, dos escalas de signo opuesto que acorralan la λ correcta, se presentaba como «decisión ambigua, ambas razonables»
status: fixed
severity: medium
component: describe
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-29
reporter: carril Claude del RUN 3 — defecto (3) de su informe
tags:
  - boxcox
  - presentation
  - diagnosis
references:
  - src/art/describe.py (describe_boxcox)
  - bugs/BUG-0040-the-domain-taxonomy-was-binary.md
  - tests/test_bug_0059_boxcox_conserva_el_signo.py
  - bugs/BUG-0059-repro/repro.py
---

## Summary

`_abscorr` devolvía `abs(corrcoef(medias, desviaciones))`, así que el signo se
perdía antes de imprimirse.

El **módulo es el criterio correcto para decidir**: se elige la escala cuya
dependencia media-dispersión está más cerca de cero. Eso no cambia. Pero el
**signo es el diagnóstico**, y dice cosas opuestas:

| | lectura |
|---|---|
| `corr > 0` | la dispersión CRECE con el nivel → la transformación **se queda corta** |
| `corr < 0` | la dispersión CAE con el nivel → la transformación **se pasa** |

Sobretransformación e infratransformación piden correcciones contrarias, y en
valor absoluto son indistinguibles.

## El caso que lo hace importar

Sobre PGAS:

```
λ=1 (original): +0.150   la dispersión CRECE con el nivel → se queda corta
λ=0 (log):      −0.173   la dispersión CAE con el nivel   → se pasa
```

**Los signos son opuestos: la λ correcta está entre las dos.** Una escala se
queda corta y la otra se pasa, así que ninguna de las dos anula la dependencia y
elegir por el módulo más pequeño (0.150 < 0.173, luego λ=1) es arbitrario.

Impreso en valor absoluto, eso salía como *«0.150 frente a 0.173, Δ=0.024 < 0.10,
decisión ambigua, ambas transformaciones son razonables»*. Es falso: **ninguna de
las dos lo es**, y el mensaje de ambigüedad invitaba a quedarse con la que el
módulo favorecía marginalmente — que es λ=1, la que produjo el desastre de PGAS
en el RUN 1 del carril DS (σ̂ₐ=2067, AIC 1511, JB p=0.002, dos residuos extremos).

Ese caso lo cerró BUG-0040 por la vía del dominio. Este arreglo hace que **el
propio estadístico lo diga** en vez de callarlo.

## Fix

* Se imprimen las dos correlaciones **con signo** y con su lectura al lado.
* Cuando los signos son opuestos (y los dos módulos superan 0.05) se nombra la
  **horquilla**: la λ correcta está entre 0 y 1, ninguna de las dos ofrecidas la
  alcanza, y la decisión no la cierra este estadístico sino el DOMINIO de la
  serie — con el porqué, que un modelo en niveles no tiene escala interpretable.
* El `.data` gana `corr_raw_signed`, `corr_log_signed` y `horquilla`. **`corr_raw`,
  `corr_log` y `gap` no cambian**: siguen en módulo, así que `policy.decide_lambda`
  no se ve afectada. El test lo fija.

Sin horquilla no se imprime nada extra.

## Lo que este arreglo NO hace

No amplía el conjunto de λ ofrecidas. La suite trabaja con λ ∈ {0, 1}, así que
cuando la horquilla aparece la respuesta correcta —una λ intermedia, o la logit
para un cociente acotado— **no está disponible**. Lo honesto es decirlo, que es lo
que hace ahora, en vez de presentar la elección forzada como si el estadístico la
respaldara.
