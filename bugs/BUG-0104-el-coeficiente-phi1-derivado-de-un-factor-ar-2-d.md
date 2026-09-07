---
id: BUG-0104
title: El coeficiente phi1 DERIVADO de un factor AR(2) de frecuencia fija se imprime como 1 en la ecuación — el .out trae su valor y la ecuación publicada no es el modelo estimado
status: fixed
severity: medium
component: describe/equation
found_in: 0.2.0.dev0
fixed_in: 0.2.0.dev0
reported: 2026-09-06
reporter: David / sesión UEM_HCPI_0219 — m04 con dos factores AR(2) de frecuencia fija
tags:
  - ecuacion
  - ar_f
  - frecuencia-fija
references:
  - fue/src/fue/model.py:9-33 (FixedFreqFactor: phi1 = 2*cos(2*pi*freq/sper)*sqrt(-phi2), derivado, no estimado)
  - src/art/describe.py (render de la ecuación — el factor f-fijo)
  - bugs/BUG-0012-... (mismo daño: la ecuación impresa no es el modelo ajustado)
---

## Summary

Un factor AR(2) de frecuencia fija tiene la forma `1 − φ₁B − φ₂B²` con
**φ₁ = 2·cos(2π·f/s)·√(−φ₂) derivado** y sólo φ₂ estimado. El bloque de la
ecuación imprime el término en B **sin su coeficiente**, es decir como si
φ₁ = ±1, cuando su valor real es otro. El `.out` sí lo trae bien.

En UEM_HCPI m04 (s=12, dos factores f-fijos):

    ecuación publicada:   (1 + B + 0.5267·B²)_f=4   (1 − B + 0.5846·B²)_f=2
    .out (correcto):      φ₁ = −0.725732             φ₁ = +0.764600
    o sea:                (1 + 0.7257B + 0.5267B²)   (1 − 0.7646B + 0.5846B²)

## Impact

Medio. No afecta a la estimación —el motor usa el valor correcto, y la
verosimilitud, la σ̂ₐ y los criterios de información son los del modelo bueno—,
pero **la ecuación publicada no es el modelo ajustado**, que es el daño de
BUG-0012.

Y el número que se pierde no es inocuo: φ₁ y φ₂ determinan juntos el
amortiguamiento del ciclo. Leído literalmente, `1 + B + 0.5267B²` tiene sus
raíces en módulo 1.378 y un φ₁ de módulo 1; el factor verdadero,
`1 + 0.7257B + 0.5267B²`, es el mismo módulo pero con φ₁ = 0.726. Un analista
que copie la ecuación para reproducir el modelo, o que juzgue la persistencia
del ciclo estacional a ojo, se lleva un factor que no es el estimado —
precisamente en el paso donde el factor f-fijo se usa para decidir si una
frecuencia es estacional y con qué amortiguamiento entra al MEG.

## Reproduction

Estimar cualquier modelo con `ar_f` no vacío y comparar el bloque de la
ecuación con el `.out`. Caso de referencia en el repo del analista:

    cases/UEM_HCPI_0219/work/UEM_HCPI_0219_m04_ffix.inp

cuya ranura f-fija es `2 4.000000 2.000000` con φ₂ sembrados en −0.62156 y
−0.61076. El `.out` imprime, correctamente y en dos líneas por factor, el φ₁
derivado (sin error típico, porque no se estima) y el φ₂ con el suyo:

    Coefficients for regular f-fixed AR factor 1 [f = 4.0]:
          -0.725732
          -0.526687  (0.096689) [15]

Comprobación aritmética: 2·cos(2π·4/12)·√0.526687 = −0.72573. ✓

## Root cause

El render de la ecuación trata el factor f-fijo como si sólo tuviera el
parámetro estimado (φ₂) y emite el término en B con coeficiente implícito 1,
en vez de calcular el φ₁ derivado —que es determinista dados `freq`, `sper` y
φ₂— o de leerlo de donde el motor ya lo dejó escrito.

## Fix

Calcular φ₁ = 2·cos(2π·freq/sper)·√(−φ₂) al componer el factor e imprimirlo
como cualquier otro coeficiente, **sin error típico** y marcado como derivado
(no es un parámetro libre: no consume grado de libertad y no debe contarse como
tal en el LR). El `.out` ya usa esa presentación de dos líneas y puede servir
de referencia.

## Validation

Un test que estime un modelo con `ar_f` y compruebe que el coeficiente en B de
la ecuación coincide con `2*cos(2*pi*freq/sper)*sqrt(-phi2)` y con el valor del
`.out`, con tolerancia de impresión.

---

## Cierre (2026-09-07)

Confirmada la aritmética contra el motor: φ₁ = 2·cos(2πf/s)·√(−φ₂), y el render
ponía **sólo el 2·cos** —que en s=12 vale exactamente 1 para f=2 y f=4— comiéndose
el √(−φ₂). De ahí que el término saliera como si su coeficiente fuese 1.

Verificado de extremo a extremo con dos factores de frecuencia fija estimados:

    .out          φ₂(f=4) = −0.994393   φ₂(f=2) = −0.975770
    φ₁ derivado         −0.997193              +0.987811
    ecuación      (1 + 0.9972·B + 0.9944·B²)_f=4 (1 − 0.9878·B + 0.9758·B²)_f=2

φ₁ va **sin error típico**, que es lo correcto: no se estima, se deriva. Y f=3 en
mensual sigue sin término en B, porque ahí 2·cos vale 0.
