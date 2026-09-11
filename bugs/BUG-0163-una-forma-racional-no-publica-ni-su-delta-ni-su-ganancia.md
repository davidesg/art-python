---
id: BUG-0163
title: Una intervención con δ no publica ni δ̂ ni la ganancia — la línea que las lleva sólo se imprime cuando hay Wald, y con forma racional lo normal es que no lo haya
status: fixed
severity: medium
component: interventions
found_in: 0.1.0
fixed_in: 0.2.1
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

## Fix

**1 · Las dos condiciones se separan**, que era el defecto:

* **ν(1) y δ(1) DESCRIBEN** — se imprimen si hay δ o más de un ω;
* **el Wald CONTRASTA** — se imprime cuando existe, y ahora con su H₀ en la
  etiqueta (`H₀: ω(1)=0`), que antes se leía sólo en la línea de abajo.

**2 · El resultado LLEVA el denominador.** `delta`, `delta_se` y `delta_1` son
campos de `InterventionTestResult`. Antes `delta_1` se calculaba para dividir y
se tiraba, y los δ ni se miraban — así que ningún consumidor podía publicarlos
aunque quisiera.

**3 · Y la tasa de decaimiento va en palabras**, que es la lectura que ω₀ no
tiene:

    δ[1]=+0.5692  SE=0.0568
    δ(1)=+0.4308   respuesta que DECAE a un 57 % por período
    ω(1)=-777.0858   ν(1)=ω(1)/δ(1)=-1803.6225   [área acumulada de la respuesta]

La etiqueta de ν(1) sale de `lectura_de_ganancia`, que ya distinguía impulso de
escalón (BUG-0076): con impulso es el ÁREA y el efecto permanente es cero por
construcción.

**4 · Y δ(1)→0 se avisa.** Es la ganancia sin acotar: el modelo es inadmisible y
el número que se publicaría no significa nada.

## Validation

`tests/test_bugs_0161_0163_el_denominador.py`. Sobre el testigo de decaimiento,
construido por la superficie: δ̂ con su SE, ν(1) **con el Wald ausente** —que es
el defecto entero, porque con un ω no hay Wald—, la tasa en palabras, y el aviso
de δ(1)≈0. Más dos de lo que no puede cambiar: una intervención SIN δ no cambia
de aspecto, y el Wald sigue diciendo su H₀.
