---
id: BUG-0163
title: Una intervención con δ no publica ni δ̂ ni la ganancia — la línea que las lleva sólo se imprime cuando hay Wald, y con forma racional lo normal es que no lo haya
status: open
severity: medium
component: interventions
found_in: 0.1.0
fixed_in:
reported: 2026-09-11
reporter: Claude (al medir BUG-0161)
tags:
  - intervenciones
  - flt
references:
  - BUG-0071
  - BUG-0072
  - BUG-0076
  - BUG-0161
---

## Summary

`InterventionTestResult.summary()` imprime la línea de ganancia sólo dentro de
`if self.wald_stat is not None`, y `wald_stat` se calcula sólo si hay **más de
un ω libre** (`if k > 1`). Con una forma racional lo típico es **un ω y un δ**
—ω₀/(1−δB)— así que k=1 y la línea no sale nunca.

Resultado, sobre un testigo con respuesta que decae (δ=0,6, ω₀=−8):

```
  [ 0] impulse[obs 71]        ✓
       ω[0]=-777.0862  SE=34.8713  t=-22.284  p=0.0000 **
```

Eso es todo. No aparece:

    δ̂    = 0,5692     ← el parámetro que DEFINE la forma
    ν(1) = −1803,63   ← la ganancia, calculada y guardada en `gain`

**El número está.** `test_intervention` lo computa —`gain = g / delta_1` con
`delta_1 = 1 − Σδᵢ`— y lo devuelve en el campo `gain`. Sólo no se imprime.

## Impact

La forma racional existe **para** su ganancia y su tasa de decaimiento. ω₀ solo
es el salto inicial, que es lo menos interesante: δ es la lectura sustantiva
—«el efecto se disipa a un 57 % por trimestre»— y ν(1) es el área acumulada.
Publicar ω₀ y callar los otros dos deja al analista con el único número que no
contesta a lo que preguntó.

Es medium y no high sólo porque hoy no se puede llegar aquí por la superficie
(BUG-0161). En cuanto se abra `n_delta`, es high.

## Repro

Determinista:

```python
itv = fue.Intervention("impulse", at=70, omega=[0.0], omega_free=[True],
                       delta=[0.0], delta_free=[True])
# … ajustar …
tr = test_intervention(m, 0)
assert tr.gain is not None            # pasa: −1803,63
assert f"{tr.gain:.2f}" in tr.summary()   # FALLA: no está en el texto
```

## Fix propuesto

Separar las dos condiciones, que hoy están fundidas en una:

* **la ganancia y δ(1) se imprimen siempre que haya δ o más de un ω** — son
  descriptivos, no un contraste;
* **el Wald se imprime cuando existe** (k>1), que es lo que hoy decide las dos
  cosas a la vez.

Y con δ presente, imprimir también δ̂ con su error típico y la tasa de
decaimiento en palabras: `art.ltf.operador_en_palabras(omega, delta, b)` ya la
sabe decir, y esta salida ya lo llama para las de más de un ω. Es el mismo
remedio de BUG-0066 —calcular la lectura en vez de pedir la resta mental— sin
aplicar al denominador.

Ojo con la lectura, que depende de la entrada (BUG-0076): con impulso ν(1) es el
ÁREA acumulada y el efecto permanente es cero por construcción; con escalón es
el desplazamiento permanente. `lectura_de_ganancia` ya lo distingue y basta con
usarla.

## Validation

Sobre el testigo de decaimiento: la salida trae δ̂ ≈ 0,57, ν(1) ≈ −1803 y dice
qué es cada uno. Y no cambia nada de lo que hoy sale para las formas sin δ.
