---
id: BUG-0076
title: la lectura de la ganancia supone input ESCALÓN y no mira el tipo de entrada — sobre un impulso declara «permanente» un efecto que es nulo por construcción
status: fixed
severity: high
component: interventions
found_in: 0.1.12
fixed_in: 0.2.0 (unreleased)
reported: 2026-09-03
reporter: David / run 5 guiado sobre PGAS
tags:
  - intervention
  - gain
  - flt
  - input-type
references:
  - src/art/interventions.py (test_intervention — omega_1 / gain)
  - tests/test_bug_0076_gain_depends_on_input.md
  - BUG-0071 (donde se introdujo la lectura, suponiendo escalón)
---

## Summary

`test_intervention` calcula ω(1) = ω₀ − ω₁ − ⋯ − ω_s y lo presenta como
**ganancia a largo plazo**, con el contraste H₀: ω(1)=0 leído como
«transitorio frente a permanente».

Eso **sólo vale para un input ESCALÓN**. La lectura depende del tipo de entrada
y la herramienta no lo miraba:

| input | ν(1) = ω(1)/δ(1) es… | efecto permanente en el nivel |
|---|---|---|
| **escalón** | el desplazamiento permanente de nivel | ν(1) |
| **impulso** | el **área acumulada** de la respuesta | **0, por construcción** |

Con un impulso la entrada no persiste, así que la respuesta vuelve a cero
sea cual sea ω. El contraste H₀: ω(1)=0 sobre un impulso no contrasta
permanencia: contrasta si el área es nula, que es aproximadamente «si la
intervención vale algo».

## Repro

PGAS, una FLT sobre input impulso: `(ω₀ − ω₁B − ω₂B²) ξₜ^{I,Q3/2008}`

```
ω = [0.1813, -0.4263, -0.2250]
camino del nivel:  +0.1813 → +0.4263 → +0.2250 → +0.0000 → … → +0.0000
suma de la respuesta (área):  +0.8327
nivel en el retardo 40:       +0.0000
```

y la herramienta reportaba:

```
ganancia ω(1)=+0.8327   Wald χ²(1)=…  p=0.0000
H₀: ganancia nula ⇒ efecto TRANSITORIO  (se RECHAZA: efecto permanente)
```

**«Efecto permanente» sobre un modelo cuyo efecto permanente es cero por
construcción.**

## Cause

BUG-0071 introdujo la lectura correcta *para el caso que tenía delante* —N
escalones en el nivel, que es la forma general del nodo de episodios— y la
generalizó a toda intervención sin condicionar al tipo de entrada.

## La consecuencia de diseño, que es lo importante

**Elegir input impulso ES imponer la restricción de ganancia nula.** No son dos
parametrizaciones de lo mismo: el escalón deja la ganancia libre y el impulso la
fija en cero por construcción. Por tanto

    escalón con s+1 coeficientes   →  modelo SIN restringir
    impulso con s coeficientes     →  el mismo, CON ω(1)=0 impuesto

y la comparación entre los dos es un **contraste de razón de verosimilitudes con
un grado de libertad**, que es como debe presentarse. Sobre PGAS: LR = 3,197,
p = 0,0738 — no se rechaza, la restricción vale. En otros casos el estadístico
mandará volver al modelo sin restringir, y ésa es justamente la decisión que la
herramienta tiene que poner delante.

## Fix

`InterventionTestResult` distingue el tipo de entrada:

- `entrada` — "impulso" | "escalon" | "rampa", derivado de `itv.type`.
- `gain` sigue siendo ν(1) = ω(1)/δ(1), pero se **etiqueta** por lo que es en
  cada caso: desplazamiento permanente con escalón, área acumulada con impulso.
- `efecto_permanente` — ν(1) con escalón, **0.0 exacto** con impulso.
- la lectura «transitorio/permanente» sólo se emite con input escalón. Con
  impulso se dice que el efecto es transitorio **por construcción** y que el
  contraste de ω(1)=0 está contrastando el área, no la permanencia.

## Test

`tests/test_bug_0076_gain_depends_on_input.py`
