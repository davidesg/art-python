---
id: BUG-0044
title: the white-noise candidate was excluded from the identification list, and the parsimony score gave zero to the most parsimonious model — on ITCER it was the right answer and never appeared
status: fixed
severity: medium
component: identification
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-28
reporter: David / réplica TFM Bolivia — hallado por el experimento del chat limpio
tags:
  - identification
  - parsimony
references:
  - src/art/model_detection.py (suggest_orders, _parsimony_score)
  - tests/test_bug_0044_0045_white_noise_and_the_lower_side.py
---

## Summary

La herramienta imprime la regla justo encima de la lista:

> **Regla ACF/PACF:** … Sin estructura → **p=0, q=0**

y luego nunca ofrecía ese candidato:

```python
for P in range(eff_P + 1):
    for Q in range(eff_Q + 1):
        if p == 0 and q == 0 and P == 0 and Q == 0:
            continue          # ← el ruido blanco, fuera de la papeleta
        _add_candidate(p, q, P, Q)
```

Los cinco candidatos llevaban siempre parámetros. En ITCER —con la intervención
ya puesta, ningún retardo cruzando las bandas, y ni el AR(1) (t=1.87) ni el MA(1)
(t=1.80) alcanzando significación— **p=q=0 era la respuesta**, y un analista sin
contexto previo tuvo que llegar a ella CONTRA la lista.

## Lo de fondo, que apareció al quitar la exclusión

```python
def _parsimony_score(similarity, p, q, P, Q, emp, s):
    total = p + q + P + Q
    if total == 0:
        return 0.0
```

**La función de PARSIMONIA daba la peor nota posible al modelo más
parsimonioso.** Era una rama «esto no puede pasar» —coherente mientras el
candidato estuviera excluido— que, admitido éste, se convirtió en el ranking.

Medido sobre los residuos del ITCER con su intervención:

| candidato | similitud CRUDA | tras parsimonia |
|---|---|---|
| **ruido blanco (0,0,0,0)** | **0.9197** (la más alta de ocho) | **0.0000** (último) |
| MA(1) | 0.8575 | 0.8625 |
| AR(1) | 0.8280 | 0.8318 |

El teórico del ruido blanco es legítimo y calculable —ACF y PACF todo ceros, que
es lo que el ruido blanco ES— y la métrica de forma ya lo prefería. No había
razón técnica para excluirlo, sólo la incomodidad de ofrecer «ninguno» como
candidato.

## Fix

Se elimina la exclusión, y para `total == 0` la penalización es **cero**: la base
de 0.03 es el coste de *tener* un modelo ARMA, y aquí no lo hay. Le alcanza
además la bonificación de «simple y con buen ajuste», que es literalmente lo que
describe.

## La comprobación que importa: no puede ganar siempre

| | candidato en cabeza |
|---|---|
| residuos del ITCER (0 retardos fuera de banda) | **(0,0,0,0)** con 0.9697 |
| PGAS, ∇ln con r(1)=0.575 | MA(1) 0.8779 — el ruido blanco cae al 4.º con 0.8114 |

La métrica compara formas, así que un teórico plano encaja bien con un
correlograma plano y mal con uno que no lo es. El test fija las dos direcciones.
