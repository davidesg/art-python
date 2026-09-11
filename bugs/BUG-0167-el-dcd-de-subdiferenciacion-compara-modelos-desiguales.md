---
id: BUG-0167
title: El DCD de subdiferenciación colapsa el AR contra la raíz unitaria — de los 39,9 puntos de LR, 38,3 son dinámica perdida y no evidencia sobre la frontera
status: fixed
severity: high
component: formal-tests
found_in: 0.1.0
fixed_in: 0.2.1
reported: 2026-09-11
reporter: David — run 3 de SF_MEG, «este contraste no tiene sentido, revisa la lógica»
tags:
  - contrastes-formales
  - dcd
  - orden-de-integracion
references:
  - BUG-0011
  - BUG-0045
---

## Summary

`dcd_underdiff_regular` pregunta si sobraba la última diferencia. Bajo H₀ θ=1 el
factor MA cancela la ∇ y el modelo colapsa:

    (1−φB)(1−B)y = (1−B)a + det     ⟹     (1−φB)y = a + det'

O sea **d=0**. Y si la serie es I(1), ese φ **tiene que irse a 1** para imitar la
diferencia — con lo que **no queda ningún AR para la dinámica de ∇y**.

El brazo libre conserva su AR(1) *y además* recibe un MA(1). El brazo restringido
tiene un solo AR y lo gasta entero en reproducir la raíz unitaria. **No se están
comparando dos parametrizaciones del mismo modelo: se está comparando un modelo
con su dinámica contra otro que la ha perdido.**

## La medida, sobre `ES_CPI_m10`

| | ℓ | npar | φ̂ |
|---|---:|---:|---|
| libre (d=1, AR+testigo MA) | −6,5192 | 14 | 0,1711 |
| **restringido, como lo construye art** | **−26,4914** | 13 | **0,9993** |
| el mismo **devolviéndole un AR** para la dinámica | −7,3401 | 14 | [0,998 · 0,4037] |
| base (d=1, AR(1), sin testigo) | −7,3917 | 13 | 0,4028 |

    LR que art atribuye a θ          39,944      → «d confirmado» (crít 1,94)
    LR al devolver el AR              1,642      → «d−1 bastaba»

**De los 39,9 puntos, 38,3 son dinámica perdida.** Y con el AR devuelto el LR cae
POR DEBAJO del crítico: **el veredicto se invierte**.

El φ̂ = 0,9993 del brazo restringido es la prueba visible: el modelo «sin
diferencia» está reproduciendo la diferencia con una raíz casi unitaria en el AR,
que es exactamente lo que la ∇ hacía.

## Impact

Alto. **Para cualquier serie I(1) cuyo modelo lleve un AR, este contraste no
puede decir otra cosa que «d confirmado»**: el brazo restringido está condenado
por construcción. El veredicto sale bien —d=1 ES correcto en ES_CPI— pero **no
está ganado**, y el ✓ verde que se imprime dice que se ha hecho una comprobación
que en realidad no discrimina nada.

Y el LR se compara contra el crítico 1,94 como si midiera evidencia sobre la
frontera. No la mide: mide, en un 96 %, un parámetro de dinámica que un brazo
tiene y el otro no.

Funciona cuando la serie es de verdad I(0) —comprobado: AR(1) estacionario con
d=1 impuesto da θ̂=+1,0000 y LR=0, apilamiento perfecto—, porque ahí el único AR
basta para el nivel y no hay nada que perder. El defecto aparece justo cuando la
respuesta importa.

## De dónde viene, y por qué funcionó donde nació

**BUG-0045, 28-ago-2026**, reportado por el analista vía «el experimento del chat
limpio», sobre **PGAS**. El hueco era real ahí: la tabla ADF/KPSS recomendaba
**d=0**, se adoptó **d=1**, y la etapa formal concluía «el orden de integración no
está en la banda ambigua» — una afirmación más fuerte de lo que los dos
contrastes sostenían, porque Shin-Fuller y el DCD de sobrediferenciación **miran
los dos hacia d+1**. Nadie preguntaba si con d−1 habría bastado, que era
justamente la duda de ese caso.

