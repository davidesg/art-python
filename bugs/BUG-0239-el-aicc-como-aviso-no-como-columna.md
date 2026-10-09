---
id: BUG-0239
title: Mejora: el AICc del identificador, de columna a AVISO — no ordena (BUG-0198) y en la lista no se sabe qué significa; donde aporta es al señalar un mixto persistente (orden de integración abierto)
status: open
severity: low
component: identification
found_in: 0.2.3.dev0 @088933d (+ arreglos sin commit de BUG-0225…0231)
fixed_in:
reported: 2026-10-08
reporter: David / Claude — batería ARIMA del identificador (ART_18/tests/benchmark_arima.py)
tags:
  - identificacion
  - aicc
  - diseno
  - mejora
references:
  - src/art/describe.py:811-850 (columna ΔAICc)
  - src/art/model_detection.py (_fit_information, mixed cells, _nested_parsimony)
  - BUG-0198 (opción B)
  - ART_18/tests/results_arima.txt
  - bugs/BUG-0238-repro/repro.py
---

## Summary

El AICc de los candidatos tiene hoy tres papeles: (1) decide qué cuatro ARMA mixtos entran
como candidatos, (2) desempata dentro de la banda de 0,04 tras parámetros y pureza, (3) se
imprime como ΔAICc junto a la similitud. Nunca se midieron por separado.

La batería ARIMA (50 réplicas, n = 200) los compara con la similitud sobre los mismos
candidatos:

| | similitud (B) | AICc |
|---|---|---|
| media, 1.º / top-3 | **74 % / 81 %** | 70 % / 77 % |
| ARMA(1,1) señal + ruido 0,95/0,7 | 64 % | **80 %** |
| MA(1) θ = 0,9 | 82 % | **86 %** |
| d = 1 sencillos | 78-86 % | 68-74 % |

El AICc gana sólo en los mixtos casi cancelados, que es donde, en los casos reales (Salamanca,
Villaverde), su preferencia por un ARMA(1,1) con φ ≈ 0,94 anunció que el orden de integración
estaba abierto.

## Impact

Dos criterios lado a lado, sin decir cuál manda ni qué significa que discrepen: el analista
(y el profesor) lo leyó como confuso.

## Reproduction

`ART_18/tests/benchmark_arima.py` (columnas B y Aic); `python bugs/BUG-0238-repro/repro.py`.

## Fix (a decidir con el analista)

- La similitud ordena (opción B, se mantiene).
- El ΔAICc sale de la lista; cuando el mejor por AICc es un mixto con φ̂ ≥ 0,9 (o un MA con
  θ̂ ≥ 0,9) y no es el primero de la lista, un AVISO: «el AICc prefiere X con φ ≈ …: señal de
  que el orden de integración puede estar abierto; contrástalo con `formal_tests`».
- Los mixtos entran como candidatos por similitud, como los puros (medir con la batería si se
  pierde alguno).
- El mismo cambio en el C (ART_18, `rank_shortlist_by_fit`).

## Validation

`benchmark_three_engines.py` y `benchmark_arima.py` sin pérdida en la media; el aviso aparece
en Salamanca y Villaverde.
