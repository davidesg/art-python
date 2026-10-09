---
id: BUG-0230
title: La sección 4 ofrece «A) Adoptar este modelo — nada en la diagnosis pide cambiarlo» para modelos sobreparametrizados (φ̂₂ con t ≈ −1; ARMA(1,1) sin ningún coeficiente significativo), y la opción B «sobreparametrizar» llama a una herramienta que no añade parámetros
status: fixed
severity: medium
component: mcp-tools
found_in: 0.2.3.dev0 @088933d
fixed_in: 0.2.3.dev0
reported: 2026-10-08
reporter: David / Claude — análisis GUIADO del IPC de España (P02, Econometría Aplicada UCM)
tags:
  - decision
  - sobreparametrizacion
  - guiado
references:
  - src/art/mcp_server.py:2468-2504
  - bugs/BUG-0225-repro/repro.py
---

## Summary

IPC_ES, sobreparametrización del AR(1):
- m03 AR(2): φ̂₂ = −0,069 (e.t. 0,068); σ̂ₐ no baja; AIC y BIC peores. Sección 4: «**A) Adoptar
  este modelo** y cerrar el nodo. Nada en la diagnosis pide cambiarlo.»
- m04 ARMA(1,1): φ̂ = 0,17 (0,20), θ̂ = −0,27 (0,20), corr 0,94. La diagnosis lo marca («Posible
  sobreparametrización») y la sección 4 vuelve a ofrecer «A) Adoptar».
- La opción B, «Sobreparametrizar para comprobarlo — añadir un parámetro y ver si sale no
  significativo», propone `overparameterization_analysis`, que sólo lee la matriz de
  correlaciones del modelo ya estimado: no añade ningún parámetro.

## Impact

Invita a adoptar justo el modelo que la sobreparametrización acaba de descartar; y la opción B no hace lo que dice.

## Reproduction

`ART_NO_VIEWER=1 python bugs/BUG-0225-repro/repro.py` (recorre el carril guiado de `IPC_ES.inp`, 2002:01-2019:12, desestacionalizado, en un directorio temporal), bloque **0230**. Guion real del caso: `02-practicas/P02-gtkfue-inp-out/solucion_guiada/IPC_ES/IPC_ES_guion.json` del repositorio del curso.

## Root cause

El menú de decisión sólo mira la diagnosis de residuos (Q, JB), no la significación del último parámetro añadido ni el aviso de sobreparametrización que la misma salida imprime.

## Fix

Si el último coeficiente de algún polinomio tiene |t| < 2 (o la diagnosis marca sobreparametrización), la opción A debe ser «volver al modelo sin ese parámetro» (con su .pre). La opción B debe estimar de verdad las extensiones (p+1, q+1) o renombrarse «revisar correlaciones de los parámetros».

## Validation

Repro, bloque 0230: m03 no ofrece «Adoptar este modelo».

## Resolution (2026-10-08)

- New `_ultimos_no_significativos(model)`: the LAST coefficient of each single-factor regular polynomial with |t| < 2 (an intermediate zero is not flagged: an AR(4) with φ̂₂ ≈ 0 is still an AR(4)). With it, section 4 offers "Quitar lo que sobra" (back to the model without it, abandon this one) and no longer "Adoptar este modelo".
- Parameter correlation keeps fue's threshold, **0.7** (C engine: possible redundancy or a badly placed estimate), and the warning is ALWAYS given — now also in the decision section. On its own it does not remove anything: Salamanca ARMA(1,1), corr(φ̂, θ̂) = 0.75 with t = 27 and t = 8, keeps "Adoptar" with the warning in front (check by simplifying and over-fitting, and say in the guion why it stays). A first version of this fix raised the pair threshold to 0.9; the maintainer rejected it (8-oct-2026): the threshold is fue's and is not moved.
- Option "Sobreparametrizar para comprobarlo" now gives the two real extensions (`confirm_and_estimate(…, base_pre_path=<.pre>, p=p+1)` and `q=q+1`) instead of `overparameterization_analysis`, which only reads the parameter correlations.

Repro: `bugs/BUG-0225-repro/repro.py`. Tests: `tests/test_bug_0225_0231_guiado_ipc_es.py`.
