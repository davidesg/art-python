---
id: BUG-0256
title: El marcador de dos lados de los falsos positivos del MEG fija [1, 6], y el f = 1 está en el filo — una perturbación de 1e-12 lo cambia
status: fixed
severity: low
component: tests
found_in: 0.2.3
fixed_in: 0.2.4
reported: 2026-10-30
reporter: David / Claude — prueba de instalación limpia de atsw 2.1.0 en diez distribuciones
tags:
  - tests
  - MEG
  - plataforma
references:
  - tests/test_pipeline_regression.py::test_el_meg_encuentra_la_estacionalidad_que_hay_y_no_otra[determinista]
  - fue/docs/FORMAL_TESTS.md §3 (la verosimilitud de frontera)
---

## Summary

La prueba fija por los dos lados los falsos positivos del MEG sobre la serie
determinista: `[1, 6]`, medido el 14-ago-2026. El de f = 1 está en el filo: su
coeficiente MA_f converge a −0.99999994, y una perturbación relativa de la
serie de 1e-12 —menos de lo que ya cambia otra libm— lo hace determinista. La
cifra fijada no es una propiedad del MEG sino de los últimos bits de una
plataforma: en Alpine (musl, el C de fue) y en Arch (Python 3.14, el motor puro
de fue) la prueba dice `[6]` (prueba de instalación limpia de atsw 2.1.0,
2026-10-30), y se lee como una regresión o una mejora cuando no es ninguna.

## Impact

Bajo: es la prueba. El MEG no cambia. Pero un marcador de dos lados que salta
por ruido de redondeo enseña a ignorarlo, y entonces deja de servir para lo
que se puso: avisar de que el MEG ha cambiado.

## Reproduction

`bugs/BUG-0256-repro/repro.py` repite el ajuste y el MEG de la prueba sobre la
serie tal cual y multiplicada por 1 + 1e-12 cos(t), y corre la prueba sobre
las dos. Sale con 1 mientras la prueba falle en alguna (ver «Arreglo»).

    PYTHONPATH=src python3 bugs/BUG-0256-repro/repro.py

## Root cause

f = 1 cae en la frontera del MEG (coeficiente MA_f en −1 hasta la séptima
cifra): un veredicto que en esa serie no está determinado, fijado como si lo
estuviera.

## Fix

Propuesto: mantener el lado de la sensibilidad (lo que está, se encuentra) y,
en el de la especificidad, fijar sólo los veredictos que no están en el filo
(f = 6), con f = 1 anotado como frontera; o cambiar la serie de la prueba por
una en la que ningún armónico quede en el filo. No se toca el MEG.

## Validation

El repro, y la prueba en glibc, musl y el motor puro de fue.

## Arreglo

No se toca el MEG; se arregla el marcador. La especificidad sigue fijada por
los dos lados, pero sólo sobre los veredictos determinados: f = 1 de la serie
determinista se anota como FRONTERA y no se fija en ningún sentido, y el resto
se compara con `[6]`. Así f = 6 tiene que seguir saliendo, y cualquier falso
positivo nuevo fuera de la frontera (o la desaparición de f = 6) sigue
fallando: el marcador conserva lo que tenía de alarma y pierde sólo lo que era
de la libm. La sensibilidad (lo que hay, se encuentra) no cambia.

Se eligió esto y no cambiar la serie de la prueba porque la serie y sus cifras
están medidas y documentadas desde el 14-ago-2026, y buscar otra en la que
ningún armónico quede en el filo en ninguna plataforma no se puede garantizar
sin probarla en todas.

El repro ya no compara los veredictos del MEG (el de f = 1 sigue cambiando con
1e-12, y debe: es la frontera), sino que corre la PRUEBA sobre la serie tal
cual y perturbada; sale con 1 si falla en alguna. Contra la prueba vieja sale
con 1 (`antes [1, 6], ahora [6]`); con la nueva, con 0.
