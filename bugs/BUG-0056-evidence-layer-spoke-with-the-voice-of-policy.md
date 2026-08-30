---
id: BUG-0056
title: unit_root_analysis presentaba la evidencia cruda con voz de recomendación — «Usa d=2» — saltándose el tope de un paso que BUG-0016 y BUG-0023 pusieron en la capa de política, y los dos carriles del RUN 3 volvieron a evaluar d=2
status: fixed
severity: high
component: describe
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-29
reporter: David — observando el RUN 3 en marcha
tags:
  - integration-order
  - presentation
  - layering
references:
  - src/art/describe.py (describe_unit_root)
  - src/art/policy.py (decide_d)
  - bugs/BUG-0016-decide-d-jumps-to-2-ignoring-the-seasonality-it-already-detected.md
  - bugs/BUG-0023-the-one-step-cap-on-d-is-absolute-where-it-should-be-relative.md
  - tests/test_bug_0056_evidencia_y_politica.py
  - bugs/BUG-0056-repro/repro.py
---

## Summary

**El arreglo de BUG-0016/0023 no se deshizo. Se puede rodear.**

La separación es correcta y deliberada: `describe_unit_root` es la **capa de
evidencia** y `recommended_d` informa en crudo de lo que ADF y KPSS encuentran;
el tope de la escuela —un paso cada vez, y la estacionalidad acota `d`— vive en
`policy.decide_d`. Su docstring lo dice con todas las letras:

> *«The evidence layer is left alone on purpose — `recommended_d` keeps
> reporting what the tests found. This is a POLICY cap, so the table still shows
> that d=2 was suggested and the cap is visible rather than hidden inside the
> statistic.»*

Lo que fallaba es que **el texto de la capa de evidencia hablaba con voz de
política**:

```
**Recomendación**: d = 2 (primera diferencia con consenso).
→ La serie con d=2 diferencia(s) es estacionaria. Usa d=2.
```

«Recomendación» y «Usa d=2» son instrucciones. Un analista que llama a
`unit_root_analysis` directamente —y es una herramienta pública— se salta la capa
de política **sin enterarse de que existe**.

De paso, la etiqueta era literalmente falsa: *«d = 2 (**primera** diferencia con
consenso)»*.

## Cómo se detectó

Observando el RUN 3 en marcha: **los dos carriles volvieron a evaluar d=2 con ADF
desde d=0**, el mismo salto que dos bugs habían arreglado. El contador de
llamadas descartó que se lo calcularan ellos —los dos habían llamado a
`unit_root_analysis`— y el diagnóstico quedó en la herramienta.

Sobre RATIO:

```
| d | Serie |   ADF p | ADF |  KPSS p | KPSS | Veredicto      |
| 0 | ln    |  0.8136 |  ✗  |  0.0100 |  ✗   | raíz unitaria  |
| 1 | ∇ln   |  0.1375 |  ✗  |  0.1000 |  ✓   | ambiguo ⚠      |
| 2 | ∇²ln  |  0.0002 |  ✓  |  0.1000 |  ✓   | estacionaria ✓ |
```

Recomendaba **d=2, saltándose el d=1 ambiguo entero**. Y RATIO es justamente una
serie estacional, que es el caso en que el ADF —cuya regresión no lleva términos
estacionales— sesga hacia no rechazar.

## Fix

El `.data` sigue crudo (`recommended_d`), y se añade `recommended_d_policy` para
quien lo quiera. Lo que cambia es la **presentación**: el titular pasa a ser «Lo
que encuentran los contrastes», y cuando evidencia y política difieren se imprime
el punto de partida con sus tres razones —el paso, la estacionalidad sin
contrastar, y que esto es especificación inicial cuyo contraste real llega al
final con `formal_tests`.

Cuando coinciden no se imprime nada extra: el aviso sólo aparece donde hay algo
que advertir.

## La lección de arquitectura

Un arreglo que vive en una capa **no protege a quien entra por otra**. Separar
evidencia de política fue la decisión correcta y sigue siéndolo; lo que faltaba
es que la capa de evidencia **hable como evidencia**. En cuanto dice
«Recomendación» y «Usa», está ejerciendo de política sin las salvaguardas de la
política.

Es la misma familia que BUG-0055: el contenido correcto existía, y la forma de
presentarlo lo contradecía.
