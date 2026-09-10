---
id: BUG-0116
title: La descripción de las herramientas no sobrevive al cliente — lo que DECIDE está detrás del recorte, y easter, ar_f_freqs y Shin-Fuller se pierden
status: fixed
severity: high
component: mcp-tools
found_in: 0.2.0
fixed_in: 0.2.2
reported: 2026-09-08
reporter: David / sesión de Windows — análisis guiado del IPC español
tags:
  - mcp
  - docstring
  - superficie
  - silencioso
references:
  - src/art/mcp_server.py (docstring de confirm_and_estimate, 8.968 caracteres)
  - bugs/BUG-0116-repro/repro.py
  - BUG-0097 (expuso `easter`; el carril sigue sin ofrecerlo)
  - BUG-0103 (expuso `ar_f_freqs`, que tampoco llega)
---

## Summary

`art` publica el docstring **entero** —comprobado: 8.968 caracteres para
`confirm_and_estimate`— y eso es correcto. **El defecto no es que `art` recorte:
es que la descripción está escrita como si fuese a llegar completa, y no llega.**

En la sesión del 8 de septiembre el cliente entregó al modelo **2.033
caracteres, el 23%**. Con ese recorte, medido sobre el texto real:

    dónde cae cada cosa            posición   ¿llega?
    base_pre_path                     1,3%     sí
    p / lista de órdenes             11,6%     sí
    «nunca capar el AR»              21,4%     sí
    Shin-Fuller                      23,5%     ❌ SE PIERDE
    ar_f_freqs                       28,6%     ❌ SE PIERDE
    easter                           36,7%     ❌ SE PIERDE
    seasonal                         45,7%     ❌ SE PIERDE
    guion_decision                   85,6%     ❌ SE PIERDE

## Impact

Alto, y de la clase que no deja rastro: el modelo no sabe que no sabe.

**El caso más claro es `easter`.** BUG-0097 se cerró habiéndolo expuesto, y esa
mitad es cierta: el parámetro existe. Pero del efecto de Semana Santa llega el
nombre y el tipo, y nada más — ni que es **sólo mensual**, ni que el motor
construye el regresor, ni que es un determinista y **no** una intervención, ni
que se ignora al encadenar por `base_pre_path`. **Y el carril guiado no lo
sugiere en ningún nodo.** En la sesión salió porque el analista leyó el fuente y
porque la Semana Santa cayó en abril de 2012 y en marzo de 2013. Ninguna de las
dos vías es la herramienta.

**Y el peor es la pareja `ar_f_freqs` + Shin-Fuller**, que se pierden juntos.
Anteayer (BUG-0103) se expuso `ar_f_freqs` precisamente para que restringir un
factor a frecuencia estacional fuese un **contraste** y no una imposición, y se
escribió la doctrina de no capar un AR. La doctrina llega —está al 21,4%— pero
**la herramienta que permite obedecerla, no**. Queda el peor de los dos mundos:
el modelo sabe que no debe imponer y no ve con qué contrastar.

Es decir: **dos informes cerrados este mismo mes entregan menos de lo que su
cierre afirma**, no porque el arreglo fuera falso sino porque la vía por la que
el modelo se entera está cortada.

## Reproduction

`bugs/BUG-0116-repro/repro.py`, determinista y sin motor. Mide lo que se
publica, dónde cae cada cosa, y cuántas descripciones exceden el presupuesto.

    confirm_and_estimate publica 8968 caracteres
    con un cliente que entregue 2033 (23%):
      easter        al 36,7%   SE PIERDE
      ar_f_freqs    al 28,6%   SE PIERDE
      Shin-Fuller   al 23,5%   SE PIERDE
      seasonal      al 45,7%   SE PIERDE

    descripciones por encima de 2000 caracteres: 12 de 46
       8968  confirm_and_estimate
       4637  intervention_plot
       4465  guided_intervention
       4236  formal_tests
       3418  incident_configurations
       3337  guided_identification

`guided_intervention` y `guided_identification` —las dos puertas del carril
guiado— están en la lista.

## Root cause

La descripción creció por acumulación honesta: cada defecto cerrado dejó su
párrafo, y cada párrafo estaba justificado **por sí mismo**. Nadie miró nunca el
total, ni el ORDEN.

Y el orden es lo que decide qué sobrevive. Hoy sigue el de una firma de Python
—modos, luego parámetros en el orden en que se declaran— que no tiene nada que
ver con lo que el modelo necesita para no equivocarse.

