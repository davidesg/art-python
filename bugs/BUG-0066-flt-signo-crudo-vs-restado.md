---
id: BUG-0066
title: la FLT de una intervención se imprime con el signo crudo, pero fue la estima restada — (0.74 + 0.43B) sale dibujado (0.74 − 0.43B) y la ganancia mostrada queda en la mitad
status: fixed
severity: medium
component: describe
found_in: 0.1.12 (unreleased)
fixed_in:
reported: 2026-09-01
reporter: David / benchmark guiado ES_CORE — FLT (ω₀−ω₁B) Step 9/2012
tags:
  - presentation
  - intervention
  - transfer-function
  - sign-convention
references:
  - src/art/describe.py (model_equation — _sign_det en la FLT, i≥1)
  - bugs/BUG-0066-repro/repro.py
  - bugs/BUG-0062-inadmissible-operators-were-presented-as-results.md (la convención (1 − c₁B − …))
---

## Summary

La **función lineal de transferencia** de una intervención se imprime con el
signo **crudo** del coeficiente, pero `fue` la estima en convención **restada**
(ω₀ − ω₁B − ω₂B² − …), la misma que usa para AR/MA. El resultado: el término B
sale con el **signo opuesto** al que estima el motor, y la **ganancia** que un
analista leería del display queda en la mitad (o con el signo equivocado).

Caso que lo delató — ES_CORE, FLT (ω₀ − ω₁B) Step 9/2012:

```
.out → Omegas for deterministic variable 12:
           0.739736   (ω₀)
          −0.429645   (ω₁,  ¡negativo!)
display → (0.7397 − 0.4296·B) ξ^{S,9/2012}     ← signo CRUDO
motor   → ω₀ − ω₁B = 0.7397 − (−0.4296)B = 0.7397 + 0.4296·B
```

El operador real es **(0.74 + 0.43·B)** y la ganancia v(1) = **1.17**. El display
imprime (0.74 − 0.43·B), que da una ganancia de 0.31 — **4× menos** y con la
lectura económica invertida (reversión vs. segundo escalón al alza).

## La convención (la misma que BUG-0062)

`fue` guarda `(1 − c₁B − c₂B² − …)` para AR y MA. Para las intervenciones, el
numerador de la FLT usa la **misma** convención: `v(B) = ω₀ − ω₁B − ω₂B² − …`.
La equivalencia que lo demuestra es empírica y exacta: un modelo con **dos steps
separados** (Step 9/2012 = +0.7397, Step 10/2012 = +0.4296) da **el mismo
loglik** (104.47) que la FLT con `omega = [0.7397, −0.4296]`. Sólo hay una forma
de que eso ocurra: el motor **resta** ω₁.

## Root cause

`describe.py` → `model_equation`, rama de FLT con varios ω (`len(om) > 1`):

```python
# describe.py, ~línea 1082 — término i≥1
tl.add(f"  {_sign_det(v)} ")     # signo CRUDO  ← el bug
```

`_sign_det` devuelve el signo crudo (`"+" si v≥0`), pero para el numerador de la
FLT el término es `− ωᵢBⁱ`, es decir el signo **restado**. Es exactamente lo que
ya hace `_fmt_poly` para AR/MA con `_sign_arma` (`"fue stores value to subtract,
so positive→−, negative→+"`). La FLT usa el helper equivocado.

## Fix

En la rama de FLT (i≥1), usar `_sign_arma(v)` en vez de `_sign_det(v)`:

```python
tl.add(f"  {_sign_arma(v)} ")
```

El término ω₀ (i=0) queda como está (se usa directo, sin resta). El caso de un
solo ω (`len(om) == 1`) también queda como está: no hay término B que restar.

## Validation

`bugs/BUG-0066-repro/repro.py` — ajusta una serie sintética con un escalón de dos
subidas y comprueba que el término B renderizado lleva el signo restado
(`+0.5·B`), no el crudo (`−0.5·B`). Sale 1 con el bug, 0 arreglado.


---

## Arreglado el 2026-09-02 — con la convención verificada en el motor

La convención se comprobó en el código, no se supuso. `fue/forecast.py`, sobre
`_calcnu`:

> *«Matches `calcnu()` in `fue_api.c`: `nu[j] = Σ δ_i·nu[j−i] − ω[j]`»*

Es decir **ω₀ − ω₁B − ω₂B² − …**, la misma convención que AR y MA. El informe
tenía razón.

### El caso de la otra réplica, que lo confirma y mide el daño

`ITCER_m10` del TFM de Bolivia, ω = [−8.9851, +8.9352]:

```
display crudo   (−8.9851 + 8.9352·B)     → parece que se cancelan
respuesta real  ν = [−8.9851, −8.9352]   → SE SUMAN,  v(1) = −17.92
```

**El display sugería un efecto neto de −0.05 y el real es −17.92.** No es un
detalle de presentación: durante toda la revisión de esa réplica el modelo se
leyó como «dos coeficientes casi simétricos, y esa casi-cancelación es lo que
dice que el escalón es transitorio». Es falso. Lo transitorio viene de la **forma
impulso** (respuesta finita), no de una cancelación, y la caída es del **18 % en
dos trimestres**.

Un display que invierte un signo no produce una lectura peor: produce **la
lectura contraria**.

## Fix

`_sign_det` se queda para lo que entra en la parte determinista tal cual —ω₀, una
intervención de un solo coeficiente, los armónicos— y se añade `_sign_omega_lag`
para los retardos ≥ 1, que el motor resta.

El test fija el **invariante**, no el texto: para cada término del polinomio, el
signo dibujado tiene que coincidir con el signo de `_calcnu`. Así cualquier
cambio futuro de la convención del motor rompe el test en vez de pasar
inadvertido.

## Nota

Este número colisionó con un informe de la réplica del TFM de Bolivia escrito el
mismo día; aquél se renumeró a BUG-0069. Ver `bugs/README.md`.
