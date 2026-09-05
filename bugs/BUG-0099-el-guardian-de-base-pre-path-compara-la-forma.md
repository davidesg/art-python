---
id: BUG-0099
title: El guardián de base_pre_path compara la forma (nobs, freq) y no el contenido — se puede encadenar el .pre de otra serie
status: fixed
severity: high
component: mcp-tools
found_in: 0.1.12
fixed_in: 0.2.0
reported: 2026-09-05
reporter: David / revisión de arquitectura con contexto limpio, hallazgo #9 — medido 2026-09-05
tags:
  - base_pre_path
  - encadenado
  - guardian
  - silencioso
references:
  - src/art/mcp_server.py (_exige_la_misma_serie; antes, la comparación nobs/freq en confirm_and_estimate)
  - bugs/BUG-0099-repro/repro.py
  - tests/test_encadenado_misma_serie.py
---

## Summary

`confirm_and_estimate(..., base_pre_path=…)` es **el camino recomendado** por las
propias instrucciones: encadenar desde el `.pre` conserva armónicos, media e
intervenciones ya estimados y añade sólo el ARMA. Su guardián comprobaba que las
dos series tuviesen el mismo `nobs` y la misma `freq` — es decir, la FORMA — y no
que fuesen la misma serie.

Dos series mensuales de la misma longitud pasan. **En el propio TFM hay tres.**

Lo que ocurre después no avisa de nada: `_build_arma_on_model` se queda con los
deterministas del `.pre` —armónicos, media, intervenciones **con sus fechas**— y
`_write_inp` escribe los datos del `.inp`. Sale un modelo cuya parte determinista
es de otra serie, estimado sobre ésta, y registrado en el guion como el paso
siguiente del recorrido de ésta.

## Medición

Dos series sintéticas de 120 datos mensuales, mismo arranque:

    guardián viejo (nobs, freq)                    PASA
    max|A − serie del .pre de B|                  152,3
    encadenado legítimo, max|A − .pre de A|      5·10⁻⁷

El margen es de ocho órdenes de magnitud, así que la tolerancia no hay que
afinarla: 5·10⁻⁷ no es ruido, es la precisión con la que el `.inp` escribe la
serie.

## Fix

`_exige_la_misma_serie(ts, ts_base, ruta, ruta_base)`, con tres comprobaciones:

  - `nobs`/`freq` — lo que ya había;
  - `start` — dos series de igual longitud y frecuencia que empiezan en fechas
    distintas están desalineadas, y las fechas de las intervenciones del `.pre`,
    que son índices, apuntarían a otro periodo;
  - **los datos**, en relativo (umbral 1e-5, frente al 5·10⁻⁷ del caso legítimo),
    diciendo en qué dato divergen y por cuánto.

En relativo y no en absoluto porque la tolerancia tiene que valer igual para una
serie en unidades y para otra en millones.

## Estado antes del arreglo

Trampa armada, no herida: no consta ningún encadenado cruzado en el corpus. Pero
el camino que lo permite es el que las instrucciones mandan usar por defecto, y
el fallo es silencioso — no habría forma de notarlo salvo releyendo el `.inp`.
