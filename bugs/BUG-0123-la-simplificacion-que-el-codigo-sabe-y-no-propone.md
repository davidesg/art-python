---
id: BUG-0123
title: test_interventions declara «no hay simplificación posible» cuando la hay — un escalón con ganancia nula es un impulso de un orden menos, y el código lo sabe pero no lo propone
status: fixed
severity: medium
component: interventions
found_in: 0.2.1
fixed_in: 0.2.1
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

**1 · La condición vive en el RESULTADO, no en el formateador.** `es_reducible(
alpha)` y `forma_reducida` son propiedades de `InterventionTestResult`, junto al
comentario que ya llevaba el álgebra. Es lo que falló: la regla estaba escrita
—bien— en prosa, y la función que tenía que usarla no la conocía. Ahora un sitio
que presente esto la **pregunta**; no la vuelve a deducir. Hay una prueba que lo
fija: si `simplify_summary` vuelve a comparar `entrada == "escalon"` por su
cuenta, falla.

Hizo falta un campo nuevo, `n_omega_total`: `omega` lleva sólo los **libres**, y
la forma reducida se cuenta sobre el operador entero.

**2 · Sección «Reducibles — imponer la restricción, no quitar»**, con el álgebra
en una línea, la forma equivalente concreta y la llamada que la construye. Y la
frase final sólo se imprime cuando **tampoco** hay reducibles.

**3 · El punto 3 del plan estaba MAL, y no se ha hecho.** Decía: con entrada de
impulso y ganancia **rechazada**, avisar de que la restricción no se sostiene.
No se puede. El Wald de un impulso contrasta si el **ÁREA** es nula, que es otra
pregunta (BUG-0076); rechazarla sólo dice que la intervención vale algo. Desde
el impulso la restricción de ganancia nula **no es contrastable** — está impuesta
por construcción y para juzgarla hay que estimar el escalón con un ω más y
comparar por LR.

Lo que se hace, entonces, es decirlo:

    *Las de entrada **impulso** llevan la ganancia nula **impuesta por
    construcción**, y este modelo no la contrasta — su Wald mira si el ÁREA es
    nula, que es otra pregunta. Para saber si la restricción se sostiene, estima
    el **escalón con un ω más** y compara por LR de 1 g.l. Es la ida del mismo
    camino, y se puede recorrer en los dos sentidos.*

Eso es lo que el analista pedía —«se puede ir hacia atrás y hacia adelante»— y
afirmar lo otro habría sido publicar un veredicto que el contraste no da.

**4 · Y se dice por qué importa más que un parámetro.** El escalón sostiene un
desplazamiento permanente del nivel que su propia ganancia dice que no existe, y
ese ω libre tiene que ir a alguna parte: de ahí las correlaciones de ±0,99 entre
los ω. En la forma de impulso la vuelta a la línea base es exacta **por
construcción**.

## Validation

`tests/test_bug_0123_reducir_no_es_quitar.py`.

Además de los casos fabricados —reducible, y las cuatro formas de no serlo: un
solo ω, ganancia rechazada, ya es impulso, sin Wald—, la prueba que de verdad
cierra esto **estima las dos formas** del mismo suceso sintético y comprueba el
álgebra:

    ESCALÓN ×3 :  ℓ = −850,4418   AIC = 1708,88   npar = 4   ω(1) = +2,80  p = 0,98
    IMPULSO ×2 :  ℓ = −850,4421   AIC = 1706,88   npar = 3

    LR = 0,0005  (1 g.l.)  p = 0,98      ΔAIC = −2,00

Un parámetro menos con la misma ℓ es ΔAIC = −2 **por definición**, y que salga
el número exacto es lo que distingue una equivalencia algebraica de una
coincidencia del ajuste. Es la misma forma que el analista midió a mano sobre
RATIO —LR = 0,04, ΔAIC = −1,95—, ahora reproducible.
