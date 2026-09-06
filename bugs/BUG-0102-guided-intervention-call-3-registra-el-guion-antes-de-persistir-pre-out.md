---
id: BUG-0102
title: guided_intervention Call 3 registra el guion antes de persistir .pre/.out — el guion niega artefactos que sí se escriben
status: open
severity: medium
component: guion
found_in: 0.2.0.dev0
fixed_in:
reported: 2026-09-06
reporter: DeepSeek — sesión UEM_FOOD_SERV_DS, análisis univariante HICP Services
tags: [guion, guided_intervention, terna, orden-de-persistencia, silencioso]
references:
  - src/art/mcp_server.py:6996 (guided_intervention Call 3 — _record_to_guion)
  - src/art/mcp_server.py:7015-7022 (write_pre / write_out, DESPUÉS del registro)
  - src/art/mcp_server.py:5189-5233 (confirm_and_estimate — persiste primero, registra después; patrón correcto)
  - src/art/mcp_server.py:4928-4951 (_record_to_guion — comprueba la terna y decide out_path / «sin .pre, .out»)
  - BUG-0088 / BUG-0092 (familia: guion desincronizado con la terna)
---

## Summary

En la **Call 3** de `guided_intervention` (la que construye, estima y verifica la
intervención), `_record_to_guion(...)` se llama **antes** de `write_pre`/`write_out`.
La comprobación de la terna dentro de `_record_to_guion` mira si `.pre` y `.out`
existen en ese momento —y no existen, porque se escriben unas líneas más abajo—,
así que la entrada del guion queda con `out_path: null` y el aviso
*«(sin .pre, .out; se rehacen estimando el .inp)»*, **aunque el `.pre` y el `.out`
sí acaban en disco un instante después**.

`confirm_and_estimate` hace lo contrario —persiste primero, registra después—, que
es el patrón correcto y el que la propia comprobación de la terna (BUG-0092)
asume. `guided_intervention` Call 3 se quedó con el orden invertido.

## Impact

El guion —el mapa por el que se vuelve atrás— niega los artefactos del paso de
intervención que sí existen. Consecuencia concreta en la sesión UEM_FOOD_SERV_DS:
la entrada `m04_step1115` (step 11/2015) quedó con `out_path: null` y la nota de
terna incompleta; al reanudar la identificación ARMA, el analista encadenó desde
`m02_AR1s.pre` en vez de desde `m04_step1115.pre` (que el guion daba por
inexistente), y **se descartó la intervención 11/2015 de la rama AR**. El defecto
no es solo cosmético: dirige el encadenado hacia una base más antigua.

## Reproduction

1. Sobre un `.inp` con residuos extremos, recorrer el nodo:
   `guided_intervention(inp)` (Call 1) → `guided_intervention(inp, date=…)`
   (Call 2) → `guided_intervention(inp, date=…, form="step", n_omega=1,
   output_path=<nuevo.inp>)` (Call 3).
2. Mirar la entrada del guion del paso 3:
   - `out_path` es `null`;
   - el aviso dice *«sin .pre, .out»*;
   - pero `ls <nuevo>.pre <nuevo>.out` devuelve ambos ficheros.

En la sesión real, `SERV_UEM_m04_step1115.pre` y `.out` existen en
`services/work/`, y la entrada v5 del guion los da por ausentes.

## Root cause

`src/art/mcp_server.py`, `guided_intervention`, rama Call 3:

```python
# línea ~6996: se registra ANTES de persistir
guion_note = _record_to_guion(model=m_fit, inp_path=output_path, ...)

# líneas ~7015-7022: la terna se persiste DESPUÉS
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

Mover la llamada a `_record_to_guion` en la Call 3 a **después** de
`write_pre`/`write_out`, reflejando el orden de `confirm_and_estimate`. El
registro debe ver los tres ficheros ya en disco para que la comprobación de la
terna (BUG-0092) funcione como está diseñada.

Observación secundaria del mismo bloque: la Call 3 pasa
`base_pre_path=inp_path` (el `.inp` fuente), mientras `confirm_and_estimate` pasa
el `.pre`. Eso hace que `infer_parent`/`base_pre_path` del paso de intervención
apunte a un `.inp` en vez de a un `.pre`, y que el encadenado desde el paso
correcto sea menos obvio. Si se toca el orden, conviene revisar de paso qué base
se registra.

## Validation

Tras `guided_intervention(..., form="step", output_path=<nuevo.inp>)`, la entrada
del guion debe tener `out_path = <nuevo>.out` resuelto, sin el aviso
*«sin .pre, .out»*, y `base_pre_path` coherente con la base real usada. Un repro
determinista (estilo `bugs/BUG-0102-repro/`) debe comprobar que los tres ficheros
existen Y que el guion los refleja, no solo que existan.
