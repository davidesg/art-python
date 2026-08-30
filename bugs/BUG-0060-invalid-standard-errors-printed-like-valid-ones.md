---
id: BUG-0060
title: los errores típicos que son la semilla del BFGS se imprimían dentro del bloque con el mismo formato que los válidos — el aviso iba debajo, y el t que sale de ahí es el doble del verdadero
status: fixed
severity: high
component: describe
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-29
reporter: carril Claude del RUN 3 — defecto (4) de su informe
tags:
  - presentation
  - standard-errors
  - bfgs
references:
  - src/art/describe.py (model_equation)
  - src/art/diagnosis.py (bfgs_seed_var, degenerate_variance_indices)
  - bugs/BUG-0027-standard-errors-come-from-the-bfgs-seed.md
  - tests/test_bug_0060_errores_tipicos_marcados.py
  - bugs/BUG-0060-repro/repro.py
---

## Summary

BUG-0027 estableció que la covarianza que devuelve `fue` puede ser la **semilla
del BFGS** (c·I con c = 2/n) en vez del hessiano, y el bloque de la ecuación lo
**avisa** — debajo del cerco. Dentro del cerco, la cifra salía con el mismo
formato que una válida:

```
  (2)  (1 − 0·B) (∇Nₜ + 0.7202) = aₜ
                      (0.1552)
```

`0.1552` es exactamente √(2/83). El t que sale de ahí es **−4.64**. El honesto,
σ̂ₐ/√n = 0.2966, da **−2.43**.

De abrumador a justo significativo: **es la diferencia entre incluir la media y
no incluirla**, decidida sobre un número que la propia herramienta sabe que no
vale.

Y el aviso, aun estando, no basta: la ecuación es el bloque que el analista lee y
del que copia. Un párrafo debajo no desarma una cifra que ya está impresa con
formato de dato bueno.

## Fix

**Se marcan dentro del cerco**, donde están:

```
  (2)  (1 − 0·B) (∇Nₜ + 0.7202) = aₜ
                     (✗0.1552)

  σ̂ₐ = 2.7020%   |   ℓ = -200.27   |   AIC = 402.55   |   BIC = 404.97

  ✗ = error típico NO VÁLIDO: es la semilla del BFGS (√(2/n) = 0.1552), no el
      hessiano. No calcules t con él.
  → μ sin ARMA libre: el error típico correcto es σ̂ₐ/√n = 0.2966, luego
      t = -2.43 (no -4.64).
```

Dos decisiones de implementación que conviene dejar escritas:

* **Se marca por VALOR, no por índice.** `degenerate_variance_indices` devuelve
  posiciones del vector plano de parámetros, y el orden de render no es ése — el
  propio módulo documenta ese desajuste. La semilla es √(2/n), un número
  conocido, así que comparar el error típico con él es exacto y no depende de
  ningún orden.
* **El error típico honesto sólo se publica donde es correcto.** σ̂ₐ/√n vale para
  la media **cuando no hay ningún parámetro ARMA libre**, porque entonces μ es la
  media muestral. Con ARMA libre no se imprime nada: dar un número aproximado
  sería repetir el error con otra cifra.

El conteo de «libre» usa las banderas (`ar_free`, `ma_free`, …), no `len()` — ver
BUG-0057 y la entrada del TODO sobre el artificio `1 1 / 0.000000 0`.

## Verificación en los tres regímenes

| modelo | niter | npar | marcados |
|---|---|---|---|
| `ITCER_m00mu` | 0 | 1 | 1 — toda la covarianza es semilla |
| `PGAS_m03` | 1 | 3 | 2 — los dos escalones sí, el AR(1) no |
| `RATIO_m23` (DS) | 5 | 11 | 5 — los deterministas sí, los seis del ARMA no |

La degeneración **parcial** es el caso peligroso y es el que ahora se distingue a
simple vista: en `PGAS_m03` el `(0.0786)` del AR(1) sale sin marcar porque esa
dirección sí se actualizó.
