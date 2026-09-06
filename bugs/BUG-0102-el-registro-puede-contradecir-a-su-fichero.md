---
id: BUG-0102
title: El registro puede contradecir a su fichero y nada lo dice — una entrada pierde 3 de 4 intervenciones; y presentar un guion anterior revienta
status: fixed
severity: high
component: guion
found_in: 0.1.12
fixed_in: 0.2.0.dev0
reported: 2026-09-06
reporter: David — «se pierde una intervención»
tags:
  - guion
  - registro
  - intervenciones
  - reconciliacion
  - regresion-propia
references:
  - src/art/guion.py (entradas_que_no_cuadran, _deterministas_del_inp, cifra)
  - src/art/mcp_server.py (guion_map: el aviso)
  - bugs/BUG-0102-repro/repro.py
  - tests/test_registro_contra_su_fichero.py
  - BUG-0098 (de donde sale la segunda mitad)
---

## Summary

Dos defectos del registro, encontrados persiguiendo el primero.

**(A) Una entrada declara menos intervenciones de las que tiene su `.inp`.**
Sobre el corpus —**616 entradas-modelo** con su fichero en disco— hay **una**:

    FOOD_UEM_2025 · v10 b02_covid_auto
       .inp    4 intervenciones: step 12/2004, 02/2017, 07/2020, 04/2022
       guion   1:                step 07/2020

Las tres que se pierden son **las que venía arrastrando de su padre**; la que
queda es la que se estaba añadiendo. La progresión del propio guion lo confirma:
v7 registra 4, v8 cinco, v9 seis — y v10, colgando de v6, registra 1.

**(B) Presentar un guion escrito por una versión anterior revienta.** Regresión
propia, de BUG-0098: hacer legibles los registros antiguos puso `None` en los
campos que no existían —`loglik`, `bic`, `sigma_a`—, y `None` es lo cierto (no
consta), pero cada `f"{v:.2f}"` muere con él.

    TypeError: unsupported format string passed to NoneType.__format__

Antes el guion fallaba **al abrirse**; después del arreglo falla **al
dibujarse**, que es peor: parece que funciona hasta que lo miras.

## Por qué importa (A)

El guion es el registro científico y su `.inp` es la evidencia. Que discrepen no
es un descuadre de formato: **lo que se lee en el mapa no es lo que se estimó**.
Una entrada que declara una intervención donde hay cuatro dice que el modelo es
mucho más simple de lo que es, y cualquier comparación de AIC contra sus hermanos
lo trata como tal.

En este caso concreto la entrada está marcada como callejón sin salida, así que
la pérdida no contaminó nada aguas abajo. Esta vez.

## Lo que NO se ha podido hacer

**Reproducirlo con el código de hoy.** `_extract_spec` sobre ese mismo fichero
devuelve las cuatro, y la ruta `form="auto"` de extremo a extremo las registra
todas. Puede que ya esté arreglado y puede que no.

Tampoco cuadran los tiempos con la hipótesis obvia: el `.inp` tiene mtime
20:27:17 y la entrada 20:27:18, así que en el momento de registrar el fichero ya
llevaba las cuatro — y todas las rutas que registran leen el modelo DEL FICHERO.

## Fix

**(A) Un detector, no un arreglo.** `entradas_que_no_cuadran(guion)` compara
cada entrada con su `.inp` leyendo el TEXTO —sin motor, sin estimar, sin cargar
el modelo, porque se llama una vez por entrada al dibujar el mapa— y `guion_map`
lo dice:

    ⚠ El registro CONTRADICE a su fichero en 1 entrada(s).
       · v10 b02_covid_auto: el `.inp` lleva 4 intervención(es) y el guion registra 1

Convierte un fallo que no sé reproducir en uno que no puede pasar desapercibido.

**(B)** `cifra(v, fmt)` en un solo sitio, y todo lo que presenta una cifra del
registro pasa por ahí: `—` cuando no consta, nunca un cero inventado. Había
cuatro sitios más en `export_guion` con la misma bomba sin estallar.

## Validación

    corpus: 616 entradas-modelo, 1 descuadre — el conocido
    repro:  detecta el descuadre, no da falso positivo cuando cuadra,
            y presenta un registro sin cifras sin reventar
