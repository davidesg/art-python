---
id: BUG-0102
title: suggest_intervention_form registra el guion antes de persistir .pre/.out — el guion niega artefactos que sí se escriben
status: open
severity: medium
component: guion
found_in: 0.2.0.dev0
fixed_in:
reported: 2026-09-06
reporter: DeepSeek — sesión UEM_FOOD_SERV_DS, análisis univariante HICP Services
tags: [guion, suggest_intervention_form, terna, orden-de-persistencia, silencioso]
references:
  - src/art/mcp_server.py:6996 (suggest_intervention_form — _record_to_guion, ANTES)
  - src/art/mcp_server.py:7017-7019 (write_pre / write_out, DESPUÉS del registro)
  - src/art/mcp_server.py:6477 (guided_intervention Call 3 delega en suggest_intervention_form)
  - src/art/mcp_server.py:5193-5220 (confirm_and_estimate — persiste primero, registra después; patrón correcto)
  - src/art/mcp_server.py:4928-4951 (_record_to_guion — comprueba la terna y decide out_path / «sin .pre, .out»)
  - BUG-0088 / BUG-0092 (familia: guion desincronizado con la terna)
---

## Summary

En `suggest_intervention_form` (el instrumento B3, al que `guided_intervention`
Call 3 delega la construcción de la intervención), `_record_to_guion(...)` se
llama **antes** de `write_pre`/`write_out`. La comprobación de la terna dentro de
`_record_to_guion` mira si `.pre` y `.out` existen en ese momento —y no existen,
porque se escriben unas líneas más abajo—, así que la entrada del guion queda con
`out_path: null` y el aviso *«(sin .pre, .out; se rehacen estimando el .inp)»*,
**aunque el `.pre` y el `.out` sí acaban en disco un instante después**.

`confirm_and_estimate` hace lo contrario —persiste primero, registra después—, que
es el patrón correcto y el que la propia comprobación de la terna (BUG-0092)
asume. `suggest_intervention_form` se quedó con el orden invertido.

## Impact

El guion —el mapa por el que se vuelve atrás— niega los artefactos del paso de
intervención que sí existen. Consecuencia concreta en la sesión UEM_FOOD_SERV_DS:
la entrada `m04_step1115` (step 11/2015) quedó con `out_path: null` y la nota de
terna incompleta; al reanudar la identificación ARMA, el analista encadenó desde
`m02_AR1s.pre` en vez de desde `m04_step1115.pre` (que el guion daba por
inexistente), y **se descartó la intervención 11/2015 de la rama AR**. El defecto
no es solo cosmético: dirige el encadenado hacia una base más antigua.

## Reproduction

`bugs/BUG-0102-repro/repro.py` — determinista, sin datos ni motor. Lee
`src/art/mcp_server.py` y compara los números de línea de las llamadas reales:

```
== A. suggest_intervention_form
  _record_to_guion  en línea 6996
  write_pre         en línea 7017
  write_out         en línea 7019
  → registra ANTES de persistir
== B. confirm_and_estimate
  write_pre         en línea 5193
  _record_to_guion  en línea 5220
  → persiste primero, registra después (patrón correcto)
FALLA (exit 1)
```

En la sesión real, `SERV_UEM_m04_step1115.pre` y `.out` existen en
`services/work/`, y la entrada v5 del guion los da por ausentes.

## Root cause

`src/art/mcp_server.py`, `suggest_intervention_form`:

```python
# línea ~6996: se registra ANTES de persistir
guion_note = _record_to_guion(model=m_fit, inp_path=output_path, ...)

# líneas ~7015-7019: la terna se persiste DESPUÉS
_base = os.path.splitext(output_path)[0]
new_pre_path = _base + ".pre"
new_out_path = _base + ".out"
m_fit.write_pre(new_pre_path)
m_fit.write_out(new_out_path)
```

`_record_to_guion` comprueba la existencia de la terna (`.inp`/`.pre`/`.out`) y,
como `write_pre`/`write_out` aún no han corrido, marca el `.out` como ausente
(`out_path` queda `null`) y emite el aviso de terna incompleta. El orden correcto
es el de `confirm_and_estimate`: persistir la terna y **después** registrar.

## Fix (propuesto)

Mover la llamada a `_record_to_guion` en `suggest_intervention_form` a **después**
de `write_pre`/`write_out`, reflejando el orden de `confirm_and_estimate`. El
registro debe ver los tres ficheros ya en disco para que la comprobación de la
terna (BUG-0092) funcione como está diseñada.

Observación secundaria del mismo bloque: `suggest_intervention_form` pasa
`base_pre_path=inp_path` (el `.inp` fuente), mientras `confirm_and_estimate` pasa
el `.pre`. Eso hace que `infer_parent`/`base_pre_path` del paso de intervención
apunte a un `.inp` en vez de a un `.pre`, y que el encadenado desde el paso
correcto sea menos obvio. Si se toca el orden, conviene revisar de paso qué base
se registra.

## Validation

Con el arreglo, `bugs/BUG-0102-repro/repro.py` debe salir 0: en
`suggest_intervention_form`, `write_pre`/`write_out` aparecen antes que
`_record_to_guion`, y la entrada del guion queda con `out_path` resuelto y sin el
aviso *«sin .pre, .out»*.
