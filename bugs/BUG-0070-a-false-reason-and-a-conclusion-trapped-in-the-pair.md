---
id: BUG-0070
title: cuando Shin-Fuller no aplica el informe daba una razón FALSA —«no tiene AR regular libre» sobre un modelo con AR(2)— y la cota inferior de d se perdía por estar atrapada dentro del bloque del par
status: fixed
severity: medium
component: describe
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-09-01
reporter: David / réplica TFM Bolivia — destapado al corregir BUG-0065
tags:
  - formal-tests
  - presentation
references:
  - src/art/describe.py (describe_formal_tests)
  - bugs/BUG-0065-the-shin-fuller-null-was-not-shin-fullers.md
  - bugs/BUG-0045-the-confirmatory-pair-only-looked-upward.md
  - tests/test_bug_0044_0045_white_noise_and_the_lower_side.py
---

## Summary

Dos defectos que aparecieron al corregir Shin-Fuller (BUG-0065), y los dos son de
la misma clase: **una conclusión atada a una condición que no era la suya**.

### (a) Una razón falsa

Hasta BUG-0065 sólo había un motivo por el que Shin-Fuller podía faltar —que el
modelo no tuviera AR regular libre— y el informe lo daba por sentado:

> *«Sin par confirmatorio. Este modelo **no tiene AR regular libre**, así que
> Shin-Fuller no es aplicable…»*

Con el segundo motivo —un AR **de raíces complejas**, donde la reparametrización
(m − ρ)·A(m) no existe— ese texto pasó a ser **falso**: el modelo tiene AR, y con
dos parámetros. Sobre `PGAS_m20`, un AR(2) con pseudociclo de 8,6 trimestres, el
informe afirmaba que no había AR libre.

Una razón equivocada es peor que ninguna, porque se cree.

### (b) Una conclusión atrapada

La **cota inferior** del orden de integración —«¿habría bastado d−1?», que
introdujo BUG-0045— se imprimía sólo **dentro del bloque del par confirmatorio**,
que requiere Shin-Fuller. Pero el lado d−1 no depende de él: lo da el DCD de
sub-diferenciación por su cuenta, y estaba calculado.

Resultado: en los modelos **sin par** se perdía una conclusión ya disponible,
justo donde más falta hace — son precisamente los que se quedan con un solo lado.

## Fix

* El informe distingue los dos motivos y publica **el que corresponde**. Para el
  caso de raíces complejas, además, remite al contraste que sí aplica: MEG y
  DCD_f, que es donde vive la no estacionariedad en ω≠0.
* La cota inferior se emite **siempre que el DCD de sub-diferenciación exista**,
  en su propio bloque cuando no hay par. El texto dice explícitamente que llega
  sin el lado AR, para que no se lea como una confirmación por los dos lados.

## La familia

Es el tercer caso de la sesión en que **arreglar un contraste apaga un aviso de
otro** porque el aviso estaba enganchado a la condición equivocada — los otros
dos son BUG-0066 (el testigo fuera del eje, atado a la discrepancia) y este
mismo. Merece una revisión sistemática: qué otras conclusiones están dentro de un
`if` que no es el suyo.

## Nota de numeración

Este informe se escribió como BUG-0067 y se renumeró a BUG-0070: el número estaba ya tomado por un hallazgo del benchmark guiado de SF_MEG, escrito unas horas antes en este mismo repositorio. **Dos sesiones distintas comparten el contador de `bugs/` y no se ven entre sí**, así que la colisión no fue un descuido sino la consecuencia de no tener reserva de número. Ver la nota en `bugs/README.md`.