Y PGAS es **un AR(2) puro sin MA regular**: `dcd()` levantaba `ValueError: No
free regular MA(1) factors found`. No había instrumento, y por eso se añadió uno.

**Lo que no se vio es que PGAS cumplía una precondición que ES_CPI_m10 no
cumple.** Bajo H₀ el AR tiene que reproducir la raíz unitaria; si su orden es 1,
la gasta entera y no queda nada para la dinámica. Con orden 2 le sobra una raíz.

Medido sobre `ES_CPI_m10`, variando sólo el orden del AR:

| AR | φ̂ del brazo nulo | raíces⁻¹ | LR |
|---|---|---|---:|
| **AR(1)** — el real | [0,9993] | [1,0007] — **una sola, gastada** | **39,944** |
| AR(2) — como PGAS | [1,3953 · −0,3953] | [1,000 · **2,530**] | 10,212 |
| AR(3) | [1,4301 · −0,5007 · 0,0696] | [1,002 · 3,79 · 3,79] | 3,971 |

**El LR se desploma según el AR gana orden: 39,9 → 10,2 → 4,0.** Es la misma
serie, el mismo testigo y la misma H₀; lo único que cambia es cuánta dinámica
puede conservar el brazo nulo mientras imita la diferencia.

**La precondición, entonces: el AR necesita orden ≥ 2.** PGAS la cumplía — por eso
el contraste funcionó donde nació, y por eso nadie la escribió.

## Root cause

El testigo se AÑADE al brazo libre (`mc.ma = ma + [[0.85]]`) y el brazo
restringido se obtiene clavando θ=1 sobre **ese mismo** modelo. Los dos tienen el
mismo `npar`... nominalmente. Pero al cancelarse la ∇, el AR del restringido
cambia de trabajo: deja de modelar ∇y y pasa a reproducir la raíz unitaria. Es
una pérdida de grados de libertad EFECTIVOS que la cuenta de parámetros no ve.

## EL FIX — se PIDE, no se ofrece (analista, 11-sep-2026)

> *«Es un contraste que se debe pedir, pero no ofrecer, por razones conocidas en
> inferencia. Está bien tenerlo, pero sirve para casos específicos que el
> analista debe pedir, o que la serie parece estacionaria en nivel —como un
> precio relativo o en estudios de cointegración—. El caso del TFM era una
> petición legítima porque estábamos evaluando si la serie era d=0 desde un
> principio.»*

**Ésta es la corrección, y deja sin efecto lo que sigue más abajo.**

El arreglo no es sustituir el instrumento por otro mejor: es **dejar de
ofrecerlo**. Una batería de contrastes que nadie pidió, corrida sobre cada
modelo y presentada con su ✓, es **pre-testing** — el veredicto no tiene el
tamaño que aparenta. La razón es de inferencia, no de implementación, y no se
arregla mejorando el cálculo.

El par confirmatorio en f=0 son **Shin-Fuller sobre el AR** y el **DCD con
testigo de sobrediferenciación**, complementarios como ADF y KPSS en la
especificación inicial. Ése se corre siempre. El lado d−1 contesta otra pregunta
y sólo se hace cuando hay MOTIVO:

* la serie parece estacionaria en nivel,
* es un precio relativo,
* o se está en un estudio de cointegración.

Y el caso que lo creó —PGAS, BUG-0045— **era una petición legítima**: se estaba
evaluando si la serie era d=0 desde el principio. Legítima porque se preguntó,
no porque el instrumento deba dispararse solo. El defecto no fue añadirlo: fue
conectarlo a la batería automática.

### Hecho

