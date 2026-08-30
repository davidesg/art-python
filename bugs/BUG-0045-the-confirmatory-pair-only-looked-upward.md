---
id: BUG-0045
title: the confirmatory pair at f=0 only looked toward d+1 — nothing asked whether d−1 would have sufficed, and a model with no regular MA had no instrument at all
status: fixed
severity: medium
component: formal-tests
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-28
reporter: David / réplica TFM Bolivia — hallado por el experimento del chat limpio
tags:
  - dcd
  - integration-order
references:
  - src/art/formal_tests.py (dcd_underdiff_regular)
  - src/art/describe.py (describe_formal_tests — el par)
  - tests/test_bug_0044_0045_white_noise_and_the_lower_side.py
---

## Summary

El «par confirmatorio en f=0» presenta dos contrastes con nulas opuestas. Pero
los dos miran **en la misma dirección**:

* **Shin-Fuller** contrasta si el AR del modelo tiene raíz unitaria — o sea, si
  hace falta MÁS diferenciación.
* **`dcd_overdiff_regular`** impone una diferencia EXTRA y mira si su testigo se
  apila.

Los dos contestan «¿basta con la `d` que tengo, o necesito `d+1`?». **Ninguno
pregunta si con `d−1` habría bastado**, que es justamente la duda cuando la tabla
ADF/KPSS recomienda una `d` menor que la adoptada.

Lo dijo un analista sin contexto previo, sobre PGAS:

> «En PGAS la tabla ADF/KPSS recomienda d=0; aceptado d=1, la etapa formal
> concluye "el orden de integración no está en la banda ambigua". Pero ni el DCD
> ni Shin-Fuller contrastan d=1 frente a d=0 — ambos miran hacia d=2. La
> afirmación suena más fuerte de lo que los dos contrastes sostienen.»

Exacto, y era el caso en que más importaba: PGAS es la serie donde la tabla
recomendaba lo contrario de lo adoptado.

## El hueco, con precisión

Si la ∇ ya tomada era innecesaria, el modelo la cancela con un cero MA en +1:
`(1 − B)` contra `(1 − θB)` con θ→1. Así que el instrumento es el DCD sobre el MA
regular del modelo.

* Si el modelo **tiene** un MA regular libre, `dcd()` ya lo contrasta — sólo que
  nunca se presentaba como el lado `d−1` del par.
* Si **no** lo tiene —un AR(2) puro, que es exactamente PGAS— `dcd()` levanta
  `ValueError: No free regular MA(1) factors found`. **No había nada que mirar.**

## Fix

`dcd_underdiff_regular(model)`, simétrico de `dcd_overdiff_regular`: si el modelo
trae MA regular libre, lo contrasta; si no, **añade** un testigo MA(1) libre
inicializado en +0.85 —igual que el otro añade el suyo— y aplica el DCD.

```
θ → +1, NO invertible (LR < crít) ⇒ la ∇ está cancelada ⇒ d−1 bastaba
θ  <  1, invertible    (LR ≥ crít) ⇒ la ∇ es genuina    ⇒ d confirmado por abajo
```

Con `d = 0` devuelve `None`: no hay diferencia que cuestionar.

Y la conclusión del par deja de afirmar de más:

```
**DCD sub-diferenciación regular** — ¿sobraba la ÚLTIMA diferencia? (H₀: θ=1)
- θ̂=-0.2667, LR=5.881 (crít 5%=1.94) → la ∇ es genuina → d confirmado por abajo ✓

**Par confirmatorio en f=0**
  ✓ Los dos coinciden: el orden de integración no está en la banda ambigua.
  ✓ Y acotado por ABAJO: la última ∇ es genuina (LR=5.881 ≥ 1.94), así que d−1
    no habría bastado. Las dos direcciones cierran sobre la misma d.
```

Cuando el testigo de abajo **sí** se apila, lo dice y retira la conclusión: el
orden no está fijado y hay que estimar el candidato `d−1`. Y si no se pudo
contrastar, se advierte de que la conclusión acota por un solo lado.

## Nota sobre el test

Comprobarlo sobre UNA realización mide la suerte: el contraste tiene tamaño 5% y
la probabilidad de apilamiento de la ley s=1 es 0.6575, no 1. Medido sobre doce
series de ruido blanco diferenciadas de más: **10 se apilan en θ̂=+1 y 1 rechaza**
(≈8%, cerca del nominal). La primera semilla que probé fue precisamente la que
rechazaba — y habría hecho pensar que el código estaba mal.
