---
id: BUG-0118
title: El repro del óptimo espurio muestra la semilla YA AJUSTADA y mezcla unidades — dos columnas que no dicen lo que dicen
status: open
severity: medium
component: bugs
found_in: 0.1.2
fixed_in:
reported: 2026-09-08
reporter: David / sesión de Windows — al verificar BUG-0006 en la otra plataforma
tags:
  - repro
  - presentacion
  - unidades
references:
  - bugs/BUG-0006-repro/repro.py
  - fue/BUG-0005 (el informe que este repro sirve)
---

## Summary

Al correr `BUG-0006-repro/repro.py` en Windows para cerrar la cuestión de la
dependencia de plataforma, su salida resultó **engañosa en dos columnas**. No
son defectos de Windows: están en las dos plataformas y llevan ahí desde que se
escribió.

### 1 · La columna «Phi seed» muestra el valor AJUSTADO

    m_seed = m1.ar_s          # guarda una REFERENCIA
    ...
    m1.fit()                  # la reescribe in situ

Las dos filas imprimen `[-0.109, -0.093]`, que es el óptimo — **no** las
semillas, que son `[-0.0400, -0.0805]` para la de por defecto y `[-0.11, -0.09]`
para la identificada. Comprobado con `copy.deepcopy` antes de `fit()`.

El repro existe **precisamente** para comparar dos arranques distintos, así que
la columna que los distingue es la que miente. Y peor: hace parecer que los dos
arranques eran el mismo, que es la conclusión contraria a la que el repro
investiga.

### 2 · `report()` mezcla unidades

No divide `μ̂` por nada, multiplica `σ_a` por 100, y no divide ninguno de los dos
por `refactor` —que vale 100, puesto por `art.pipeline._make_model`—. De ahí que
su propio bloque «Expected» (μ̂ ~ 0,00, σ_a ~ 0,261) **no case con lo que él mismo
imprime** (μ̂ = +0,2149, σ_a = 26,0772).

Un lector cuidadoso ve una divergencia de ×100 donde no la hay:

    μ̂  = +0,214892 / 100 = +0,002149   ← referencia +0,002149  ✓
    σ_a =  0,260772 / 100 =  0,002608   ← referencia 0,2608     ✓
    AIC = 76,4 − 2·292·ln(100) = −2613,0                        ✓

## Impact

Medio, y de la clase que cuesta caro justo cuando importa: este repro se corre
para **decidir** si un informe cierra. En la sesión del 8 de septiembre hizo
falta rehacer la aritmética a mano para ver que el resultado de Windows coincidía
con el de Linux hasta la sexta cifra.

Un repro cuya salida hay que reinterpretar antes de creerla no cumple su función,
que es dar una respuesta legible sin conocer sus tripas.

## Fix

1. `copy.deepcopy` de las semillas ANTES de `fit()`, y etiquetar la columna como
   lo que es.
2. Dividir por `refactor` al presentar, o —más honesto— **imprimir las dos
   escalas** y decir cuál es cuál. El bloque «Expected» debe estar en la misma.

## Nota de nomenclatura

El repro vive en `art/bugs/BUG-0006-repro/` y sirve a `fue/BUG-0005`. Los
documentos de la prueba de Windows lo llamaron «BUG-0005» siguiendo al informe
de `fue`; el `art/BUG-0005` es otra cosa (`nyquist-added-when-no-harmonics`).
Conviene decirlo en la cabecera del repro para que no vuelva a confundir.
