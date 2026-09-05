---
id: BUG-0101
title: El guion no sabe que está incompleto, y la iteración no existe como entidad contable
status: fixed
severity: high
component: guion
found_in: 0.1.12
fixed_in: 0.2.0
reported: 2026-09-06
reporter: David / revisión de arquitectura, hallazgo #5 — destapado por el caso UEM_FOOD_SERV_DS
tags:
  - guion
  - iteracion
  - registro
  - reconciliacion
references:
  - src/art/guion.py (Iteracion, iteraciones, numera_iteraciones, modelos_sin_registrar)
  - src/art/mcp_server.py (guion_map: cuenta y reconciliación; envuelve_iteracion en meg_reformulate y record_version)
  - bugs/BUG-0101-repro/repro.py
  - tests/test_iteracion_como_entidad.py
---

## Summary

Dos defectos del mismo registro, y el segundo es el grave.

**(A) La iteración no era contable.** El método es iterativo y sus etapas están
dadas —especificación, estimación por MVENC, diagnosis, reformulación— pero el
guion registraba las etapas y no la vuelta. Sobre el mismo corpus, «¿cuántas
iteraciones tuvo este análisis?» tenía **tres respuestas defendibles**: 1.181 por
entrada, 565 por modelo, 616 por nodo. El código no elegía ninguna.

**(B) El registro no sabía que le faltaban modelos.** Un `.inp` con su `.out` es
un modelo estimado. Si lo escribió una herramienta que no registra —y hay más
herramientas que ESCRIBEN modelos que herramientas que los REGISTRAN— la
iteración ocurre entera fuera del guion y nada lo dice.

## El caso que lo destapó

`cases/UEM_FOOD_SERV_DS`, un análisis que **salió bien** y fue difícil.

    modelos con terna completa en disco     13
    modelos en el guion                      9

    19:04   m08_ar6.inp   ← y el guion se escribe por última vez a las 19:04
    19:15   m09_fact.inp
    19:28   m10_fact.inp
    21:06   m11_fact.inp

Dos horas de análisis sin una línea en el registro, más un hueco intermedio
(`m05_ep17`, 18:23). Y lo que falta no es relleno:

    m08_ar6   ℓ=41,565  k=21   AIC −41,13   BIC 29,75   ← último del guion
    m11_fact  ℓ=41,385  k=19   AIC −44,77   BIC 19,36   ← el FINAL, según NOTAS.md

**El registro se quedó con el subcampeón.** La factorización —dos parámetros
menos por 0,18 de verosimilitud, 10,4 puntos de BIC— es la sustancia del caso y
es justo el tramo que no está.

No era una excepción: sobre el corpus, **23 guiones tienen 59 modelos estimados
fuera del registro**.

## Fix

**(A)** `iteracion` y `nodo` como campos de `GuionEntry`, con la regla del
método: un MODELO estimado cierra una iteración y se lleva el número; los NODOS
que lo preceden son su etapa 1 y llevan ese mismo número. De ahí que un nodo
pueda contener varias iteraciones —medido: hasta 9— y una iteración no pueda
contener varios nodos. `Iteracion` es la entidad (número, nodo, especificación,
modelo, **semilla**, decisión, estado) y `iteraciones(guion)` la lista. Se estampa
al escribir y se DERIVA al leer para los guiones ya escritos, sin reescribir un
byte: el orden de las entradas ya llevaba la información.

Una respuesta y no tres: **656 iteraciones** en el corpus.

**(B)** `modelos_sin_registrar(guion, path)` compara el registro con su propia
carpeta —que el guion conoce desde BUG-0098— y `guion_map` lo dice. Se mira sólo
lo que tiene `.out`: un `.inp` sin estimar es una especificación escrita, no una
iteración.

Esto **no impide** que una herramienta escriba un modelo sin registrarlo. Lo hace
visible, que es lo que faltaba: a las 21:06 de aquel día habría avisado.

## De paso: el sobre, con el denominador bien

El informe decía «4 de 46 herramientas». El denominador está mal: 40 de las 46
son **instrumentos** —gráficos, barridos, contrastes— y ponerle una
«reformulación» a un ACF sería inventarla. Cierran una iteración las que
escriben en el guion, y son **seis**. Faltaban dos: `meg_reformulate` —que ES una
reformulación, la etapa 4 con nombre propio— y `record_version`. Ya son 6 de 6.
