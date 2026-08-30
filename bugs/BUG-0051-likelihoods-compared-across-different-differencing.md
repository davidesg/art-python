---
id: BUG-0051
title: se comparaban loglik/AIC/BIC entre modelos con diferenciación distinta — ifadf se caía del spec, así que la transformación era invisible en la ecuación, en el diff y en el anidamiento, y el LR llegó a salir negativo
status: fixed
severity: high
component: mcp-server
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-29
reporter: carril Claude del RUN 2 — defecto (e) de su informe
tags:
  - comparison
  - integration-order
  - likelihood
references:
  - src/art/guion.py (_extract_spec, _build_equation)
  - src/art/mcp_server.py (_spec_diff, _nested_relation, compare_versions)
  - tests/test_bug_0051_comparabilidad_de_verosimilitudes.py
  - bugs/BUG-0051-repro/repro.py
---

## Summary

`_extract_spec` construía el diccionario de especificación **sin `ifadf`**, la
diferenciación por frecuencia. Y `ifadf` es tanto una transformación de los datos
como la `D`: con `ifadf=[0,1,0]` sobre una serie trimestral el modelo no explica
`∇ln y` sino `(1+B²)∇ln y` — otra variable dependiente, otro número efectivo de
observaciones, otra escala de verosimilitud.

Al caerse del spec, se caía de todo lo que lo usa:

| dónde | qué pasaba |
|---|---|
| `_build_equation` | escribía `∇[ln y_t]` para los dos modelos: la diferencia era **invisible** |
| `_spec_diff` | recorría `d, D, p, q, P, Q, n_harmonics` — ni `ifadf` ni `lam` |
| `_nested_relation` | comparaba `d` y `D`, nunca `ifadf` ni `lam` |
| `compare_versions` | publicaba ΔAIC y ΔBIC como si significaran algo |

## El caso real

`RATIO_m03` (∇ln y) frente a `RATIO_m06` ((1+B²)∇ln y):

```
loglik  m03= -238.420   m06= -232.200
AIC     m03=   488.84   m06=   474.40   (Δ=-14.44)
sigma_a m03=  4.20525   m06=  4.20091   (Δ=-0.00434)  ← practicamente IGUAL
LR = 2*(m03 - m06) = -12.441   ← NEGATIVO
```

Tres señales de que algo va mal, y ninguna se recogía:

1. **14,4 puntos de AIC de «mejora» con σ̂ₐ idéntica.** Una mejora de ajuste real
   no puede dejar la desviación típica residual donde estaba.
2. **La diagnosis de `m06` FALLA** (Q ✗) y aun así «gana».
3. **El LR sale negativo.** Entre modelos anidados es imposible —el más rico no
   puede ajustar peor— así que un LR negativo no es «una mejora no
   significativa»: es la demostración de que el anidamiento o la escala están
   mal. Se imprimía como `p=1.0000` y se seguía.

Una lectura ingenua del AIC adopta el modelo **peor**, con la diagnosis rota, y
además cambia el orden de integración de la serie — que en este proyecto es la
decisión de la que depende que las tres series sean montables en un VECM.

## Fix

* `_extract_spec` lleva `ifadf`.
* `_build_equation` nombra el factor de cada frecuencia activa: `f=0 → (1−B)`,
  Nyquist → `(1+B)`, interiores → `(1 − 2cos(ω_f)B + B²)`. En trimestral con
  `f=1` sale `(1+B²)`, porque `2cos(π/2)=0`; en mensual, `(1−1.732B+B²)`.
* `_spec_diff` anuncia los cambios de `ifadf` y de `lam`.
* `_nested_relation` exige que **todo** el operador de diferenciación coincida —
  `lam`, `d`, `D`, `ifadf`— antes de declarar anidamiento.
* `compare_versions` comprueba la comparabilidad: si el operador difiere,
  **suprime** los Δ de loglik/AIC/BIC (quedan como `— no comp.`), explica por
  qué, y remite a lo que sí es comparable: la diagnosis, σ̂ₐ en unidades de la
  serie, la previsión fuera de muestra, y `formal_tests` si lo que se decide es
  el orden de integración.
* Red de seguridad: un LR negativo se rotula **IMPOSIBLE** en vez de publicarse
  con su p-valor.

σ̂ₐ y `npar` conservan su Δ: la primera está en unidades de la serie y la segunda
es un recuento.

## Después del arreglo

```
**Cambios (A→B)**: n_harmonics: 1→0, ifadf: [0, 0, 0]→[0, 1, 0]

> ⚠ loglik, AIC y BIC NO son comparables entre estos dos modelos. [...]

| loglik | -238.420 | -232.200 | — no comp. |
| AIC    |   488.84 |   474.40 | — no comp. |
| σ_a    |  4.20525 |  4.20091 |   -0.00434 |

Modelos no anidados — test LR no aplicable.
```
