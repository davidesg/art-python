---
id: BUG-0034
title: chaining ARMA onto a fitted model drops the FIXED-FREQUENCY operators — _build_arma_on_model inherits interventions, ifadf and mu but never mentions ar_f/ma_f, so a MEG-reformulated model keeps its seasonal unit root and silently loses its MA_f witness
status: fixed
severity: high
component: pipeline
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-27
reporter: David / réplica TFM Bolivia
tags:
  - pre-contract
  - meg
  - seasonality
  - silent-loss
references:
  - src/art/pipeline.py (_build_arma_on_model)
  - src/art/mcp_server.py (confirm_and_estimate, base_pre_path)
  - src/art/mcp_server.py (meg_reformulate — quien añade el testigo)
  - bugs/BUG-0034-repro/repro.py
  - tests/test_bug_0034_fixed_frequency_operators_inherited.py
---

## Summary

`fue` guarda en bloques propios del `.inp` —**"AR(2)/MA(2) operators with fixed
frequency"**— los factores anclados a una frecuencia estacional. En el modelo
llegan como `m.ar_f` y `m.ma_f`, listas de `FixedFreqFactor`, **no** dentro de
`ar_s`/`ma_s`.

`_build_arma_on_model` —la función que sostiene `confirm_and_estimate(base_pre_path=…)`—
hereda `interventions`, `ifadf` y `mu`, y **no menciona `ar_f` ni `ma_f` en
ninguna parte**. Los pierde en todo encadenamiento.

## Por qué es grave: el testigo y la raíz unitaria son UN objeto

Ahí es donde vive el **testigo MA_f** que `meg_reformulate` añade junto a
`ifadf[f]=1`. Y no son dos ajustes independientes:

| | qué es |
|---|---|
| `ifadf[f]=1` + testigo MA_f libre | el **modelo S** de estacionalidad estocástica, el que contrasta el MEG |
| `ifadf[f]=1` **sin** testigo | la forma **AR-only**, que SOBREDIFERENCIA la estacional |

El propio docstring de `meg_reformulate` lo dice: *«with_witness=False gives the
AR-only form (no witness): this OVER-DIFFERENCES the seasonal (inflated σ,
exploded Q-test) and is only a diagnostic subproduct, NOT S»*.

Así que añadir un ARMA **regular** a un modelo reformulado por el MEG —pasar
`q=1` y no tocar nada más, que es lo natural— conservaba la raíz unitaria y
tiraba su testigo, produciendo exactamente la forma contra la que la
documentación avisa. **En silencio**: el pie de estado decía `ifadf f=1 ·
1 armónicos` y parecía correcto.

## Medido sobre RATIO (Gasto/PIB Bolivia)

Modelo reformulado por el MEG (`ifadf[1]=1` + testigo), al que se le quiere
añadir un MA(1) regular para cerrar el Q:

| | σ̂ₐ | ℓ | AIC | Q p-mín |
|---|---|---|---|---|
| partida (sin el MA regular) | 4.1153% | −232.20 | 474.40 | 0.0265 ✗ |
| **con el defecto** | 5.5173% | −254.60 | 519.21 | **0.0000** ✗ |
| **arreglado** | **4.0274%** | **−229.48** | **470.95** | **0.2730 ✓** |

El defecto no sólo degradaba el modelo: **era lo que impedía cerrar la serie**.
Con `ar_f`/`ma_f` heredados, el paso que el analista quería dar produce un modelo
adecuado — y sin él, la única salida aparente era volver atrás y quedarse con un
modelo cuya especificación estacional el MEG había declarado incorrecta.

## Repro

`bugs/BUG-0034-repro/repro.py` — serie trimestral con estacionalidad
**estocástica** (amplitudes de los armónicos como paseo aleatorio), semilla fija.
Construye el modelo S con `ma_f=[FixedFreqFactor(freq=1.0, …)]`, encadena un
MA(1) regular y comprueba si el testigo sigue ahí.

## Fix

`ar_f` y `ma_f` se copian como las intervenciones:

```python
# BUG-0034: los operadores de FRECUENCIA FIJA son estructura, no órdenes.
ar_f_val = list(m_base.ar_f or [])
ma_f_val = list(m_base.ma_f or [])
...
return fue.Model(..., ar_f=ar_f_val or None, ma_f=ma_f_val or None, ...)
```

**Sin interruptor, y a propósito.** `(p, q, P, Q)` nombran los operadores
regulares y los de retardo estacional; los de frecuencia fija son *estructura*,
igual que `ifadf` y las intervenciones. Un parámetro para apagarlos habría dado a
elegir entre dos modelos de los cuales uno no es un modelo, sino un subproducto
de diagnóstico.

## El camino equivocado que tomé primero, por si vuelve

La primera hipótesis fue que el testigo vivía en `ma_s` y que el defecto era que
`Q=0` lo borraba; llegué a implementar un `Q` de tres estados con centinela. **No
reprodujo nada sobre el caso real**, y por eso: `m.ma_s` estaba vacío y el
testigo estaba en `m.ma_f`. Lo dejo escrito porque el síntoma —"desaparece el MA
estacional al encadenar"— apunta con naturalidad al parámetro equivocado.
