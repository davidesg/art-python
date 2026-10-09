---
id: BUG-0224
title: DCD de subdiferenciación sin potencia con AR libre — bajo H₀ el AR va a ≈1 y reconstruye la ∇ cancelada; el texto dice «θ→+1» con θ̂ = −0.06
status: open
severity: high
component: formal-tests
found_in: 0.2.3.dev0 @088933d
fixed_in:
reported: 2026-10-07
reporter: David / Claude — revisión del paper de dolarización (Ecuador), Fase 1, componente Rc del ratio IT
tags:
  - dcd
  - subdiferenciacion
  - orden-de-integracion
  - par-confirmatorio
references:
  - src/art/formal_tests.py (dcd_underdiff_regular, ≈ l.858)
  - src/art/describe.py (veredicto `ud_res`, ≈ l.2750)
  - bugs/BUG-0045 (origen del contraste d−1)
---

## Summary

`dcd_underdiff_regular` añade un testigo MA(1) y compara el modelo libre con el
restringido θ = 1. Si el modelo tiene **AR regular libre**, en el restringido
el AR se va a la unidad (φ̂ ≈ 0.98) y **reconstruye la diferencia** que el MA
unitario acaba de cancelar: (1 − φB)∇ = (1 − B)·a con φ → 1 equivale otra vez
a ∇. La verosimilitud restringida apenas cae, el LR sale pequeño y el
veredicto es «con d−1 bastaba» aunque el testigo libre esté lejísimos de +1.

Además, el texto del veredicto se decide **sólo por el LR**: imprime «testigo
NO invertible (θ→+1)» con θ̂ = −0.06.

## Impact

- Con cualquier AR libre en el modelo, el lado d−1 del par en f = 0 pierde la
  potencia y tiende a declarar la ∇ cancelada: puede llevar a adoptar d − 1
  cuando la diferencia es genuina. En un análisis de cointegración eso cambia
  qué series son I(1).
- El mismo modelo sin AR da la respuesta contraria: el veredicto depende de un
  parámetro no significativo.
- El texto «θ→+1» contradice el θ̂ impreso en la misma línea.

## Reproduction

Datos: `/home/david/Dropbox/dolarization/Python/art_drvec/EXT/bop_components_q.csv`,
columna `Rc` (renta + transferencias recibidas, Ecuador, trimestral 2003T1–2019T4,
n = 68). Modelos copiados en
`/home/david/Dropbox/dolarization/Python/art_drvec/EXT/Rc/`:

- `Rc_m00`: ln Rc, d = 1, armónicos f = 1, 2, μ, sin ARMA.
- `Rc_m01_ar1`: lo mismo + AR(1) libre (φ̂ = 0.167, t = 1.4, no significativo).

```
formal_tests("Rc_m00.inp",     subdiferenciacion=True)
  → DCD sub-dif: θ̂ = −0.1626, LR = 157.698 → la ∇ es genuina ✓
formal_tests("Rc_m01_ar1.inp", subdiferenciacion=True)
  → DCD sub-dif: θ̂ = −0.0587, LR = 1.574 → «testigo NO invertible (θ→+1)
     → la ∇ está CANCELADA → con d−1 bastaba ✗»
```

Internos (replicando `dcd_underdiff_regular`):

```
Rc_m00     libre: AR 0 (fijo)  MA −0.163  ℓ −210.737 | H₀ θ=1: AR 0 (fijo)   ℓ −289.586  LR 157.7
Rc_m01_ar1 libre: AR 0.110     MA −0.059  ℓ −210.716 | H₀ θ=1: AR **0.979** ℓ −211.503  LR   1.57
```

El modelo libre es prácticamente el mismo en los dos casos (ℓ −210.74 frente a
−210.72); toda la diferencia está en el restringido, donde el AR libre se va a
0.979.

## Root cause

`formal_tests.py`, `dcd_underdiff_regular`: el modelo restringido `mk` fija
θ = 1 pero deja libres los AR regulares. Bajo H₀ el modelo es
(1 − φB)·∇N = (1 − B)·a ⇔ (1 − φB)·N = a (d − 1), y el optimizador puede
recuperar la ∇ con φ → 1. El contraste de H₀: θ = 1 queda no identificado
frente a «φ = 1 y θ = 1» (cancelación AR/MA en +1). Es la cuasi-cancelación
del par en f = 0 trasladada al lado d − 1.

`describe.py`: `ver_u` se elige con `ud_res.lr < c5u` sin mirar `coef_free`.

## Fix

1. En el restringido, **acotar la raíz AR dominante lejos de la unidad**
   (p. ej. |φ| ≤ ρ_m = 1 − 4/n, el mismo umbral de Shin-Fuller), o estimar el
   restringido como el modelo **d − 1 con su AR** y comparar contra él con la
   ley adecuada. Alternativa mínima: si en el restringido alguna raíz AR
   regular supera ρ_m, declarar el contraste **no concluyente** («el AR
   reconstruye la ∇: el lado d−1 no se puede leer con este modelo») en vez de
   «d−1 bastaba».
2. El veredicto textual debe usar también θ̂: «θ→+1» sólo si θ̂ está cerca de
   +1; con θ̂ lejos y LR bajo, decir que el LR es bajo porque el restringido se
   compensa por otro parámetro, y nombrarlo.
3. Informar en la salida el AR del modelo restringido (es lo que permite leer
   el resultado).

## Validation

- Rc_m01_ar1: con el AR acotado, LR del orden del de m00 (≫ 1.94) → ∇ genuina.
- Test sintético: paseo aleatorio + AR(1) 0.2 en la ∇ → d confirmado por abajo
  con y sin AR libre en el modelo.
- Test sintético: AR(1) estacionario 0.5 en niveles modelizado con d = 1 → el
  contraste sigue detectando que la ∇ sobraba.

## Addendum (2026-10-08) — batería de contrastes

En `research/bateria_contrastes_d.py`, el DCD de subdiferenciación con AR real libre y sin MA
se lanzó en 9 de los 21 modelos sin ninguna advertencia de esta pérdida de potencia. En esos
casos acertó («genuina»), porque la batería estima con la d verdadera; la fase 2
(docs/PLAN-bateria-orden-integracion-fase2.md) estimará con d+1 para medir cuántas veces dice
«d−1 bastaba» en falso. Mientras no se arregle, la salida debería avisar: «con AR libre y sin
MA, el lado d−1 pierde potencia (BUG-0224)». Repro: `bugs/BUG-0236-repro/repro.py`, bloque
«d=1 AR(1) .6». Árbol: docs/ARBOL-orden-de-integracion.md §4.