`describe_formal_tests(..., subdiferenciacion=False)` y
`formal_tests(..., subdiferenciacion=False)`. Sin pedirlo **no se estima nada**
—son dos ajustes— y el bloque no aparece. La descripción publicada dice cuándo
pedirlo, porque un instrumento bajo petición que no dice en qué casos no se pide
nunca, o se pide siempre, que es lo mismo que ofrecerlo.

---

## ANEXO — la ruta que se exploró y NO es adecuada

*Lo que sigue se conserva porque es la medición que llevó a la decisión de
arriba, no porque proponga nada. La prescripción de reemplazar el instrumento
por «SF sobre el ARIMA(p+1,0,0)» **no es adecuada**: se midió y no converge.*

### La forma correcta del anidamiento (y por qué aun así no vale)

El defecto está bien visto y el arreglo que propuse era malo. La corrección:

> *«Si tienes un ARIMA(2,1,0), el modelo anidado que estima infradiferenciación
> es ARIMA(3,0,0), y el contraste de infradiferenciación es SF sobre el
> AR(1)·AR(2) resultante, donde la nula es d=1 y la alternativa es d=0.»*

**El modelo anidado no lleva testigo MA: es el modelo SIN DIFERENCIAR con el AR
subido un orden.**

    ARIMA(p, 1, 0)   →   anidado para infradiferenciación:   ARIMA(p+1, 0, 0)

Y el instrumento es **Shin-Fuller sobre ese AR(p+1)**, con H₀: d=1 (hay raíz
unitaria) frente a H₁: d=0.

Eso explica todo lo medido arriba. Subir el orden del AR es exactamente lo que le
faltaba al brazo nulo: con p+1 el modelo tiene sitio para la raíz unitaria **y**
para la dinámica, que es por lo que el LR caía de 39,9 a 10,2 y a 4,0 al añadir
órdenes. No era un truco para cerrar el hueco: era el modelo correcto
asomándose.

**Y hay una razón de fondo por la que el DCD con testigo MA no podía valer aquí.**
Un modelo d=1 y uno d=0 explican **variables dependientes distintas**, así que sus
verosimilitudes no son comparables (BUG-0051). Un LR entre ellos no significa
nada. La construcción con testigo MA *aparenta* esquivarlo —los dos brazos son
nominalmente d=1— pero cuela el problema por el MA que cancela. El contraste
sobre las RAÍCES del modelo sin diferenciar no tiene ese problema: no compara
verosimilitudes de variables distintas, mira dónde cae la raíz.

### Medido sobre `ES_CPI_m10` — ARIMA(1,1,0) → ARIMA(2,0,0)

    semilla AR(2) = (1−0.98B)(1−0.4028B)      [fue rechaza la raíz EXACTA]

    φ̂ = [1.2610, −0.2610]
    |B| de las raíces = [1.0000, 3.8316]      ← una en la unidad, otra libre
    φ dominante = 0.99999

    SHIN-FULLER:  Φ̂₁ᵤ = 0.000   crít 5% = 1.758   → NO rechaza H₀
                  ⇒ la raíz unitaria está ⇒ **d=1 confirmado**

Compárese con lo que hace hoy:

| | veredicto | por qué |
|---|---|---|
| DCD con testigo MA (actual) | d confirmado | LR=39,9, de los que **38,3 son dinámica perdida** |
| SF sobre ARIMA(p+1,0,0) | d confirmado | la raíz cae en **1,0000** con la dinámica intacta |

Los dos aciertan. Sólo uno lo hace por la evidencia.

### Y LA MEDIA ES LA PENDIENTE (analista, 11-sep-2026)

> *«ARIMA(1,1,0) con media anida con ARIMA(2,0,0) con TENDENCIA. El parámetro de
> la media ahora es semilla de la pendiente del ARIMA(2,0,0) con tendencia.»*

