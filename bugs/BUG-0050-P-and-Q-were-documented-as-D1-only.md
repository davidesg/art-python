---
id: BUG-0050
title: la documentación decía que P y Q son «D=1 only» — es falso, y quien se lo cree concluye que un AR estacional residual obliga a la ruta B2, justo la que el objetivo multivariante prohíbe
status: fixed
severity: high
component: mcp-server
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-29
reporter: carril Claude del RUN 2 — defecto (f) de su informe
tags:
  - documentation
  - seasonality
  - objetivo
references:
  - src/art/mcp_server.py (confirm_and_estimate — docstring de P y Q)
  - src/art/pipeline.py (_make_model, "Stationary stochastic seasonality on top of the deterministic harmonics")
  - tests/test_bug_0050_P_con_D0.py
  - bugs/BUG-0050-repro/repro.py
---

## Summary

`confirm_and_estimate` documentaba:

```
P : seasonal AR order (D=1 only)
Q : seasonal MA order (D=1 only)
```

Es falso. `_make_model` construye un AR estacional con `D=0` desde siempre y
lleva su propio comentario diciéndolo — *«Stationary stochastic seasonality on
top of the deterministic harmonics»*. Es la forma en que la ruta **B1** absorbe
la estacionalidad que los armónicos deterministas dejan.

Y no es un caso de esquina: **los dos modelos finales de RATIO de este proyecto
son exactamente eso**, `P=1` con `D=0` — el del modo guiado (`RATIO_m31`) y el
del carril Claude del RUN 2 (`RATIO_m03`).

## Por qué es grave, y no sólo inexacto

Lo encontró el analista del RUN 2, y lo importante es **adónde le mandaba**:

> Si hubiera hecho caso a la documentación habría concluido que la única salida
> era B2, es decir, exactamente la ruta que el objetivo multivariante prohíbe.

La cadena es corta y sale mal entera: el analista ve estacionalidad estocástica
residual sobre B1 → busca un operador estacional → la documentación le dice que
eso exige `D=1` → concluye que B1 no puede expresarlo → adopta B2. Con
`objetivo="multivariante"` esa ruta está vetada, así que la documentación le pone
en un callejón sin salida **inventado**: el problema tenía solución dentro de la
ruta permitida, con un solo parámetro.

Y la propia lista de identificación le recomendaba `SARIMA(0,0,0)(1,0,0)₄` con
`D=0`. O sea que la herramienta se contradecía a sí misma, y la contradicción se
resolvía a favor de la parte equivocada por venir en la documentación del
parámetro, que es donde se busca la respuesta.

## Repro

```
$ python bugs/BUG-0050-repro/repro.py

1) ¿Qué dice la documentación?
   «D=1 only» presente: False   ← corregida

2) ¿Existe P=1 con D=0 en el propio proyecto?
   guiado/RATIO/RATIO_m31.pre:  P=1  D=0   ← AR estacional CON D=0
   run2/RATIO/RATIO_m03.pre:    P=1  D=0   ← AR estacional CON D=0

3) ¿Lo estima el motor sobre datos sintéticos?
   estimado sin error con D=0 y P=1
   Q p-minimo = 0.1125  (ruido blanco)
```

## Fix

El docstring describe lo que el motor hace, dice que `D=0` está incluido, y deja
escrito el coste de la afirmación anterior para que no vuelva.

## Nota sobre la clase de defecto

No hay una línea de código mal. Hay una frase que afirma lo contrario de lo que
el código hace, en el sitio exacto donde alguien va a buscarla, y que empuja
hacia una ruta prohibida por el objetivo declarado. Vale la pena tenerlo presente
al revisar el resto de la documentación de parámetros: **una restricción
inventada es más cara que una capacidad no documentada**, porque la segunda se
descubre probando y la primera impide probar.
