---
id: BUG-0258
title: Con λ=1 μ, los coeficientes de los armónicos y la media residual salen en la escala ×100 de fue, al lado de un σ̂ₐ ya devuelto a las unidades de la serie
status: fixed
severity: medium
component: describe
found_in: 0.2.4
fixed_in: 0.2.5 (unreleased)
reported: 2026-11-15
reporter: David / Claude — revisión de incoherencias entre componentes antes de mtram
tags:
  - scale
  - lambda-1
  - equation
references:
  - src/art/describe.py:1705-1745 (μ en la ecuación, sin dividir)
  - src/art/describe.py:1240-1245 (s_om = escala_omega, que sólo se aplica a las intervenciones)
  - src/art/describe.py:1860-1865 (σ̂ₐ, que sí se divide: BUG-0033)
  - src/art/interventions.py:447 (escala_omega, la regla)
  - BUG-0033, BUG-0253 (la misma corrección, para σ̂ₐ y para los ω de las intervenciones)
---

## Summary

BUG-0033 devolvió σ̂ₐ a las unidades de la serie cuando λ ≠ 0 y BUG-0253 hizo
lo mismo con los ω de las intervenciones (`escala_omega`). Quedaron en la escala
en que estima fue (`refactor`·y):

- **μ** en la ecuación: `(Nₜ − 9959.416)` para una serie que vale ~99.6;
- los **coeficientes de cos, sin y (−1)ᵗ**: un coseno de amplitud 2 se imprime
  209.266;
- la línea **«Media residual»** de la diagnosis (`media=-0.2219` junto a
  σ̂ₐ = 0.878; su t = −0.03 sólo cuadra en la escala ×100).

```
  (2)  (1 − 0.5726·B) (Nₜ − 9959.416) = aₜ
           (0.0645)          (16.1182)

  σ̂ₐ = 0.87836
```

Y no es solo λ = 1 a factor 100. La regla mira la magnitud del factor
(`refactor >= 10`, `sigma_raw < 0.5`), y con ficheros que no vienen a 100 —la
GUI de atsw-gui escribe 1— la ecuación de un escalón del 5 % con σ = 1.1 % dice:

```
λ=0 factor=1    : ω = 0.0516   μ = 4.6051     σ̂ₐ = 0.01106  (1.106%)
λ=0 factor=10   : ω = 0.5165   μ = 46.051     σ̂ₐ = 0.1106%      <- es 1.106 %
λ=0 factor=100  : ω = 5.1645   μ = 460.511    σ̂ₐ = 1.1062%
λ=0 factor=1000 : ω = 51.645   μ = 4605.106   σ̂ₐ = 11.0621%     <- es 1.106 %
λ=1 factor=1…1000: ω = 5.2933, σ̂ₐ = 1.13558 (bien); μ = 100.0, 1000.1, 10000.8, 100008.1
```

## Impact

La ecuación mezcla dos escalas sin decirlo: σ̂ₐ en unidades de la serie y μ y
los armónicos cien veces mayores. Comparar μ con la media de la serie, o la
amplitud estacional con σ̂ₐ, exige saber que hay que dividir por 100. Lo
hereda mtram, que pinta la ecuación con `art.describe`. No afecta a la
estimación ni a los contrastes (t y Wald son cocientes).

## Reproduction

`bugs/BUG-0258-repro/repro.py`: serie sintética en torno a 100 (AR(1) de sd 1 más
un coseno de amplitud 2), `confirm_and_estimate` con λ = 1, μ y un par de
armónicos; lee μ, el coeficiente del coseno y σ̂ₐ de la ecuación. Sale con 1
mientras μ o el coseno estén en la escala ×100.

## Root cause

`describe.py` saca μ y los coeficientes deterministas de los parámetros
(`pi.pop()`) y los imprime tal cual; `s_om` (BUG-0253) se aplica sólo a los
escalones, impulsos, rampas y compimp. La media residual se calcula sobre los
residuos de fue, que están en la escala ×100.

## Fix

La regla es `fue.scale.display_scale`, y la ecuación entera pasa por ella:
`interventions.escala_omega` devuelve su divisor (ya no mira la magnitud del
factor) y se aplica a los ω de las intervenciones, a los armónicos y `alter`,
a `easter` y `trend`, a μ, a σ̂ₐ y a la media residual de la diagnosis. Con
λ = 0 todo va en tanto por ciento (lo que art ya enseñaba con factor 100: no
cambia nada de lo que se leía); con otro λ, en las unidades de la serie
transformada. Al PRESENTAR: el `.pre` y el motor siguen en su escala.

## Validation

El repro sale 0 (μ = 99.591, coseno 2.0927, σ̂ₐ = 0.877). Con factores 1, 10,
100 y 1000 la ecuación da las mismas cifras, en logaritmos y en niveles
(`tests/test_bug_0257_0258_0259_escala.py`).
