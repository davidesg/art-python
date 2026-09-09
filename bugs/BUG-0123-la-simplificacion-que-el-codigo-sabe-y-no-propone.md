---
id: BUG-0123
title: test_interventions declara «no hay simplificación posible» cuando la hay — un escalón con ganancia nula es un impulso de un orden menos, y el código lo sabe pero no lo propone
status: open
severity: medium
component: interventions
found_in: 0.2.1
fixed_in:
reported: 2026-09-08
reporter: David
tags:
  - intervenciones
  - simplificacion
  - ganancia
references:
  - BUG-0071
  - BUG-0072
  - BUG-0076
  - BUG-0086
---

## Summary

`simplify_interventions` conoce **un solo** tipo de simplificación: quitar una
intervención entera que no sea significativa. Cuando todas lo son, cierra con

    *Todas las intervenciones son significativas — no hay simplificación posible.*

y eso es **falso** siempre que una intervención con entrada de escalón y dos o
más ω libres tenga la ganancia nula sin rechazar. Ahí no hay que **quitar** nada:
hay que **reducir**.

La fórmula está escrita en el propio módulo, en `interventions.py:275`, sobre el
campo `entrada` de `InterventionTestResult`:

> *«De ahí una consecuencia de diseño: **elegir input impulso ES imponer la
> restricción de ganancia nula**. Escalón con s+1 coeficientes e impulso con s
> son el mismo modelo con y sin esa restricción, y la comparación entre ellos es
> un LR de un grado de libertad.»*

Es álgebra elemental: si ω(1)=0 entonces (1−B) divide a ω(B), o sea
ω(B) = (1−B)·ψ(B) con ψ de un orden menos, y como I_t = (1−B)S_t,

    ω(B)·S_t  =  ψ(B)·(1−B)·S_t  =  ψ(B)·I_t

El programa **calcula el contraste** —lo imprime tres líneas más arriba, con su
Wald y su veredicto TRANSITORIO— y luego declara que no hay nada que hacer con
él. El conocimiento está en un comentario y no llega a ser comportamiento.

## Impact

**Medio, y sistemático: se pierde un grado de libertad cada vez.** No es un
error de cálculo sino una simplificación que no se ofrece, así que sólo la
encuentra quien ya sabe la fórmula — y el sitio donde el programa tenía que
decírsela al que no la sabe es exactamente éste.

Medido en la réplica de Bolivia, RATIO, `run5_guiado`, 8-sep. Sobre `m20` y
sobre `m31`, el mismo bloque imprimía las dos cosas:

    ω(1)=-0.9854   Wald χ²(1)=0.025  p=0.8741
    H₀: ganancia nula ⇒ efecto TRANSITORIO  (no se rechaza)
    …
    *Todas las intervenciones son significativas — no hay simplificación posible.*

La simplificación que decía no existir —escalón de 3 ω en Q2/2020 → impulso de
2 ω— vale, medida estimando las dos:

| | m31 (escalón ×3) | m41 (impulso restringido) |
|---|---|---|
| ω de 2020 | 3 | **2** |
| ℓ | −234,69 | −234,71 |
| AIC | 485,38 | **483,43** |
| BIC | 504,74 | **500,36** |
| colinealidad | corr(ω,ω_l1) = −0,993 · corr(ω,ω_l2) = +0,996 | **sin advertencia** |

LR = 0,04 con 1 g.l. (p ≈ 0,84): la restricción **no cuesta nada** y devuelve
1,95 de AIC, 4,38 de BIC y una covarianza sana. Y además arregla lo que el
modelo *afirmaba*: `m31` sostenía un desplazamiento permanente del nivel de
−1,16 que nadie creía y que estaba ahí sólo porque un parámetro libre tenía que
ir a alguna parte; en `m41` la vuelta a la línea base es exacta por
construcción.

La encontró el analista, no el programa.

## Root cause

`simplify_summary` (`interventions.py:595-614`) tiene una sola rama: `nosig` no
vacía → sugerir eliminar; `nosig` vacía → «no hay simplificación posible». La
condición de reducibilidad —`entrada == "escalon"` y `len(omega libres) ≥ 2` y
`wald_p >= alpha`— está toda disponible en el `InterventionTestResult` que la
función ya tiene delante.

Es la enfermedad recurrente de este proyecto en una variante nueva. No es un
concepto escrito dos veces con una copia atrasada: es un concepto escrito **una
vez, y sólo en prosa**, que nunca se conectó con la función que tenía que
usarlo.

## Fix

*(propuesto, no aplicado)*

1. En `simplify_summary`, sección nueva **«Reducibles — imponer la
   restricción»** para cada resultado con entrada escalón, ≥2 ω libres y
   ganancia nula no rechazada. Con la forma equivalente concreta —«impulso con
   s ω en la misma fecha»—, la llamada que la construye, y el aviso de que el
   LR de la restricción es de 1 g.l.
2. Corregir la frase final: «no hay simplificación posible» sólo puede
   imprimirse cuando tampoco hay reducibles.
3. Simétricamente, con entrada de impulso y ganancia **rechazada**, el aviso
   inverso: la restricción no se sostiene y la entrada correcta es el escalón.

## Validation

*(pendiente)* Repro sintético con dos `InterventionTestResult` fabricados —uno
reducible y uno no— comprobando qué dice el resumen en cada caso; y una prueba
de regresión sobre el caso medido, que la frase «no hay simplificación posible»
no aparezca cuando hay un escalón con ganancia nula.