## Fix

No es «acortar»: la información hace falta. Es **repartirla**.

1. **Presupuesto por descripción** —del orden de 1.500-2.000 caracteres— con lo
   que DECIDE delante: qué elige la herramienta, qué no debe hacerse nunca, y
   los parámetros que cambian el modelo. Comprobable, y el repro ya lo mide.
2. **Lo que es doctrina, a `_INSTRUCTIONS`**, que se entrega aparte y entera.
   La regla de no capar el AR ya está ahí; `easter` y la ruta de factorización
   no.
3. **Lo que es referencia, a los documentos** —`docs/`— citados por nombre desde
   la descripción. Un modelo que necesite el detalle puede pedirlo; uno que no
   lo necesite no paga por él en cada llamada.
4. **Y que el carril lo OFREZCA.** Es lo que de verdad cierra el caso del
   `easter`: `_alternativas_desde` ya propone opciones con su llamada exacta a
   partir de la diagnosis. Una opción «añadir el efecto de Semana Santa» cuando
   haya anómalos recurrentes de marzo/abril vale más que cualquier párrafo,
   porque llega **cuando hace falta** en vez de esperar a ser leída.

## Lo que NO hay que hacer

Culpar al cliente. Que recorte es un hecho del entorno —y otro cliente recortará
por otro sitio—; una descripción que sólo funciona entregada entera es frágil
por diseño. Lo que se puede controlar desde aquí es que lo importante vaya
primero.


---

## Punto 4 aplicado (2026-09-08): el carril ya OFRECE el easter

De los cuatro puntos del arreglo se aplica el **cuarto**, que era el último de la
lista y resulta ser el que cierra la consecuencia grave: **que una capacidad
exista y nadie la encuentre nunca**.

### Y al medirlo, mi propia propuesta resultó estar mal

Este informe decía «una opción cuando haya **anómalos recurrentes de
marzo/abril**». Medido, es falso:

    serie CON un efecto de Semana Santa del 4%
      n_extreme      0        ← NO deja anómalos: es SISTEMÁTICO
      white_noise    False    ← deja ESTRUCTURA
      q_fails        lag 12, lag 24, lag 36

`intervention_hints` no lo ve, y lo que sí ve —la Q rompiéndose en los retardos
estacionales— es **la misma firma que la estacionalidad corriente**. Una
alternativa basada en anómalos no habría saltado nunca.

### Lo que sí lo distingue: que SE MUEVE

La Semana Santa cae en marzo o en abril según el año, así que **ningún armónico
de periodo fijo la absorbe**. De ahí sale el contraste: correlacionar los
residuos con el regresor que el motor sabe construir, que es un contraste de
puntuación de andar por casa.

Medido sobre 10 réplicas de cada hipótesis, n=240, **con el paquete estacional
determinista ya puesto** —que es el caso que importa, porque ahí lo fijo ya está
absorbido— y con un efecto pequeño, del 2%:

    SIN easter     |t| mediana 0,35   máximo 1,30
    CON un +2%     |t| mediana 9,89   mínimo 9,82

Factor 7 entre el peor caso de cada lado. `UMBRAL_EASTER = 3`, muy dentro del
hueco.

### Y la alternativa lleva encima lo que el cliente no entrega

    **Añadir el efecto de SEMANA SANTA** — los residuos correlacionan con su
    regresor a |t| = 15.5. No aparece como anómalos porque es sistemático, y
    ningún armónico lo absorbe porque **se mueve entre marzo y abril**.
       `confirm_and_estimate(inp_path=…, easter=True, …)` — es un determinista,
       no una intervención: no lleva fecha, y sólo existe en series mensuales

Eso es exactamente la documentación que este informe mide como perdida (está al
36,7% del docstring, y el cliente entregó el 23%). **Llega cuando hace falta**,
que es lo que ningún párrafo consigue.

Ocho pruebas, incluidas las que fijan que no se ofrezca si el modelo ya lo lleva
—ofrecer lo puesto es ruido, y en el carril guiado el ruido compite con las
alternativas que importan— y que ni se mire en series no mensuales.

### Lo que sigue abierto de este informe

Los puntos **1, 2 y 3**: el presupuesto por descripción, mover la doctrina a
`_INSTRUCTIONS` y la referencia a `docs/`. **12 de 46 descripciones siguen por
encima del presupuesto**, y `ar_f_freqs` y Shin-Fuller se siguen perdiendo con un
cliente que recorte — o sea que la doctrina de no capar el AR llega y la
herramienta para obedecerla, no.


