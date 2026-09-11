---
id: BUG-0157
title: El aviso «la explicación no concuerda con el contraste» se da sobre un episodio que EXCLUYE la vuelta, así que «permanente» sale por construcción
status: fixed
severity: high
component: interventions
found_in: 0.2.0
fixed_in: 0.2.1
reported: 2026-09-11
reporter: David — corrida guiada de ITCER
tags:
  - intervenciones
  - episodios
references:
  - BUG-0155
  - BUG-0136
---

## Summary

Cuando el analista declara `evento_naturaleza="transitorio"` y el contraste de
ganancia da ω(1) ≠ 0, la herramienta avisa de que **la explicación
extramuestral no concuerda con el contraste** — y trata eso como razón para
subir de peldaño.

En ITCER el aviso se dio sobre un episodio acotado a **un período**, que excluye
el rebote de 2009Q2–Q4. Con la vuelta fuera del modelo, **«permanente» sale por
construcción**: no hay nada en la especificación que pueda devolver el nivel.

El aviso desautoriza la información del analista con un contraste que **no puede
ver el suceso que el analista está describiendo**.

## Root cause

Tres piezas que encajan mal:

1. `decide_episodios` agrupa extremos contiguos. La caída de 2008 y el rebote de
   2009 están separados por trimestres tranquilos, así que son episodios
   distintos.
2. `incident_configurations` extiende el arranque **hacia atrás** por el
   mecanismo —un impulso de nivel en T da +ω en T y −ω en T+1— y no tiene forma
   de extender hacia **delante** para alcanzar una vuelta diferida.
3. El contraste ω(1)=0 se calcula sobre la intervención construida, que por (1)
   y (2) sólo cubre la caída.

Y la escalera tampoco ofrece la forma: `1b` —impulso de nivel— fuerza la vuelta
en T+1, y el dato la tiene cuatro trimestres después. **No hay forma en el
catálogo para un transitorio de vuelta diferida.**

## Impact

Alto, y de método. El nodo de intervención existe para incorporar lo que el
analista sabe y los datos no dicen; éste es el único sitio de `art` donde eso
entra. Un aviso que declara «no concuerda» cuando la discrepancia la produce la
propia delimitación **enseña al analista a desconfiar de su información**, que
es lo contrario de lo que el nodo pretende.

Además sugiere `incident_configurations` «para revisar la delimitación», y ese
instrumento no puede delimitar un episodio cuya otra mitad está después.

## La razón exacta, que resultó ser de FORMA y no de delimitación

Al arreglarlo se vio que el diagnóstico inicial —«el episodio excluye la
vuelta»— era la mitad de la historia. La otra mitad es más limpia y más general:

> **ω(1)=0 no dice «el nivel vuelve». Dice «el nivel vuelve EN EL ÚLTIMO PERÍODO
> QUE LA ESPECIFICACIÓN CUBRE».** La forma no tiene libertad sobre CUÁNDO.

De ahí que rechazar ω(1)=0 descarte *esa* vuelta y no cualquier vuelta. Y como
`evento_naturaleza` no lleva fecha de vuelta, **la discrepancia no se puede
establecer nunca**: el analista afirma «transitorio», el contraste responde
sobre «transitorio con vuelta en tal fecha», y son dos afirmaciones distintas.

Por eso el arreglo no es redelimitar: es que la propiedad
`concuerda_con_lo_extramuestral` **devuelva `None`** —indeterminable— siempre que
se declare `transitorio` y el contraste lo rechace.

La asimetría con `permanente` es deliberada y se prueba: una vuelta DENTRO del
tramo sí contradice «el nivel se quedó desplazado», así que ahí el aviso se
mantiene.

Y el caso extremo tiene nombre propio: con **un solo ω**, ω(1)=ω₀, y las dos
únicas lecturas posibles son «el nivel se desplaza» y «no pasó nada». No hay
vuelta expresable en NINGUNA fecha. (De paso, `en_palabras` decía ahí «el nivel
vuelve a la línea base tras 0 período(s)», que no es una vuelta: es que no pasó
nada.)

## Fix

**1 · El aviso dice su precondición, y dice DÓNDE sitúa el contraste la vuelta.**

    ⚠ **El contraste SITÚA la vuelta, no la busca.** Se declara *transitorio*, y
    la configuración con la que se compara —**Q2/2008×3** — la de **mejor AIC**,
    no una que hayas nombrado: no diste `evento_desde`— sólo admite una lectura
    transitoria: que el nivel vuelva en **Q4/2008**, el último período que
    cubre. Rechazar ω(1)=0 descarta *esa* vuelta, **no cualquier vuelta**.

