---
id: BUG-0253
title: con λ=1 los ω de una intervención salen en la escala ×100 de fue, al lado de un σ̂ₐ ya devuelto a las unidades de la serie
status: fixed
severity: medium
component: describe/interventions
found_in: 0.2.3
fixed_in: 0.2.4
reported: 2026-10-22
reporter: Claude, en la réplica de Martín Manjón y Treadway (1997) con el rodaje de sima 0.2.0
tags:
  - scale
  - interventions
  - lambda-1
references:
  - src/art/describe.py:1505-1530 (los ω de la ecuación, sin dividir por refactor)
  - src/art/describe.py:1838-1860 (σ̂ₐ, que sí se divide con λ=1: BUG-0033)
  - BUG-0033, BUG-0084, BUG-0085 (la misma escala, por otros caminos)
---

## Summary

La suite estima con `refactor=100`: con λ=0 eso pone todo en tanto por ciento,
que es lo que hace legibles las ecuaciones. Con **λ=1** el residuo escalado son
las unidades de la serie ×100, y BUG-0033 arregló σ̂ₐ dividiéndolo por
`refactor`. **Los ω de las intervenciones no se dividen**: la misma ecuación
muestra σ̂ₐ en las unidades de la serie y los ω cien veces mayores.

Fed Funds efectivo 1985-1995 en 100·log(1+y/100) (λ=1). En ∇ el salto de 12/1986
es **+0.8171**, y los dos escalones de 12/1986 estiman ω₀ = 0.817 (s.e. 0.22),
ω₁ = 0.450 (s.e. 0.22) en las unidades de la serie. La ecuación imprime:

```
  + (81.710  − 45.000·B) ξₜ^{S,12/1986}
    (22.0805) (22.0816)
  σ̂ₐ = 0.21966
```

## Impact

Un salto de 0.82 puntos se lee como uno de 82, contra una innovación de 0.22.
Lo mismo en `guided_intervention` (Call 2: la tabla de configuraciones da
ω(1) = +36.71, +81.71, y la figura tiene el eje ∇ en esa escala) y en el
contraste de intervenciones («ω(1)=+36.7100 [desplazamiento permanente…]»).
Comparar el ω con el artículo (.57 % en su Tabla 2) o con σ̂ₐ exige saber que hay
que dividir por 100. No afecta a la estimación ni a los contrastes (t, Wald):
sólo a cómo se presentan los ω.

## Reproduction

`bugs/BUG-0253-repro/repro.py` (datos públicos de FRED, FEDFUNDS, transformados
como en el artículo): estima ∇y sin ARMA, añade `step` con `n_omega=2` en
12/1986 y lee ω₀ y σ̂ₐ de la ecuación. Sale 1 mientras ω₀ esté en la escala ×100.

## Root cause

`describe.py` toma los ω de los parámetros del modelo (`pi.pop()`) y los imprime
tal cual; la conversión `/ refactor` de BUG-0033 sólo se aplica a σ̂ₐ. Con λ=0
no se nota porque ×100 es tanto por ciento, la escala que se quiere.

## Fix

`interventions.escala_omega(model)` es la regla, la misma de σ̂ₐ (BUG-0033):
`refactor` cuando refactor ≥ 10 y λ ≠ 0, 1 en otro caso. Se divide al
PRESENTAR, y el `.pre` y el motor siguen en su escala:

- `test_intervention` y `net_gain`: ω, sus s.e., ω(1), su s.e., la ganancia
  y la ganancia neta. De ahí lo leen la tabla de configuraciones
  (`configuracion`), la escalera (`escalera`) y el contraste de
  intervenciones; las t, los p y los Wald son cocientes y no cambian.
- `describe`: los ω de la ecuación (escalón, impulso, rampa, compimp) y sus
  s.e.
- La advertencia de rampa de `mcp_server`: el ω por periodo y su anualizado.
- La figura de `guided_intervention`: los residuos y los ω que se superponen
  (la escala y el R² de la superposición no cambian).

`intervention_plot` no cambia: recibe los ω «tal como salen del `.out`», en la
escala del motor, junto con los residuos del modelo, y los dos están en la
misma.

## Validation

El repro sale 0: la ecuación imprime ω₀ = 0.8171 al lado de σ̂ₐ = 0.21966.
En `guided_intervention` la tabla de configuraciones da ω(1) = +0.3671 y
+0.8171 (antes +36.71 y +81.71), y `test_interventions` ω[0] = +0.8171,
SE 0.2208, con la misma t (3.701) y el mismo Wald (1.382).
