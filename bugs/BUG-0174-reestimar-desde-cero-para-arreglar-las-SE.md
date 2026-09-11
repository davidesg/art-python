---
id: BUG-0174
title: Reestimar con las semillas a CERO para arreglar los errores típicos — funciona por suerte, puede caer en otro óptimo y destruye el convenio del `.pre`
status: fixed
severity: high
component: estimation
found_in: 0.2.1
fixed_in: 0.2.1
reported: 2026-09-12
reporter: David — run 4 de IPC_ES, sin contexto
tags:
  - errores-tipicos
  - contrato-de-ficheros
  - semillas
references:
  - BUG-0027
  - BUG-0090
  - BUG-0151
  - BUG-0159
  - fue/BUG-0015
---

## Summary

En el run 4 —hecho sin contexto— el asistente detectó bien el problema y propuso
una maniobra peligrosa. Del guion:

> *«m06 convergió en 6 iteraciones desde las semillas de m05 y varios SE quedaron
> junto a la semilla del BFGS. **Se reestima desde cero** para verificar el
> óptimo y obtener SE fiables.»*
>
> decisión: *«m06 reestimado desde semillas neutras (armónicos/Easter/μ=0,
> φ=0.1, testigos MA_f=−0.5)»*

**El diagnóstico era correcto.** Sobre `m06` (n=216), la semilla del BFGS es
√(2/n) = 0,09645, y **5 de los 12 errores típicos estaban a menos del 5 % de
ella**:

    0.09719  0.09457  0.09498  …  0.09543  …  0.09750

Tras reestimar: **0 de 12**. Y las SE se mueven entre **×0,29 y ×2,23** — cinco
parámetros más allá de ±60 %.

**Y la maniobra funcionó… sin que nadie lo comprobara:**

    ℓ  m06   −12.5554578499
       m06z  −12.5554578512        Δ = 1,3 × 10⁻⁹

## El problema no es que fallara: es que funcionó sin verificación

Dos objeciones, distintas y las dos ciertas.

**1 · De riesgo.** Con las semillas a 0 el optimizador arranca **fuera de la
cuenca** del óptimo conocido y puede caer en otra. En una superficie con
fronteras de MA —que es donde vive el testigo del MEG— eso no es hipotético. Un
óptimo distinto con ℓ mejor sería **otro modelo**, no el mismo mejor estimado, y
se adoptaría creyendo que se ha «verificado» el anterior.

**2 · De convenio, y es la grave.** Si la práctica pasa a ser «pon las semillas a
0 y reestima para tener SE fiables», el `.pre` deja de ser lo que es. Su
invariante —*corre fue sobre un `.pre` y los números no se mueven*— y la cadena
`.inp(t−1) → .pre(t−1) → .inp(t)` sólo significan algo si cada eslabón **arranca
donde acabó el anterior**. Reestimar desde cero en cada paso convierte la
construcción incremental en una serie de ajustes independientes: se pierde el
método, no sólo la semilla.

Palabras del analista: *«poner en 0 puede ir a un óptimo global y destruye el
convenio del `.pre`»*.

## Fix propuesto (hecho — ver §Fix)

**Perturbar POCO, no poner a cero, y verificar ℓ.**

Un desplazamiento pequeño desde el óptimo fuerza iteraciones reales sin salir de
la cuenca: el optimizador trabaja, la covarianza se construye sobre un camino de
verdad, y el punto de partida sigue llevando la información del `.pre`.

Y la comprobación que aquí faltó, que es la que convierte la suerte en evidencia:
**comparar ℓ**. Tres desenlaces, y sólo uno sirve:

| | |
|---|---|
| \|Δℓ\| ≤ tol | **verificado** — mismo óptimo, las SE nuevas son las buenas |
| ℓ mejora | el `.pre` **no era el óptimo**. Es un hallazgo, no un éxito |
| ℓ empeora | la corrida en frío **no llegó**; sus SE no valen |

La escala natural de la perturbación es el propio error típico del parámetro:
`v ± k·SE`. Con k≈1 se arranca a una desviación típica del óptimo — lejos para
que el optimizador tenga que trabajar, cerca para no cambiar de cuenca.

## Fix

`pipeline.reestima_en_frio(pre, out, k=1.0, tol=1e-5)` y la herramienta
`verify_optimum`. Perturba cada parámetro libre **una desviación típica**
—`v ± k·SE`, signos alternos, determinista— reestima y compara ℓ. Sobre los dos
modelos del run 4:

    m06   veredicto verificado   Δℓ = −5,0e-12   iteraciones  8 → 17
          SE en la semilla del BFGS:  3 → 0  de 12
    m03   veredicto verificado   Δℓ = +4,5e-11   iteraciones 10 → 20
          SE en la semilla del BFGS:  3 → 0  de 14

El mismo resultado que poner las semillas a cero, **sin salir de la cuenca y
comprobándolo**.

La perturbación es determinista a propósito: un instrumento de verificación que
no se puede repetir no verifica. Y los operadores se acotan a ±0,98 para no
salir de la región admisible al perturbar.

### Qué verifica exactamente

Que **el arranque perturbado llega al mismo óptimo que el arranque en caliente**.
NO que los valores guardados en el `.pre` sean óptimos: `fue` los reajusta al
cargarlos, así que un `.pre` que mintiera daría «verificado» igualmente. Para eso
está el invariante del convenio —reejecutar un `.pre` no mueve los números—, que
es otra pregunta.

Se descubrió al construir la prueba negativa, que no funcionaba por esto. Queda
dicho en el docstring porque la confusión es fácil.

## Validation

`tests/test_bug_0174_verificar_el_optimo_sin_destruir_el_pre.py`, más el caso
real del run 4. Las que sostienen el arreglo:

* **no pone las semillas a cero** — se comprueba que el punto de partida
  perturbado sigue en el orden de magnitud del óptimo, que es el defecto entero;
* **hace trabajar al optimizador** — `niter` sube, que es de donde sale una
  covarianza de verdad;
* **es determinista** — dos ejecuciones dan el mismo ℓ y las mismas iteraciones;
* y **el veredicto depende de Δℓ**: con una tolerancia imposible deja de decir
  «verificado», y distingue «mejora» de «no llegó», que no son lo mismo ni se
  arreglan igual.

La rama negativa se prueba **apretando la tolerancia**, no construyendo una
verosimilitud multimodal: eso es otra investigación, y lo que aquí hay que
garantizar es que el veredicto no sea decorativo.
