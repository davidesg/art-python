---
id: BUG-0151
title: La covarianza del .out conserva la semilla del BFGS en direcciones ROTADAS — ningún detector por parámetro la ve
status: open
severity: high
component: estimation
found_in: 0.2.2
fixed_in: 
reported: 2026-09-10
reporter: David — corrida guiada fase 1, ITCER
tags:
  - fase-1
  - covarianza
  - errores-tipicos
  - bfgs
references:
  - BUG-0027
  - BUG-0041
  - BUG-0124
---

## Summary

El método dice que los errores típicos válidos están en el `.out` y sólo ahí.
En ITCER no lo están: la covarianza del `.out` es la aproximación del BFGS al
inverso del hessiano, y **en una o dos direcciones que no son ejes de ningún
parámetro sigue siendo la semilla**. Las varianzas de la diagonal parecen
normales —ninguna está cerca de la semilla—, así que ni el detector exacto
(BUG-0027) ni el de proximidad (BUG-0041/0124) la ven.

El resultado publicado: errores típicos **demasiado pequeños**, t inflados y un
aviso de «posible sobreparametrización» que es un artefacto.

## Impact

Alto, porque va en la dirección peligrosa (infra-estima) y porque llega por el
canal que el método declara fiable. Afecta a las decisiones que se toman con t:
la regla «no añadas un parámetro no significativo», el contraste de
intervenciones y el análisis de sobreparametrización (que propone quitar
parámetros por una correlación de −0,99 que no existe).

En este caso las conclusiones al 5 % sobreviven por margen; con un parámetro
más justo no sobrevivirían: ω₀ de m01 se publica con p = 0,007 y vale p ≈ 0,04.

## Reproduction

ITCER, λ=0, d=1, D=0, μ + intervenciones de escalón, sin ARMA. Sin ARMA el MV
exacto es un MCO de ∇(100·ln y) sobre μ y los impulsos, y la covarianza exacta
es σ̂²(X′X)⁻¹: impulsos en fechas distintas son **ortogonales**, así que cada ω
tiene varianza ≈ σ̂²·(1+1/n) y correlaciones ≈ 0,01.

**m01** (`Q2/2008×3`; 14 iteraciones, gradiente 0):

| | ω₀ | ω₁ | ω₂ | corr(ω₀,ω₁) |
|---|---|---|---|---|
| `.out` | 1,7356 | 1,5618 | 2,2754 | **−0,98** |
| exacto | 2,3161 | 2,3161 | 2,3161 | 0,012 |

**m02** (m01 + `Q2/2009×1`; 9 iteraciones):

| | ω₀ | ω₁ | ω₂ | corrs del bloque |
|---|---|---|---|---|
| `.out` | **1,2766** | **1,2766** | **1,2766** | **±0,99** |
| exacto | ≈2,18 | ≈2,18 | ≈2,18 | ≈0 |

El ω de 2009 (2,1743) y μ (0,2432) del mismo `.out` sí coinciden con los
exactos.

**La firma, en los autovalores** del bloque ω de 2008 del `.out` (semilla del
BFGS: var = 2/n ≈ 0,024):

| | autovalores | exactos |
|---|---|---|
| m01 | **0,0175**, 5,20, 5,41 | ≈5,4 ×3 |
| m02 | **0,0214**, **0,0214**, 4,85 | ≈4,75 ×3 |

Una dirección (m01) y dos (m02) se quedaron en la semilla, rotadas respecto de
los ejes: en m01 la menor es ≈ (0,67, 0,74, −0,08), en m02 el subespacio
ortogonal a (1, −1, −1). Por eso cada varianza de la diagonal es una mezcla de
una dirección aprendida y otras sin aprender, y ninguna parece «la semilla».

Los ficheros: `replica/fase1/ITCER/ITCER_m01.out`, `ITCER_m02.out`.

## Root cause

La covarianza que publica fue es el inverso del hessiano **aproximado** por el
BFGS a lo largo de su camino (BUG-0027). Converger en el gradiente no garantiza
que la aproximación haya aprendido la curvatura en todas las direcciones: con
arranques en los que el gradiente no explora un subespacio, éste queda en la
matriz inicial c·I.

Los detectores actuales comparan la **diagonal** con la semilla. Una semilla
retenida en una dirección rotada no aparece en la diagonal.

## Fix

Dos niveles:

1. **Detectar**: comparar los AUTOVALORES de la covarianza (o del hessiano
   aproximado) con la varianza-semilla, no las varianzas de la diagonal. Un
   autovalor a menos de un orden de magnitud de la semilla ⇒ aviso, y los t de
   los parámetros con carga en ese autovector se marcan como no válidos.
2. **Arreglar**: al terminar, calcular el hessiano numérico en el óptimo
   (diferencias finitas sobre la log-verosimilitud exacta) y publicar esa
   covarianza —la información observada—, dejando la del BFGS como diagnóstico
   del camino. Es el único arreglo que no depende de cómo haya ido el camino.

## Validation

`m01`/`m02` de ITCER como fixture: los errores típicos publicados de los ω de
2008 deben quedar en ±5 % de 2,316 (m01) y ≈2,18 (m02), y la correlación del
bloque por debajo de 0,1. Y una prueba de la clase: modelo de regresión pura sin
ARMA, donde la covarianza exacta es σ̂²(X′X)⁻¹ en forma cerrada, contra la
publicada.
