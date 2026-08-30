---
id: BUG-0033
title: σ̂ₐ carries a percent sign that is only true when λ=0 — the rule branches on `refactor` alone, so a level model publishes a figure 100× too large with a label that misstates its units
status: fixed
severity: high
component: describe/equation
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-27
reporter: David / réplica TFM Bolivia
tags:
  - units
  - presentation
  - box-cox
references:
  - src/art/describe.py (model_equation, bloque de stats)
  - bugs/BUG-0033-repro/repro.py
  - tests/test_bug_0033_sigma_units_depend_on_lambda.py
---

## Summary

`fue` escala los residuos por `refactor` (×100, que lo pone el escritor de ART).
**Qué significa ese residuo escalado depende de λ**, y la regla no lo miraba:

```python
if refactor >= 10:
    sigma_disp = f"{sigma_raw:.4f}%"     # el `%` va SIEMPRE
```

| λ | residuo escalado | qué es |
|---|---|---|
| 0 | `∇ln(y)·100` | **un porcentaje** — el `%` es correcto |
| 1 | `∇y·100` | las **unidades de la serie ×100** — ni es un porcentaje ni está en la escala de nadie |

En un modelo en niveles la línea publicaba un número **100× inflado** con una
etiqueta que miente sobre sus unidades.

## El testigo, y por qué importa más de lo que parece

PGAS de la réplica del TFM, la misma serie por los dos carriles:

```
guiado   (λ=0)   σ̂ₐ = 7.8695%        ✓
autónomo (λ=1)   σ̂ₐ = 2273.6533%     ✗
```

La innovación real del segundo es **22.87 USD/t** sobre una media de 294.44 —
es decir **7.77 %**, casi exactamente el 7.87 % del primero.

**Los dos modelos tienen prácticamente la misma innovación, y la línea impresa
los separaba en dos órdenes de magnitud.** Ese es el daño: no es una errata de
formato, es que la comparación entre carriles —que es para lo que la réplica
existe— quedaba invalidada por la única cifra que resume el ajuste. El analista
que mira las dos líneas concluye que el modelo autónomo es basura, y no lo es
por ese motivo; es peor por otras razones (λ mal elegida, forma de la
intervención), todas ellas invisibles junto a un 2273 %.

Y lo encontró el analista mirando, no la batería: no había ningún test que
comparase la misma serie estimada con dos λ.

## Repro

`bugs/BUG-0033-repro/repro.py` — una serie positiva con innovación
multiplicativa del 8 %, estimada dos veces con la MISMA especificación:

```
serie: media=278.23  min=182.96  max=411.46

logs   (λ=0)    refactor = 100
   sd(residuos crudos) = 7.0519
   -> innovación       = 7.0519% (el crudo YA es %)
niveles (λ=1)   refactor = 100
   sd(residuos crudos) = 2018.3579
   -> innovación       = 20.1836 unidades = 7.254% de la media
```

Hay que pasar **por el `.inp`**: el ×100 lo pone el escritor de ART, y es justo
la rama donde vive el defecto. Un `fue.Model(...)` construido a mano sale con
`refactor=1` y no la toca — por eso la primera versión del repro no reprodujo
nada.

## Fix

Ramificar por λ, que es el dato que decide qué son esas unidades:

```python
if refactor >= 10 and lam == 0.0:
    sigma_disp = f"{sigma_raw:.4f}%"              # ∇ln·100 ES un porcentaje
elif refactor >= 10:
    sigma_disp = f"{sigma_raw / refactor:.5f}"    # unidades de la serie
elif lam == 0.0 and sigma_raw < 0.5:
    sigma_disp = f"{sigma_raw:.5f}  ({sigma_raw*100:.3f}%)"
else:
    sigma_disp = f"{sigma_raw:.5f}"
```

`lam` ya estaba en el ámbito (`lam = model.boxlam`, describe.py:730): el arreglo
no necesita ningún dato nuevo, sólo mirar el que ya tenía delante.

Después:

```
auto lam=1     σ̂ₐ = 22.73653   |   ℓ = -760.05   |   AIC = 1526.10
guiado lam=0   σ̂ₐ = 7.8695%    |   ℓ = -289.74   |   AIC = 585.49
```

## Lo que NO arregla

Las dos líneas siguen sin ser **directamente** comparables, y no pueden serlo:
una está en porcentaje y la otra en unidades porque los modelos viven en
escalas distintas, y por la misma razón sus AIC tampoco se comparan. Lo que el
arreglo garantiza es que **cada línea diga la verdad sobre sus propias
unidades**, que es la condición previa para que el analista haga la conversión.

Queda abierto si la ecuación debería ofrecer además la innovación **relativa**
(σ̂ₐ / media de la serie) para modelos con λ≠0, precisamente para que la
comparación entre carriles no dependa de que alguien haga la división a mano.
Anotado en TODO.md.
