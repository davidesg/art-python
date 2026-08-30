---
id: BUG-0054
title: la alarma de estacionalidad residual se leía sobre residuos que no son ruido blanco — una estructura regular sin modelar se hace pasar por estacional, y empuja a meter armónicos en una serie que no los necesita
status: fixed
severity: medium
component: describe
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-29
reporter: carril Claude del RUN 2 — defecto (g) de su informe
tags:
  - diagnosis
  - seasonality
  - false-positive
references:
  - src/art/describe.py (describe_diagnosis — la alarma)
  - src/art/seasonal_detection.py (detect_seasonality)
  - tests/test_bug_0054_0055_avisos_legibles.py
  - bugs/BUG-0054-repro/repro.py
---

## Summary

`detect_seasonality` corre una regresión armónica con F de HAC. Aplicada a los
**residuos** de un modelo ajustado, hereda la regla que rige en todo lo demás:
sobre residuos que no son ruido blanco no es un contraste débil, **no es un
contraste**. La alarma se imprimía sin condición.

El mecanismo es inmediato en datos trimestrales: **el retardo 2 ES la frecuencia
de Nyquist** —el armónico semestral `(−1)^t`— así que una ACF(2) positiva sin
modelar entra en la regresión armónica exactamente como si fuera un patrón
estacional.

## Repro

```
modelo     Q p-min  blanco   F seas   p seas    ACF(1)   ACF(2)   alarma
m03         0.0358      NO     3.16   0.0293    +0.166   +0.152   SALTA
m04         0.8753      si     2.05   0.1139    +0.005   +0.006   -
```

`PGAS_m03` es un MA(1) que deja ACF(1)=+0,166 y ACF(2)=+0,152. Su Q rechaza, y la
alarma salta con F=3,16 (p=0,0293) — sobre una serie cuyo contraste en el **nodo
estacional** había dado F=0,669, p=0,5734.

`m04` corrige el orden a MA(2). **Las dos cosas se callan a la vez**, y no se
tocó nada estacional en ningún momento. Ésa es la demostración de que la alarma
era estructura regular disfrazada.

## Por qué importa

El analista que la lee sin sospecha previa mete armónicos en una serie que no
tiene estacionalidad, y a partir de ahí el modelo entero se desvía. En una serie
destinada a un sistema es peor todavía: armónicos espurios en una de las tres
rompen la comparabilidad que el objetivo multivariante exige.

## Fix

La alarma sigue apareciendo —suprimirla podría ocultar un problema estacional
real— pero cuando los residuos no son ruido blanco lleva la advertencia dentro,
nombra la causa (estructura REGULAR sin modelar), nombra el mecanismo (el
retardo `s/2` es Nyquist) y da el orden de trabajo: **corrige primero el ARMA
regular y vuelve a mirar; si la alarma era de eso, desaparece sola.**

Con residuos limpios no se imprime nada extra: la advertencia sólo aparece donde
hay algo que advertir.
