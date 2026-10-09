---
id: BUG-0238
title: El identificador no propone nunca el AR(4) con los coeficientes de Salamanca: ausente de la lista en 20 de 20 réplicas (y 0 de 50 entre los tres primeros en la batería ARIMA); el C lo pone entre los tres primeros en el 54 %
status: wontfix
severity: medium
component: identification
found_in: 0.2.3.dev0 @088933d (+ arreglos sin commit de BUG-0225…0231)
fixed_in:
reported: 2026-10-08
reporter: David / Claude — batería ARIMA del identificador (ART_18/tests/benchmark_arima.py)
tags:
  - identificacion
  - candidatos
  - ar-de-orden-alto
references:
  - src/art/model_detection.py (suggest_orders: _validate_ar, eff_p, BUG-0194 «AR de orden alto»)
  - ART_18/tests/results_arima.txt
  - bugs/BUG-0238-repro/repro.py
---

## Summary

AR(4) con los coeficientes estimados en Salamanca (φ = 0,334; 0,136; 0,111; 0,187), d = 1,
n = 200. `suggest_orders(d=1, top_n=50)`:

- el (4,0) **no está en la lista** en 20 de 20 réplicas (repro);
- lo que sale primero: ARMA(1,1) en 15, AR(3) en 3, AR(2) en 2;
- en `benchmark_arima.py` (50 réplicas): 0 % primero y 0 % entre los tres primeros, por
  similitud y por AICc; el C 20 % / 54 %; pmdarima 46 %.

En la serie REAL de Salamanca el AR(4) sí apareció, pero por la regla del AR de orden alto
(BUG-0194: una barra AISLADA de la FAP), y quinto.

## Impact

Un AR de orden 4 con coeficientes pequeños es la lectura natural de la FAP en precios de
vivienda (los distritos de la P02). El identificador lo cambia por un ARMA(1,1) persistente
—que es precisamente el que lleva a pedir d+1 (Salamanca)—, sin ofrecer la alternativa.

## Reproduction

`python bugs/BUG-0238-repro/repro.py 20` (bloque «AR(4) Salamanca»).

## Root cause

Diagnosticado el 9-oct-2026 (`suggest_orders`, 20 réplicas, n = 200). Son dos causas, y
ninguna es el filtro de la FAP:

1. **Entrada.** Con `freq=1`, que es la de la batería, `p_max` vale 3
   (`p_max = max(3, s // 2) if s > 1 else 3`) y un AR(4) no puede entrar. Con `freq=12`, la de
   los distritos, entra por la regla de los submúltiplos de s (BUG-0194: 4 = 12/3) en 15 de 20
   réplicas, siempre que la FAP en 4 sea significativa.
2. **Orden.** Cuando entra, queda en el 4.º o el 5.º puesto. Su similitud cruda es la más alta
   con diferencia (0,99, frente a 0,91 del ARMA(1,1)). La carga de parsimonia la iguala:
   0,03 + 0,015 por parámetro, más la bonificación de +0,05 que reciben los modelos de hasta 3
   parámetros. Las dos quedan en 0,90. Dentro de la banda de empate (`TIE_SIM` = 0,04),
   `_nested_parsimony` pone primero al que tiene menos parámetros.

La FAP de este AR(4) es un BLOQUE: 1, 2, 3 y 4 significativas en el 100, 80, 65 y 70 % de las
réplicas. Es justo lo que la decisión del 29-sep-2026 (BUG-0194) lee como persistencia, no
como un AR de orden alto. La regla que pone el *airline* de la serie G por delante del
AR(3)×SAR(1), con similitud cruda 0,882 frente a 0,973, es la misma que pone aquí el ARMA(1,1)
por delante del AR(4).

## Fix

No se corrige en la identificación. Abrir la entrada para s = 1 (p_max = 4) no cambia el
primer puesto ni los tres primeros, porque el cuello de botella es el orden. Cambiar el orden
rompe la serie G (test_bug_0192). Que un AR(4) de coeficientes pequeños y un ARMA(1,1)
compitan se resuelve después de la identificación: estimando los dos y con la
sobreparametrización y la diagnosis.

Tampoco lo arreglaría la red del C como fuente de candidatos. En mensual el AR(4) ya está en
la lista; lo que le falta es el puesto.

## Validation

Repro y `benchmark_arima.py`: el AR(4) entre los tres primeros en una proporción comparable a
la del C.
