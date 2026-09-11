---
id: BUG-0168
title: El aviso de las SE publicaba una magnitud de sesgo que ningún algoritmo calcula — y el LLM la repetía como si fuera una medida
status: fixed
severity: high
component: diagnosis
found_in: 0.1.0
fixed_in: 0.2.1
reported: 2026-09-11
reporter: David — run 3 de SF_MEG
tags:
  - errores-tipicos
  - avisos
  - numero-inventado
references:
  - BUG-0027
  - BUG-0090
  - BUG-0124
  - BUG-0166
  - fue/BUG-0015
---

## Summary

> *«El LLM sistemáticamente está observando los SE. Esto confunde: aparentemente
> está calculando el sesgo, pero ¿cómo lo hace? No tiene ningún algoritmo para
> calcular el sesgo de los SE. Lo único que puede calcular es cuando no hay
> estructura ARMA.»*

No lo calcula. **Repite nuestras cifras.** `AVISO_SE_DESDE_PRE` —que art pega
junto a cada tabla de errores típicos— publicaba cinco números con aspecto de
magnitud:

    «la desviación llega al menos a **4.23×** del valor correcto»
    «se han observado desde **0.46×** hasta **4.23×** sobre modelos distintos»
    «dos armónicos pasan de |t| = **3.02** y **2.83** a **1.31** y **1.28**»

…y a continuación: *«no hay corrección posible ni cota conocida»*. Las dos cosas
a la vez no se sostienen. **Un número que no se puede aplicar, puesto al lado de
un error típico, se aplica.**

## Dos intentos, y la lección

El proyecto ya rozó esta esquina. La primera versión decía «entre 0.46× y 3.47×»,
se leyó como una cota, y el arreglo fue **añadir «al menos»** y una tercera cifra.
Se atacó la FORMA —rango contra cota— y no el fondo: publicar una magnitud de
sesgo que nadie ha calculado. Había hasta una prueba fijándola
(`assert "4.23×" in AVISO_SE_DESDE_PRE`), o sea que **la suite guardaba
justamente lo que sobraba**.

## La asimetría

art publicaba lo que **no puede** calcular y se callaba lo que **sí** puede:

* **No calculable.** Cuánto se desvía la covarianza del BFGS. Es un subproducto
  del CAMINO del optimizador: depende de por dónde se pasó, no de una cantidad
  estimable. No es un sesgo con magnitud, es ruido sin cota.
* **Calculable, y estaba escrito pero no computado.** Sin ARMA el estimador de μ
  es la media muestral y su error típico es **σ̂/√n**, con forma cerrada — sin
  optimizador, sin hessiano y sin camino. `AVISO_COV_CASI_SEMILLA` lo NOMBRABA
  («la desviación típica residual dividida por √n») y no lo calculaba.

## Fix

**1 · El aviso deja de publicar magnitudes**, y dice por qué no las hay: quitar
las cifras sin la razón haría pensar que se olvidó medirlo.

**2 · `diagnosis.se_exacta_de_la_media(model)`** devuelve σ̂/√n cuando procede y
`None` cuando no. El bloque de la ecuación lo imprime **junto al publicado**:

    ℹ **Sin ARMA, el error típico de μ tiene forma cerrada**: σ̂/√n = 4.348631,
    frente a 4.334014 publicado arriba. Es el único de esta familia que se puede
    calcular en vez de sospechar. Úsalo.

**3 · Y apunta a la raíz**: `fue/bugs/BUG-0015`.

### Dos trampas al implementarlo, las dos ya conocidas en el repo

* **Contar la PRESENCIA del ARMA y no si es LIBRE.** `_write_inp` deja
  `ar=[[0.0]]` con el coeficiente fijo en cero, que no es estructura: es un hueco
  declarado. La primera versión se apagaba en el caso más común —la media sola—
  que es justo para el que existe. Es BUG-0166 otra vez, en otro sitio.
* **`np` no está a nivel de módulo en `mcp_server`.** La comparación con el valor
  publicado caía en un `except` mudo y sólo salía la mitad del aviso.

## Validation

`tests/test_bug_0168_el_aviso_no_inventa_un_sesgo.py`: el aviso no contiene
ningún factor `N×` ni ninguna razón t; dice por qué no hay magnitud; conserva lo
que sí afirma. Y σ̂/√n se calcula sin ARMA libre, devuelve `None` con ARMA libre
o sin media, **no** se apaga por un AR fijo en cero, y el bloque lo imprime con
el publicado al lado.

La prueba del contrato que exigía `4.23×` se reescribe **al revés**: ahora
comprueba que no haya ninguna magnitud.