Correcto y necesario: si ∇y tiene media μ, entonces y lleva una tendencia lineal
determinista de pendiente μ. El anidado completo es, entonces:

    ARIMA(p, 1, 0) + media μ̂    →    ARIMA(p+1, 0, 0) + TENDENCIA (pendiente ← μ̂)

La primera medición de este informe **no la llevaba** —dejó `estimate_mu`, que
con d=0 es un nivel y no una pendiente—, así que estaba incompleta.

### Y al ponerla, el ajuste NO CONVERGE

El modelo sin tendencia está ANIDADO en el modelo con tendencia (ω=0), así que
ℓ(con) ≥ ℓ(sin) **siempre** en el óptimo. Seis semillas, y ninguna lo cumple:

| semilla AR | semilla pendiente | ℓ | pendiente estimada | φ dominante |
|---|---:|---:|---:|---:|
| (1−0,98B)(1−φ₀B) | 0,1545 | −54,13 | **−0,0816** | 1,000000 |
| (1−0,98B)(1−φ₀B) | 0,0000 | −98,91 | −0,2331 | 0,999999 |
| (1−0,95B)(1−φ₀B) | 0,1545 | −95,24 | −0,2087 | 0,999991 |
| (1−0,95B)(1−φ₀B) | 0,0000 | −134,35 | −0,3600 | 1,000000 |
| (1−0,90B)(1−φ₀B) | 0,1545 | −78,90 | −0,1427 | 0,999989 |
| (1−0,90B)(1−φ₀B) | 0,0000 | −116,29 | −0,2936 | 0,999999 |

    ℓ SIN tendencia (14 par) = −46,81   ← NINGUNA con tendencia lo supera

Y la pendiente sale **negativa** en las seis —entre −0,08 y −0,36— sobre un
índice de precios que sube, con un valor que depende por completo de la semilla.
Es la firma de una dirección no identificada.

**Por qué.** φ dominante = 1,000000 en todas. Bajo una raíz unitaria, el efecto
de un regresor de tendencia lineal se ACUMULA: implica una deriva cuadrática en
el nivel. Así que la pendiente compite con el AR casi unitario por la misma
característica, y la superficie de verosimilitud es degenerada **justo en H₀**.

Es el problema clásico de Dickey-Fuller: **el coeficiente de la tendencia no está
identificado bajo la nula de raíz unitaria.** Por eso DF y Shin-Fuller trabajan
sobre una REPARAMETRIZACIÓN en regresión —∆y sobre y₋₁, tendencia y retardos—
donde la pendiente sí está identificada bajo las dos hipótesis, y no por máxima
verosimilitud sobre el ARMA sin diferenciar.

**Consecuencia para el arreglo:** la prescripción es correcta en el ANIDAMIENTO y
en la semilla, pero no se puede implementar como «ajusta ARIMA(p+1,0,0) con
tendencia por MV y corre SF encima». Hace falta la reparametrización, o fijar la
pendiente en μ̂ en vez de estimarla libre. Eso es decisión del método.

### Lo que queda por decidir

La semilla. `fue` se niega a estimar un AR con raíz unitaria exacta
(`bad initial estimate: AR has a unit root`), así que el anidado hay que
sembrarlo **justo dentro** — aquí `(1−0.98B)(1−φ̂₀B)`. Es un detalle de
implementación, pero de los que deciden si el contraste converge.

### Observación aparte

El `ShinFullerResult` de ese ajuste trae `lr = 0.0` con
`loglik_free = −46,813` y `loglik_constrained = −52,337`, que no cuadra
(2·Δℓ = 11,05). O el campo no se rellena en esta rama o mide otra cosa. No es
este defecto; queda anotado.

## Validation

Sobre `ES_CPI_m10`: devolver un AR al brazo restringido tiene que dejar el LR
en 1,64 y no en 39,94. Y el control de que el contraste sí funciona donde debe:
AR(1) estacionario con d=1 impuesto da θ̂=+1,0000 y LR≈0 para φ ∈ {0, 0,5, 0,8}.
