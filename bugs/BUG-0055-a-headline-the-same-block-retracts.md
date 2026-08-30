---
id: BUG-0055
title: el DCD de sobrediferenciación titulaba «considerar d+1» y tres párrafos más abajo el mismo bloque explicaba que ese lado no da veredicto sobre d
status: fixed
severity: medium
component: describe
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-29
reporter: carril Claude del RUN 2 — defecto (h) de su informe
tags:
  - presentation
  - integration-order
  - formal-tests
references:
  - src/art/describe.py (describe_formal_tests — DCD sobre-diferenciación)
  - tests/test_bug_0054_0055_avisos_legibles.py
  - bugs/BUG-0055-repro/repro.py
---

## Summary

El bloque imprimía, en negrita:

```
→ testigo invertible → raíz unitaria regular genuina → considerar d+1 ✗
```

y a continuación, en el mismo bloque:

* *«El crítico correcto ahí es mayor, así que un LR apenas por encima del impreso
  **NO es evidencia de d+1**»* (deterministas resonantes en f=0);
* *«**Sin par confirmatorio.** El veredicto de arriba es UN SOLO lado, y los
  contrastes de frontera se leen en pareja»*;

y el contraste siguiente remataba con *«d confirmado por abajo ✓»*.

**El contenido correcto estaba entero.** Lo que fallaba era la jerarquía visual:
un titular invita a leer sólo el titular, y quien lo hace se va a `d=2` sin
motivo. No es hipotético — **pasó en esta réplica**: se adoptó un `d=2` sobre
RATIO que hubo que retractar, con el aviso impreso unas líneas más abajo.

## Fix

Las salvedades se calculan **antes** que el veredicto y el titular las lleva
dentro:

```
→ testigo invertible → **este lado, POR SÍ SOLO, apuntaría a d+1 — pero NO es
  concluyente**: el crítico impreso está SUBESTIMADO (deterministas resonantes
  en f=0) y falta el lado AR del par. Lee los avisos de abajo ANTES de mover `d`
```

Y cuando no hay salvedades, el titular sigue sin afirmar de más: *«este lado
apunta a d+1 (⚠ un solo lado: confírmalo con el par en f=0, más abajo)»*. El
contraste de frontera se lee en pareja siempre, así que el titular de uno solo
nunca es una conclusión.

## La clase de defecto

No hay ningún estadístico mal calculado. Hay un **orden de lectura** que
contradice al contenido: lo que se afirma arriba se retira abajo, y arriba está
en negrita. Vale la pena revisarlo en el resto de bloques con la misma pregunta:
*¿puede este titular leerse solo sin engañar?* Un veredicto que necesita tres
párrafos de matices no es un veredicto — o los matices suben al titular, o el
titular baja de tono.
