---
id: BUG-0180
title: El carril AUTÓNOMO que el estudio validó —el LLM hace de analista y decide cada nodo— nunca pasó al protocolo; art mandaba el autónomo a `build_model`, y sin enunciado el «autónomo» era un auto-ARIMA con paradas del guiado
status: fixed
severity: critical
component: protocolo
found_in: 0.1.0
fixed_in: 0.2.1
reported: 2026-09-12
reporter: David — run 5 de IPC_ES, autónomo sin enunciado
tags:
  - autonomo
  - carriles
  - diseño
  - protocolo
references:
  - BUG-0110
  - BUG-0179
  - BUG-0181
---

## Summary

El modo autónomo de art tiene que ser **el LLM haciendo de analista**: recorre los
mismos nodos que el guiado y decide cada uno, con su razón por escrito. Así se
diseñó y así se midió, con varios LLM, en la réplica del TFM y en SF_MEG.

**Pero ese diseño nunca llegó al protocolo.** El protocolo de art decía —en 0.1.12
y en 0.2.1, sin cambio—:

> *«Si el usuario elige autónomo → usa build_model o batch_build.»*
> *«Autónomo: build_model(inp, out) sin spec → la heurística decide todo.»*

Las reglas que convertían al LLM en analista vivían **en el enunciado de cada
ejercicio**. Encontrados ocho —réplica run2, run3, run4, chat limpio, SF_MEG—, los
ocho empiezan igual: *«Eres el analista. […] decidiendo tú solo cada nodo. […] Eso
NO significa ir rápido»*. Cada run determinaba su carril por su enunciado; art no.

Es un error de **diseño**, no de código: el estudio se hizo, se evaluó con rúbrica
y prerregistro, y no se consolidó.

## Lo que se mide

Quién decide los nodos, en cada guion:

    0.1.x AUTÓNOMO  SF_MEG sfmeg/                8 series   LLM: 70
    0.1.x AUTÓNOMO  SF_MEG sfmeg_run2/           8 series   LLM: 84
    0.1.x AUTÓNOMO  SF_MEG realizaciones/r1      6 series   LLM: 54
    0.1.x AUTÓNOMO  réplica TFM run2-4           9 series   LLM: 75
    0.1.x GUIADO    SF_MEG realizaciones/r2,r3  12 series   analista+LLM: 104
    0.2.1 AUTÓNOMO  run5                         1 serie    heurística: 5 · analista+LLM: 1
    0.2.1 AUTÓNOMO  run4/auto                    1 serie    analista+LLM: 7 · heurística: 5

**283 nodos en 31 series decididos por el LLM en 0.1.x; ninguno en 0.2.1.** En los
autónomos de hoy decide la heurística, o el LLM sigue firmando con la etiqueta del
guiado.

## Reproduction

**run5** — autónomo sin enunciado, sólo con el protocolo. Transcripción:

    build_model(...)               ← «· autónomo»    5 s, diagnosis limpia en la ronda 1
       🤖 «El modelo quedó identificado, estimado y pasa la diagnosis…»

Una llamada y cerrado. Sin sobreparametrización, sin Semana Santa, sin contrastes
formales, sin MEG. El LLM hizo exactamente lo que el protocolo le decía que era el
autónomo. El guion lo registra: 4 modelos, cinco nodos firmados por `heurística`.

Frente a esto, el guiado de run4 sobre la misma serie: 19 modelos, AR(2) y
ARMA(1,1) rechazados por sobreparametrización, Semana Santa con t=2,9, MEG sobre
f=3 y f=5, verificación del óptimo en frío.

## Por qué es lo peor de los dos mundos

Palabras del analista: *«Si no es un modo híbrido entre el modo guiado y el
pmdarima. Es decir el peor de los mundos.»*

Sin enunciado, el autónomo de 0.2.1 era:

- **un auto-ARIMA** para decidir (`build_model`: la heurística elige λ, d, D, p, q
  y para en cuanto la diagnosis sale limpia), y
- **las paradas del guiado** en cuanto el LLM intentaba seguir: cada estimación
  terminaba en ⏸ y le ordenaba esperar (BUG-0181).

No tiene ni el juicio del analista ni la continuidad de un pipeline.

## Root cause

Dos piezas del estudio nunca llegaron a art:

1. **La definición del carril.** El protocolo enrutaba el autónomo a `build_model`,
   y la sección de construcción del modelo lo describía como «el MISMO motor en
   ambos modos». Nada decía que en autónomo el LLM ocupa la silla del analista.
2. **Las reglas que el estudio validó.** La más clara, en
   `replica/evaluacion_run4/RESULTADOS_RUN4.md`: los nodos decididos en lote
   cayeron **de 8 a 0**, y la conclusión escrita fue *«Bastó escribirla. La opción
   de que ART lo vigilara […] se puede cerrar sin implementar.»* Se escribió en el
   enunciado, se midió que funcionaba, y ahí se quedó.

La superficie de herramientas, por su parte, sí conocía el carril:
`guion_node(decidido_por=…)` documenta `"LLM" (autonomous)`. Herramienta y
protocolo describían dos autónomos distintos.

## Fix

**El protocolo, consolidado desde el enunciado mejor puntuado** (réplica run4,
claude 11/13):

- La pregunta inicial define los dos carriles por **quién decide**: en GUIADO el
  usuario; en AUTÓNOMO «yo hago de analista: recorro el mismo protocolo, decido
  cada nodo con su razón por escrito».
- El autónomo se enruta a una sección nueva, **EL CARRIL AUTÓNOMO — TÚ ERES EL
  ANALISTA**: los diez nodos en orden y uno por vez, la regla de los nodos en lote
  con su medición, el carril declarado en cada llamada (`modo="autonomo"`,
  BUG-0181), las reglas del estudio —la recomendación es evidencia; un empate se
  resuelve estimando; un contraste sobre un modelo inadecuado no es un contraste;
  los anómalos se calibran—, y la documentación obligatoria: `guion_node(…,
  decidido_por="LLM")` tras cada nodo y `guion_abandon(why=…)` en cada rama
  descartada.
- **«AUTÓNOMO NO ES build_model»**, dicho en el enrutado. `build_model` pasa a
  describirse como lo que es: un atajo heurístico de una llamada, para cuando el
  usuario pida un ajuste automático sin análisis.
- Las reglas que sólo valen en guiado lo dicen: «En GUIADO, NUNCA encadenes pasos
  sin…», «En GUIADO las decisiones son del USUARIO».

Lo que es de cada ejercicio —las series, la lista blanca de lectura, dónde
escribir, el objetivo— **sigue en su enunciado**. Lo que es del método pasa a art.

**Coste:** el protocolo pasa de 39.190 a 43.834 caracteres (+11,8 %), en un texto
que viaja en cada llamada. Se asume a cambio de que el carril exista sin
enunciado; y es un argumento más para el troceo por etapas anotado para 0.3.

## Validation

`tests/test_bugs_0180_0181_el_autonomo_es_el_analista.py`:

- el enrutado ya no manda el autónomo a `build_model` y dice que no lo es;
- la sección existe, recorre los nueve nodos nombrados, y lleva las reglas del
  estudio: nodos en lote, `decidido_por="LLM"`, `modo="autonomo"`, empates,
  `guion_abandon`;
- `guion_node` y el protocolo describen el mismo carril;
- `build_model` se presenta como atajo;
- «no encadenes pasos» y «decide el usuario» están acotadas al guiado.

La prueba de verdad no es un test: es repetir run5 **sin enunciado** y ver el
recorrido en el guion. Es la prueba i) del camino al push.
