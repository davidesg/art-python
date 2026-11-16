---
id: BUG-0259
title: La semilla de μ transforma con |y|^λ y fue con (y^λ − 1)/λ — con λ fuera de {0, 1} el ajuste cae en el óptimo degenerado de BUG-0001
status: fixed
severity: high
component: pipeline
found_in: 0.2.4
fixed_in: 0.2.5
reported: 2026-11-15
reporter: David / Claude — revisión de incoherencias entre componentes antes de mtram
tags:
  - mu
  - lambda
  - optimum
  - seed
references:
  - src/art/pipeline.py:942 (_mu_seed)
  - fue src/fue/forecast.py:91 (_boxcox, la transformación de fue y del C)
  - BUG-0001 (por qué existe la semilla)
---

## Summary

`_mu_seed` existe para que μ no arranque lejos de los datos (BUG-0001: una raíz
AR en 1 absorbe el nivel). Transforma con `sign(y)·|y|^λ`; fue (y el C)
transforma con `(y^λ − 1)/λ`. Con λ ∉ {0, 1} la semilla está en otro espacio:

```
λ = −1, serie ~100:   semilla de art = 1.0003    media de lo que fue ajusta = 99
λ = −0.5:             semilla = 10.0              media = 180
λ =  0.5:             semilla = 999.9             media = 1 800
```

y fue cae en el óptimo degenerado:

```
λ = −1:   art: φ = 1.0000  ℓ = 471.904    bien sembrado: φ = 0.5128  ℓ = 503.178
λ = −0.5: art: φ = 1.0000  ℓ = 105.265    bien sembrado: φ = 0.5135  ℓ = 134.749
λ =  0.5: art: φ = 0.9999  ℓ = −628.482   bien sembrado: φ = 0.5148  ℓ = −602.137
```

Con d ≥ 1 la semilla de la deriva sale con el signo cambiado si λ < 0 (factor
1/λ); en el caso medido fue se recupera.

## Impact

Alto para quien fija λ fuera de {0, 1} con μ y d = 0: el modelo sale con una
raíz unitaria espuria, 26-31 puntos de ℓ por debajo del óptimo, y converge
(`converged=True`), así que nada lo delata. Lo que fue escribe en el `.pre` es
ese óptimo falso y se propaga a mtram y sima. La política de art sólo propone
λ = 0 o 1; entra por `confirm_and_estimate` con λ del analista.

## Reproduction

`bugs/BUG-0259-repro/repro.py`: AR(1) sintético del 1 % en torno a 100,
`confirm_and_estimate` con λ = −1, d = 0 y μ, contra el mismo modelo sembrado en
la media de lo que fue ajusta. Sale con 1 mientras el de art quede más de un
punto de ℓ por debajo.

## Root cause

`_mu_seed` escribe su propia Box-Cox en vez de usar la de fue
(`fue.forecast._boxcox`, la del C). Para λ = 0 y λ = 1 coinciden con la de fue
salvo una constante que μ absorbe (λ = 1: fue usa y, no y − 1), y por eso no se
vio.

## Fix

`_mu_seed` usa `fue.scale.boxcox`, la transformación del motor. Lo mismo las
otras dos copias que había (la referencia de las semillas estacionales,
`pipeline.py`, y la decisión de la deriva, `policy.py`).

## Validation

El repro sale 0: con λ = −1, φ = 0.5128 y la verosimilitud del modelo bien
sembrado (antes φ = 1.0000 y 31 puntos menos).