---

## Punto 3 aplicado (2026-09-08): los RECURSOS, que no existían

El informe proponía «mover lo que es referencia a `docs/`, citados por nombre».
Al ir a hacerlo apareció algo mejor y que el propio protocolo ya ofrecía:

    herramientas   46      se EMPUJAN en cada llamada  → caras, y se recortan
    recursos        0      se PIDEN cuando hacen falta → completas, y con URI

**MCP tiene un primitivo exactamente para esto y `art` usaba cero.** No es un
defecto de código: es una capacidad sin estrenar, y explica por qué el arreglo
no era acortar. El texto hace falta; lo que estaba mal es el canal.

    art://defectos              23.028 car.   índice, con lo que sigue abierto
    art://defectos/{bug_id}     14.180        un informe entero
    art://docs                     664        índice de diseño
    art://doc/{nombre}          13.915        un documento entero
    art://protocolo             34.121        releíble a mitad de análisis

### Lo que esto desbloquea, y es más que el canal

**El registro de defectos pasa a ser consultable en tiempo de ejecución.** Son
121 informes con su causa MEDIDA y la razón del arreglo, o sea la memoria de por
qué el método es como es — y hasta ahora el modelo que opera la herramienta no
veía ninguno.

Es el principio que `guion.py` ya aplica al análisis:

> «lo que una iteración fallida produce de valor NO es el modelo que se
> descarta, es la RAZÓN por la que se descarta.»

`art` lo aplicaba al análisis y **no a sí mismo**. Y no es teórico: en la sesión
del capado del AR(6), la razón por la que eso invierte la lógica del contraste
estaba escrita en `BUG-0103` y no había forma de pedirla.

### La mitad que hace que sirva

Un recurso que nadie sabe que existe es igual que no tenerlo, así que van
anunciados en `_INSTRUCTIONS` —el canal que SÍ llega entero— con las tres cosas
que hacen que se usen:

  · **cuándo**: «antes de proponer una simplificación que parezca obvia —capar
    un operador, podar un armónico, fiarte de un error típico»;
  · **el ejemplo concreto** del AR(6), que es lo que hace entender el
    disparador;
  · y **el aviso de que las descripciones pueden llegar recortadas**, que el
    modelo no puede saber por sí mismo —no ve el original— con la salida:
    pedirlo como recurso.

### Puntos 1 y 2 aplicados (2026-09-10): la FASE 1 de `ORDEN.md`

**Punto 1 — el presupuesto por descripción. CERRADO.** Las catorce que pasaban
de 1.800 —eran doce cuando se escribió esto y crecieron a catorce mientras se
hacía el censo de figuras, lo que dice por sí solo que el canal atrae texto—
están reescritas con la plantilla de SEMAFORO §4.1. **Ninguna pasa de 1.800.**

`ar_f_freqs` y Shin-Fuller, que eran los dos ejemplos nombrados arriba, ya no
dependen de que el cliente no recorte: el primero viaja en el ESQUEMA
(`Field(description=…)`, que el cliente necesita para construir la llamada y por
tanto no recorta) y el segundo está en la descripción de `formal_tests`, ahora
de 1.573 caracteres, y entero en `art://doc/DISENO-contrastes-formales`.

**Punto 2 — la doctrina. CERRADO, y por el otro lado.** No se metió más doctrina
en `_INSTRUCTIONS`: se sacó. La cabecera pasa de 35.941 a 1.991 caracteres con
lo que hay que saber ANTES de poder preguntar, y el método entero se sirve por
`art://protocolo` y sus siete etapas.

    descripciones    76.531  →  46.144
    cabecera         35.941  →   1.991
    por llamada     112.472  →  48.758      −57%

Y ORDEN 1.5 añadió lo que faltaba para que el canal que se pide funcione: la
cita aparece **donde se decide** y sólo cuando el caso lo pide. Un recurso que
sólo se anuncia en la cabecera se lee al abrir la sesión y, cuando hace falta,
ya salió de la ventana.

### Lo que este informe destapó y sigue abierto

Excede a un defecto, y por eso no se cierra con él: que
`DefaultPolicy` tiene todas las reglas en código mientras `ClaudePolicy` recibe
el 23% del texto, o sea que **los dos decisores no están igual de informados**.
Eso amenaza la comparabilidad que `guion_diff` afirma dar, y es medible.