Con un solo ω el texto es el del teorema: «**«Permanente» sale aquí por
construcción, no del dato.**»

**2 · Se dice de quién es la configuración de referencia.** Sin `evento_desde`
se compara contra la de mejor AIC — una que el analista nunca nombró. Callarlo
convertía una elección de la herramienta en un veredicto sobre el analista.

**3 · El techo del conjunto, calculado.** `vuelta_mas_tardia` da la vuelta más
tardía que ALGUNA configuración construida admite. En ITCER las tres acaban en
Q4/2008, porque la marcha hacia delante para en el primer residuo tranquilo. El
informe lo dice como hecho, no como sospecha.

**4 · La recomendación deja de desmentir al analista.** Decía «el dato
identifica la configuración: … PERMANENTE», sin matiz, justo después de que el
analista declarara transitorio.

**5 · El contraste de la ganancia NETA — `net_gain(model, [i, j])`**, y por la
superficie `test_interventions(..., ganancia_neta=[i, j])`:

    H₀:  Σᵢ ωᵢ(1) = 0        ⇔  el nivel acabó donde empezó

Una única restricción lineal sobre el vector completo de parámetros, así que
sigue siendo un Wald χ²(1) exacto: el mismo de `test_intervention` con α
extendido sobre los bloques elegidos. Un impulso pesa **0** en la suma — su
efecto en el nivel es cero por construcción, no por estimación (BUG-0076).

Y da **tres** lecturas, no dos:

    no se rechaza                  el nivel VOLVIÓ       transitorio
    se rechaza, |neta| < |caída|   volvió EN PARTE       recuperación PARCIAL
    se rechaza, neta ≈ caída       no volvió             permanente

La del medio es la que el catálogo no sabía nombrar, y es la que el analista
describía en ITCER: «recuperación parcial desde 2009Q2».

**6 · El callejón de la escalera ofrece la tercera salida.** Cuando ninguna forma
resuelve el suceso, decía «redelimita, o no es un suceso». Faltaba la lectura
que el caso necesitaba: vuelta DIFERIDA ⇒ dos intervenciones ⇒ ganancia neta.
Está escrito en dos sitios y se arreglan los dos; la prueba comprueba los dos,
porque un aviso que sólo da la mitad de los carriles es medio aviso.

## Lo que NO se ha hecho

**Extender la delimitación hacia delante** (era el punto 2 del plan original):
que `incident_configurations` busque una vuelta en una ventana y ofrezca la
forma de dos tramos como un candidato más. No hace falta para que el consejo sea
accionable —intervenir dos veces encadenando por `base_pre_path` ya funciona, y
la ganancia neta las junta— pero automatizaría lo que hoy el analista hace a
mano. Queda como mejora del catálogo, no como defecto abierto.

## Validation

Dos ficheros de prueba.

`test_bug_0157_el_contraste_no_ve_la_vuelta.py` reconstruye los **tres
candidatos de ITCER con sus números** —381,93 / 384,16 / 387,15, ω(1) de
−21,16 / −16,22 / −10,77, los tres acabando en Q4/2008— y comprueba que ya no se
afirma la discrepancia, que el aviso dice dónde cae la vuelta contrastada, que
dice que la referencia la eligió el AIC, y que la recomendación no desmiente al
analista. Y comprueba lo que NO debe cambiar: `permanente` declarado sigue
pudiendo discrepar, un `transitorio` confirmado sigue concordando, y sin
naturaleza declarada no se avisa de nada.

`test_bug_0157_ganancia_neta_del_episodio.py` monta un episodio sintético de
vuelta diferida —caída de −10 en dos tramos, recuperación de +6 seis períodos
después— y comprueba las tres lecturas, que la neta recupera la verdad del
testigo, que el Wald sólo rechaza cuando debe, y que un impulso no entra en la
suma.

**El testigo lleva AR(1) a propósito**, y esa decisión es ella misma una
medición: sin estructura ARMA el optimizador arranca cerca, apenas itera y la
covarianza se queda en la semilla del BFGS — el SE de la neta saltaba entre
**0,076 y 0,539** con el MISMO diseño y los mismos parámetros, sólo cambiando la
realización. Con el AR(1) da 14-16 iteraciones y el SE se queda en 0,55 en los
tres escenarios. Hay una prueba que lo fija (`test_el_SE_no_depende_de_los_datos_con_el_mismo_diseno`).
Es la regla del analista hecha prueba: *sin ARMA el optimizador puede llevar la
semilla; con ARMA es probable que las iteraciones necesarias den para tener SE
fiables.*
