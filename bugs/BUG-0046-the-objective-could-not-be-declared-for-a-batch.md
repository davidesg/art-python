---
id: BUG-0046
title: el objetivo del modelo no era declarable en el lote — batch_build, la entrada que se usa para preparar las series de un sistema, era la única que no podía decir que van a un sistema
status: fixed
severity: medium
component: mcp-server
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-28
reporter: David / réplica TFM Bolivia
tags:
  - objetivo
  - seasonality
  - integration-order
  - batch
references:
  - src/art/mcp_server.py (_INSTRUCTIONS — PREGUNTA INICIAL OBLIGATORIA; batch_build)
  - src/art/policy.py (decide_seasonal_route)
  - tests/test_bug_0046_objetivo_en_el_lote.py
  - bugs/BUG-0046-repro/repro.py
---

## Summary

`run_full` acepta `objetivo` y lo usa para adjudicar la ruta estacional: en
`"multivariante"` **veta la ruta B2 (D=1)**, de modo que todas las series lleven
el mismo tratamiento estacional y sus órdenes de integración sean comparables.

El mecanismo funcionaba. Lo que fallaba era **llegar a él**:

1. **`batch_build` no tenía el parámetro.** Su firma era
   `batch_build(inp_paths, output_dir, max_rounds=5, run_meg=False)` y llamaba
   `run_full(ts, out_inp, max_rounds=max_rounds)`, siempre con el defecto. La
   entrada del **lote** —que es justamente como se preparan las series de un
   sistema— era la única que no podía declarar que van a un sistema.

2. **Nadie preguntaba.** La PREGUNTA INICIAL OBLIGATORIA sólo ofrecía
   guiado/autónomo. Elegido el autónomo, el objetivo se quedaba en
   `"univariante"` en silencio.

3. **El lote no avisaba de la consecuencia.** Series con D distinta salían del
   batch sin una palabra: cada una había ganado por su propio ajuste, que es lo
   correcto para uso univariante y deja el lote inservible para un sistema.

## Por qué importa, con un caso real

Le pasó a esta réplica. RATIO, en el carril autónomo y con el defecto
univariante, se fue a las dos frecuencias estocásticas y dio un modelo
univariante mejor (AIC 458 frente a 488). Al llegar a la fase C hubo que
**descartarlo** y rehacerlo en forma B1, porque sus órdenes de integración no
eran comparables con los de PGAS e ITCER. El trabajo se hizo dos veces por una
pregunta que nadie hizo.

## Repro

```
$ python bugs/BUG-0046-repro/repro.py

  serie   univariante   multivariante
  ------------------------------------
  ESTOC     D=1           D=0
  DETER     D=0           D=0

  univariante   → D en [0, 1]  ← NO comparables
  multivariante → D en [0]  ← un solo tratamiento
```

Dos series sintéticas: una con raíz unitaria estacional (el patrón evoluciona) y
otra con un armónico fijo. Cada una elige bien **por separado**; el lote no se
puede montar.

## Fix

* `batch_build` acepta `objetivo` y lo reenvía a `run_full`.
* La PREGUNTA INICIAL OBLIGATORIA gana una segunda parte, **sólo en autónomo**,
  con un renglón de sesgo por opción y nada más — el desarrollo largo ya lo
  entrega `_nota_objetivo` en el nodo estacional, que es cuando la decisión se
  toma.
* El resumen del lote **declara** el objetivo, y marca «por defecto — nadie lo
  declaró» cuando nadie lo eligió: un defecto silencioso no se puede discutir.
* Si las series del lote **no comparten D** y el objetivo no es multivariante,
  se avisa con la consecuencia concreta y el remedio.

### Sobre el momento de preguntar

Las instrucciones dicen, para d/D, que **no** se pregunte antes de ver la
ACF/PACF: «una pregunta sobre estacionalidad al abrir el análisis pide una
decisión sobre algo que todavía no existe». Ésta no es esa pregunta y no hay
contradicción que arreglar: **no es sobre los datos —que aún no se han visto—
sino sobre el uso, que el analista ya sabe.** Queda escrito en las instrucciones
para que una lectura futura no «arregle» la aparente contradicción.

En **guiado** no se pregunta en la apertura: allí va en la LLAMADA 3, con la
estacionalidad ya a la vista.

## Lo que el arreglo NO hace

El autónomo sigue sin poder **detenerse** a media corrida. Lo ideal sería que
preguntara al detectar estacionalidad —el momento en que la pregunta muerde—,
pero eso exige que el pipeline se suspenda y se reanude, que es un cambio de
forma. Queda anotado.
