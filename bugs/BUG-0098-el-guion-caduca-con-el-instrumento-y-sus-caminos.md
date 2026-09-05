---
id: BUG-0098
title: El guion caduca con el instrumento (un registro anterior no se puede leer) y sus caminos son relativos al cwd del día
status: fixed
severity: high
component: guion
found_in: 0.1.12
fixed_in: 0.2.0
reported: 2026-09-05
reporter: David / revisión de arquitectura con contexto limpio, hallazgo #4 — medido sobre el corpus 2026-09-05
tags:
  - guion
  - registro
  - compatibilidad
  - rutas
  - evidencia
references:
  - src/art/guion.py (GuionStats: campos obligatorios añadidos después)
  - src/art/guion.py (_campos_conocidos, _resuelve_ruta, CAMPOS_DE_RUTA, load_guion, save_guion)
  - bugs/BUG-0098-repro/repro.py
  - tests/test_guion_no_caduca.py
---

## Summary

El guion es el registro científico del recorrido: qué se probó, en qué orden,
por qué se abandonó cada rama y dónde está la evidencia de cada nodo. Dos
defectos independientes lo hacían **irrecuperable en parte**, y ninguno de los
dos borra un byte — los dos rompen la LECTURA.

**(A) El registro caduca con el instrumento.** `GuionStats` fue ganando campos
obligatorios (`loglik`, `bic`, `sigma_a`) sin valor por defecto. Un guion escrito
antes de que existieran levanta `TypeError` al abrirse, y no pierde una columna:
**pierde el fichero entero**.

**(B) Los caminos son relativos al cwd del día.** `inp_path` se guardaba tal como
se lo pasaban a la herramienta, que era relativo al directorio de trabajo de
aquella sesión. El guion viaja —a otra carpeta, a otra máquina, al repositorio—
y el cwd no viaja con él.

## Medición sobre el corpus real (101 guiones, 1.307 entradas)

    guiones ilegibles por (A)                            1   (10 entradas)
    entradas con inp_path                              630
      de ellas, apuntando a un fichero inexistente      189   (30%)
      de esas 189, RELATIVAS                            189   (el 100%)
      de esas 189, ABSOLUTAS                              0

Que las 189 sean relativas y ninguna absoluta es el diagnóstico: **no se había
borrado nada**. Y lo confirma la contraprueba:

    resolubles contra la carpeta del propio guion      188 de 189

La evidencia estaba donde siempre y el registro sabía dónde. Lo que fallaba era
el ORIGEN desde el que se leía el camino.

## Por qué importa

Un `.inp` al que no se llega no es un inconveniente de navegación. Es el fichero
desde el que se reestima ese nodo, se releen sus parámetros y se le compara con
un hermano; sin él, la entrada del guion es una afirmación sin respaldo. Y (A) es
peor todavía, porque no degrada: quita el registro completo.

Los dos comparten raíz, y por eso van en un solo informe: **el guion se escribía
pensando en la sesión que lo estaba escribiendo**, no en la que lo va a leer.

## Fix

**(A)** Todos los campos de `GuionStats` con valor por defecto, y `from_dict`
filtrando por `_campos_conocidos`: los campos que ya no existen se descartan y
los que aún no existían los pone la clase. `None` significa NO CONSTA, no cero.

**(B)** Dos mitades, y hacen falta las dos:

  - al ESCRIBIR (`save_guion`), los caminos de la terna se guardan absolutos —
    pero **sólo se absolutiza lo que existe**, porque convertir a absoluto contra
    este cwd un camino que no se puede comprobar es inventar una ubicación, que
    es el mismo error con otro disfraz;
  - al LEER (`load_guion`), un camino relativo que no existe se resuelve contra
    la carpeta del propio guion. Esto es lo que rescata los ya escritos, que son
    justo los que sostienen las mediciones.

`figure_path` y `hist_path` quedan FUERA a propósito (`CAMPOS_DE_RUTA`): son
hermanos del guion, viven en `figs/` a su lado y viajan con él. Absolutizarlos
sería romperlos al mover la carpeta.

## Verificación

Sobre el corpus, releído con el arreglo:

    guiones ilegibles      1 → 0
    caminos muertos      189 → 1

El que queda es el único de los 189 que no resuelve contra la carpeta del guion:
ése sí es evidencia efectivamente ausente, y ahora se distingue de los 188 que
sólo estaban mal direccionados.

## Lo que este arreglo NO hace

La compatibilidad es hacia ATRÁS, no hacia delante. Un guion escrito por una
versión posterior y leído por ésta pierde al reescribirlo los campos que esta
versión no conoce. `_campos_conocidos` lo documenta: **la lectura es segura; la
reescritura es la que trunca.**
