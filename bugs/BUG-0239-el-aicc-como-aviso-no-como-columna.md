---
id: BUG-0239
title: Mejora: el AICc del identificador, de columna a AVISO — no ordena (BUG-0198) y en la lista no se sabe qué significa; donde aporta es al señalar un mixto persistente (orden de integración abierto)
status: fixed
severity: low
component: identification
found_in: 0.2.3.dev0 @088933d (+ arreglos sin commit de BUG-0225…0231)
fixed_in: 0.2.3
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

`python3 bugs/BUG-0239-repro/repro.py` — Salamanca y Villaverde (los `.inp` de
BUG-0232-repro y BUG-0235-repro); sale con 1 mientras la lista lleve ΔAICc o falte
el aviso.

`ART_18/tests/benchmark_arima.py` (columnas B y Aic); `python bugs/BUG-0238-repro/repro.py`.

## Fix

De las cuatro piezas propuestas, dos ya estaban hechas antes de este arreglo y
no se tocan: la similitud ordena (BUG-0198, opción B) y los mixtos entran por
similitud como los puros (9-oct-2026, `ART_MIXTOS_POR`, en
`suggest_orders`). La del C (ART_18, `rank_shortlist_by_fit`) no está en este
repositorio: queda para quien lleve el motor C. Lo hecho, en
`src/art/describe.py`:

- **El ΔAICc sale de la lista.** La lista marca `[empate]` en los candidatos de
  la banda del primer puesto (la de la ficha, BUG-0233) y la nota de orden lo
  explica. El orden NO cambia —el AICc sigue siendo la última clave de
  `_nested_parsimony` entre candidatos de igual tamaño y pureza—, así que las
  baterías de acierto no se mueven por construcción.
- **El aviso** (`_aviso_aicc_persistente`): si el mejor por AICc de los
  candidatos de la lista es un mixto con una raíz AR real ≥ 0,9, o lleva una
  raíz MA real ≥ 0,9, dice cuál es, en qué puesto va y que el orden de
  integración puede estar abierto, y remite a `formal_tests` (Shin-Fuller y DCD,
  o el DCD de sobrediferenciación). Se aparta de lo propuesto en dos cosas:
  1. avisa también cuando ese mixto ES el primero de la lista: en Salamanca el
     (1,1,1) con φ = 0,95 va primero, y es justo el caso que motivó el aviso;
     con «y no es el primero» no aparecería;
  2. exige que el otro lado no cancele la raíz (`HOLGURA_CANCELACION` = 0,05):
     un φ y un θ casi iguales se anulan entre sí, no con la diferencia. En
     modelos sin persistencia los avisos del lado AR bajan de 7 a 1 de 240
     (casi todos eran φ ≈ θ ≈ 1); en total, de 11 a 10.

Medido (60 réplicas por caso, n = 200, d = 1): avisa en 10 de 240 modelos sin
persistencia (ruido, AR(1) 0,6, MA(1) 0,5, ARMA(1,1) 0,6/0,3), en 43/60 del
ARMA(1,1) 0,95/0,7, en 26/60 de un I(2) diferenciado una vez y en 53-57/60 de un
I(0) sobrediferenciado.

Test: `tests/test_bug_0239_aicc_como_aviso.py` — la raíz real mayor; avisa con un
mixto persistente (lado AR) y con un MA cerca de 1 (lado MA); no avisa sin
persistencia ni con φ ≈ θ; en Salamanca y Villaverde, sin ΔAICc y con el aviso
sobre el ARIMA(1,1,1). Falla sin el arreglo.

## Validation

El repro sale con 0: ninguna de las dos listas lleva ΔAICc y las dos traen el
aviso —Salamanca: ARIMA(1,1,1), 1.º de la lista, raíces 0,95 (AR) y 0,68 (MA);
Villaverde: ARIMA(1,1,1), 4.º de la lista, 0,97 y 0,87—. Antes salía con 1.
