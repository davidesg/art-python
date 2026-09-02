---
id: BUG-0071
title: el Wald conjunto de test_intervention contrastaba α=(1,−δ₁,−δ₂,…)·ω, que no es la ganancia ν(1) ni el numerador ω(1) ni ninguna cantidad reconocible
status: fixed
severity: high
component: interventions
found_in: 0.1.12
fixed_in: 0.2.0 (unreleased)
reported: 2026-09-02
reporter: David / auditoría previa al nodo de intervención por episodios
tags:
  - intervention
  - wald
  - gain
  - sign-convention
  - flt
references:
  - src/art/interventions.py (test_intervention — Wald conjunto)
  - bugs/BUG-0071-repro/repro.py
  - tests/test_bug_0071_wald_es_la_ganancia.py
  - docs/DISENO-nodo-intervencion.md §3, §4.1
  - BUG-0066 (la misma convención de signo, en la lectura de la respuesta)
---

## Summary

El contraste conjunto sobre los ω de una intervención usaba

```python
alpha_vec = np.array([1.0] + [-d for d in free_dl[:k - 1]])   # (1, −δ₁, −δ₂, …)
g         = alpha_vec @ omega_est
```

es decir, metía los coeficientes del **denominador** δ dentro de un contraste
sobre el **numerador** ω. El resultado, `g = ω₀ − δ₁ω₁ − δ₂ω₂ − ⋯`, no es la
ganancia a largo plazo ν(1), no es el numerador ω(1), y no corresponde a
ninguna cantidad de la función de transferencia: ni a νₖ, ni a una suma parcial
de la respuesta al impulso.

Procede del commit inicial y nunca se revisó.

## Repro

`bugs/BUG-0071-repro/repro.py` — determinista, sin datos y sin `fue`: pura
aritmética sobre la convención de signo del motor.

```
caso                          nu(1) recursión    w(1)/d(1)  alpha ACTUAL
------------------------------------------------------------------------
FLT s=1 r=1 decaimiento              2.200000     2.200000      0.950000
FLT s=1 r=1 respuesta lenta          4.000000     4.000000      0.840000
FLT s=2 r=1                          4.125000     4.125000      1.740000
FLT s=2 r=2                          4.500000     4.500000      1.860000
```

Con ω=(0,80, −0,30) y δ=(0,50): la ganancia vale 2,20, el numerador ω(1) vale
1,10, y el contraste devolvía 0,95. Las dos primeras columnas coinciden siempre
—la ganancia es ésa—; la tercera no reproduce ninguna de las dos en ningún caso.

## Cause

Confusión entre «la ganancia lleva δ dentro» y «hay que meter δ en el α». La
ganancia es un **cociente**, ν(1) = ω(1)/δ(1); δ va en el denominador, no
multiplicando los ω del numerador.

## Fix

α = (1, −1, …, −1), que es ω(1) con la convención del motor:

```
ω(B) = ω₀ − ω₁B − ⋯ − ω_sB^s   ⟹   ω(1) = ω₀ − ω₁ − ⋯ − ω_s
```

Escribirlo como suma directa `Σωᵢ` daría un número plausible y
sistemáticamente equivocado — es la misma convención que produjo BUG-0066, donde
leímos como cuasi-cancelación (−0,05) una respuesta que **suma** −17,92.

**Y el denominador no hace falta.** Para H₀: ν(1) = 0 el cociente es cero
exactamente cuando lo es su numerador, siempre que δ(1) ≠ 0. Así que el
contraste de ganancia nula es un Wald lineal EXACTO sobre ω y **no necesita
método delta**. Éste sólo hace falta para un intervalo sobre la ganancia, o para
contrastar una ganancia distinta de cero. Con δ(1) → 0 el modelo es
inadmisible; `gain` vuelve NaN y de eso habla `admissibility_problems`.

El signo lo fija la **posición** en el vector ω completo, no el orden entre los
libres: fijar ω₀ desplazaba todos los signos un hueco. Los ω fijos entran como
constante `c` en `g = α·ω_libre + c`.

Se añaden `omega_1` y `gain` al resultado, que es lo que el contraste está
contrastando y antes no se veía.

## Test

`tests/test_bug_0071_wald_es_la_ganancia.py`

- `test_el_contraste_es_omega_de_uno_y_no_la_mezcla_con_delta`
- `test_la_ganancia_es_omega_uno_partido_delta_uno`
- `test_distingue_transitorio_de_permanente` — la premisa del nodo de
  episodios, medida como **tasa** sobre 15 realizaciones y no sobre un sorteo:
  potencia ≥ 0,80 con escalón permanente, tamaño ≤ 0,20 con dos impulsos.

Sobre serie sintética, ω(1) = −0,14 (p = 0,11, no rechaza) para dos impulsos en
el nivel, y ω(1) = +5,86 (χ² = 4071, p = 0,0000) para el escalón sostenido.
