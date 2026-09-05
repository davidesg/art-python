---
id: BUG-0100
title: Tres nombres y DOS recuentos distintos para los armónicos, y el tope se aplicaba con un min mudo
status: fixed
severity: medium
component: pipeline
found_in: 0.1.12
fixed_in: 0.2.0
reported: 2026-09-05
reporter: David / revisión de arquitectura con contexto limpio, hallazgo #7 — medido 2026-09-05
tags:
  - armonicos
  - nomenclatura
  - silencioso
  - nyquist
references:
  - src/art/pipeline.py (maximo_de_armonicos, tope_de_armonicos; antes el `min` mudo)
  - src/art/seasonal_detection.py (n_terminos_estacionales, antes num_harmonics)
  - src/art/mcp_server.py (n_terminos_arm, antes n_arm)
  - tests/test_cuenta_de_armonicos.py
---

## Summary

El mismo concepto se llamaba de tres maneras, y las tres no contaban lo mismo:

| módulo                 | nombre          | qué cuenta                        | mensual |
|------------------------|-----------------|-----------------------------------|---------|
| `pipeline` (28 usos)   | `n_harmonics`   | **pares** cos/sin, tope freq//2−1 | 5       |
| `seasonal_detection`(8)| `num_harmonics` | **términos** (freq−1)             | 11      |
| `mcp_server` (4)       | `n_arm`         | términos cos/sin/**alter**        | 11      |

El armónico de Nyquist —el `alter`, que es un término suelto y no un par— cae
dentro de dos recuentos y fuera del tercero. `num_harmonics` y `n_harmonics`
están además a un carácter de distancia.

**Y el tope era mudo.** `pipeline` hacía

    _n_harm = min(n_harmonics, max(freq // 2 - 1, 0))

así que un bloque que dice «11 armónicos», leído por un analista o un LLM y
pasado como `n_harmonics=11`, producía un modelo de 5 pares **sin decirlo**: un
modelo distinto del pedido, registrado como si fuera el pedido.

## Medición

Sobre el corpus (612 entradas con `n_harmonics`):

    {0: 266, 1: 88, 2: 18, 3: 36, 4: 37, 5: 167}
    por encima del tope mensual (5): 0

**No había ocurrido nunca.** Trampa armada, no herida — y conviene decirlo así.

## Fix

  - `pipeline.maximo_de_armonicos(freq)` y `tope_de_armonicos(n, freq, avisa=)`,
    con el convenio escrito en un solo sitio: `n_harmonics` son PARES y el
    Nyquist va aparte. El recorte avisa con `RuntimeWarning` y traduce la cifra:
    *«si los 11 vienen de un bloque que cuenta TÉRMINOS, el equivalente en pares
    es 5»*.
  - `seasonal_detection`: `num_harmonics` → `n_terminos_estacionales`. Ahí es lo
    correcto —son los grados de libertad del contraste F—, pero tiene que
    llamarse distinto de lo que no es.
  - `mcp_server`: `n_arm` → `n_terminos_arm`, y el texto que sale al analista
    pasa de «11 armónicos» a «11 términos armónicos».
