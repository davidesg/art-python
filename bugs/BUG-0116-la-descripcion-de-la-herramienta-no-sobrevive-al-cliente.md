---
id: BUG-0116
title: La descripción de las herramientas no sobrevive al cliente — lo que DECIDE está detrás del recorte, y easter, ar_f_freqs y Shin-Fuller se pierden
status: open
severity: high
component: mcp-tools
found_in: 0.2.0
fixed_in:
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
