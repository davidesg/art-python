---
id: BUG-0030
title: decide_interventions places every autonomous intervention d+D*s periods early — it converts a 1-based index of the RESIDUAL series into a 0-based position of the ORIGINAL series with at_0 = obs - 1, and never receives d or D
status: fixed
severity: high
component: policy
found_in: 0.1.11
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-27
reporter: David / réplica TFM Bolivia
tags:
  - interventions
  - off-by-one
  - autonomous
references:
  - src/art/policy.py:316-335 (decide_interventions)
  - src/art/pipeline.py:825 (el llamador, que no pasaba el desfase)
  - bugs/BUG-0030-repro/repro.py
---

## Summary

`diag.extreme` devuelve índices **1-based sobre la serie de RESIDUOS**, que
empieza `d + D*s` observaciones después de la original. `decide_interventions`
los convertía a posición 0-based sobre la serie **ORIGINAL** con

```python
at_0 = obs - 1          # policy.py:331
```

y eso sólo sería correcto si las dos series arrancaran a la vez. La conversión
correcta es `obs - 1 + d + D*s`.

**Resultado: toda intervención que añade el carril autónomo cae `d + D*s`
períodos ANTES del anómalo que la disparó.** Un trimestre en un modelo con d=1;
**trece períodos** en un mensual con d=1 y D=1.

Y la forma del defecto es **estructural, no aritmética**: `decide_interventions`
no recibía `d` ni `D`, así que no podía hacer la conversión aunque quisiera.

## La inconsistencia, en una línea

El mismo índice recibe dos fechas distintas en dos partes del sistema:

```
diagnose dice:            obs 19, z=−3,91
  en residuos, eso es:    2008:Q4     <- lo que fue escribe en su .out
decide_interventions da:  at_0 = 18   (= obs − 1)
  en la serie, eso es:    2008:Q3     <- donde ART pone la intervención
```

## Impact

Alta, y **silenciosa**, que es lo que la hace peligrosa.

Un pulso de **nivel** colocado un período antes ajusta la **imagen especular** del
correcto. Medido sobre el sintético del repro, misma especificación y sólo
cambiando la fecha:

| | ω | t | logL |
|---|---|---|---|
| mal colocada (2008:Q3) | **+4,347** | +4,57 | −142,346 |
| bien colocada (2008:Q4) | **−4,353** | −4,58 | −142,315 |

**Signo invertido, magnitud casi idéntica, Δ logL = 0,03.** El coeficiente sale
grande y muy significativo en los dos casos, y la diagnosis no distingue. Nada
delata que se está modelando la fecha equivocada — con el signo contrario.

En el caso real (`ITCER`, corrida autónoma) ART informó *«obs 19 (z=−3.65) →
Añadidas: PULSE obs 19»* y acto seguido imprimió la intervención como
`Ξ^{I,Q3/2008}`, con ω = +2,8322 (t=1,89, ni siquiera significativo al 5%),
mientras el anómalo estaba en Q4/2008. El modelo **aprobó la diagnosis**.

**Cómo se encontró.** Comparando la corrida autónoma con la guiada sobre la misma
serie: la guiada situaba la intervención en Q4/2008 y la autónoma en Q3/2008,
partiendo del mismo anómalo. Sin esa comparación el defecto no se ve, porque cada
corrida por separado es internamente coherente y aprueba.

## Reproduction

```
python3 bugs/BUG-0030-repro/repro.py
```

Sintético y determinista (semilla 23): se **pone** un anómalo en la posición
0-based 19 de la serie original, que es 2008:Q4.

```
el anomalo se PUSO en la posicion 0-based 19 = 2008:Q4

diagnose lo encuentra en:   obs 19 (z=-5.86) de la serie de RESIDUOS
   y esa obs es la fecha:   2008:Q4      <- la deteccion es correcta

decide_interventions SIN el desfase:  at_0 = 18  ->  2008:Q3   <- el defecto
decide_interventions CON el desfase:  at_0 = 19  ->  2008:Q4   <- correcto
```

## Fix

```python
-def decide_interventions(extreme, existing_ats):
+def decide_interventions(extreme, existing_ats, offset: int = 0):
     ...
-        at_0 = obs - 1
+        at_0 = obs - 1 + int(offset)
```

y el llamador, `pipeline.run_full`, pasa el desfase que sólo él conoce:

```python
new_itvs = pol.decide_interventions(
    diag.extreme, [at for at, _ in extra_itvs],
    offset=int(d) + int(D) * int(ts.freq))
```

El parámetro es lo esencial del arreglo: sin él la función no tiene con qué
hacer la conversión, y la aritmética correcta no se puede escribir.

## El test dorado lo confirma — y midió cuánto costaba

`tests/golden/build_model_synth_b1.json` fijaba la salida del carril autónomo
sobre el sintético del proyecto, y el arreglo lo rompió. El diff **es** la
validación:

```
interventions: golden=[[STEP,60],[STEP,61],[PULSE,120]]
               actual=[[STEP,61],[STEP,62],[PULSE,121]]
loglik:  -1201.4  ->  -1176.1     (+25.3)
aic:      2432.8  ->   2382.2     (-50.6)
```

**Las tres intervenciones se desplazan exactamente +1 = d**, y el ajuste mejora
**50,6 puntos de AIC** sobre el propio caso de regresión del proyecto.

Es decir: el dorado llevaba fijada la colocación defectuosa, y ese fichero es la
medida de lo que costaba. Se regeneró, y este párrafo es la razón — un dorado que
cambia sin explicación escrita es peor que no tenerlo.

## Validation

`tests/test_bug_0030_intervention_offset.py`, 6 casos: que la **detección** es
correcta (el anómalo se encuentra en su fecha — el defecto está en traducir el
índice, no en encontrarlo); que sin el desfase cae un período antes y con él en
su fecha; que **el llamador lo pasa** (un arreglo que nadie usa no arregla nada);
que el carril autónomo de punta a punta coloca la intervención en la posición
donde se puso el anómalo; y un test de **por qué era silencioso** — que las dos
colocaciones dan signos opuestos, magnitudes iguales y verosimilitudes
indistinguibles.
