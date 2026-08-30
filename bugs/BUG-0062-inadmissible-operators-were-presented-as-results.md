---
id: BUG-0062
title: un operador con raíces dentro del círculo unidad se presentaba como cualquier otro resultado — un MA estacional con Θ₄=−2.0989 (no invertible) salió de 45 iteraciones sin una palabra, y sólo la diagnosis rota lo delataba
status: fixed
severity: high
component: describe
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-29
reporter: carril Claude del RUN 3 — defecto (5) de su informe
tags:
  - invertibility
  - stationarity
  - presentation
references:
  - src/art/diagnosis.py (admissibility_problems, _raices_factor)
  - src/art/describe.py (model_equation)
  - tests/test_bug_0062_admisibilidad.py
  - bugs/BUG-0062-repro/repro.py
---

## Summary

Un AR con raíz **dentro** del círculo unidad no es estacionario; un MA con raíz
dentro no es invertible. Las dos cosas invalidan la lectura del modelo, y ninguna
se anunciaba.

`RATIO_m04sma1` estimó un MA estacional **Θ₄ = −2.0989** —raíz de módulo **0.831**
en B— tras 45 iteraciones, y con `fue` declarando *«Check for invertibility:
constrained search»* en la cabecera de su propio `.out`. Se imprimió como
cualquier otro resultado. Lo único que delataba el problema era la diagnosis rota
(Q), que es enterarse por el síntoma equivocado: un operador inadmisible no es un
modelo que ajusta mal, es un modelo que **no se puede leer**.

Un MA no invertible no tiene representación AR(∞), así que su previsión depende
del pasado infinito y sus parámetros no son interpretables.

## La convención, que es de donde sale la comprobación

`fue` guarda **`(1 − c₁B − c₂B² − …)` para AR y MA por igual**. Comprobado contra
la ecuación que ART imprime:

| almacenado | renderizado |
|---|---|
| `ar = [0.7647, −0.2640]` | `(1 − 0.7647·B + 0.2640·B²)` |
| `ma = [−0.7879, −0.2760]` | `(1 + 0.7879·B + 0.2760·B²)` |

Para un factor estacional el polinomio va en `u = Bˢ`. El módulo se reporta
**siempre en B** (`|B| = |u|^{1/s}`), que es el que el analista compara con 1 al
leer la ecuación: sobre Θ₄ eso es |u| = 0.476 y **|B| = 0.831**.

## Dentro y frontera no son lo mismo

Barridos los **214 modelos** de la réplica salen exactamente **dos** casos, uno
de cada clase, y ningún falso positivo:

| modelo | operador | \|raíz\| | clase |
|---|---|---|---|
| `run3/RATIO/RATIO_m04sma1` | MA estacional | 0.8308 | **dentro** — no invertible |
| `run2/RATIO/RATIO_m22` (DS) | MA(4) | 1.000000 | **frontera** |

El segundo tiene **dos raíces de módulo exactamente 1** con `d=1`: eso no es un
operador roto, es el MA **cancelando la diferencia** — la firma de la
sobrediferenciación. Se arreglan de forma distinta, así que llevan mensajes
distintos: el primero manda reformular el operador; el segundo remite a
`formal_tests` antes de mover `d`.

## Lo que queda fuera a propósito

`ar_f` y `ma_f` no se comprueban. El testigo del MEG vive ahí y **apunta
deliberadamente a la frontera** (λ → −1): marcarlo sería avisar de justo lo que
el contraste está buscando.
