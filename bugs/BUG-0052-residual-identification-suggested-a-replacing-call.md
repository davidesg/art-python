---
id: BUG-0052
title: la identificación sobre residuos sugiere un INCREMENTO, pero la llamada que imprimía SUSTITUYE el ARMA — tomada al pie de la letra reestimaba el mismo modelo
status: fixed
severity: medium
component: mcp-server
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-29
reporter: carril Claude del RUN 2 — defecto (c) de su informe
tags:
  - identification
  - iterative-cycle
references:
  - src/art/mcp_server.py (guided_identification — next_call con pre_path)
  - tests/test_bug_0052_0053_incremento_y_linaje.py
  - bugs/BUG-0052-repro/repro.py
---

## Summary

Con `pre_path`, `guided_identification` identifica sobre los **residuos** del
modelo ajustado. Esos residuos ya tienen su ARMA quitado, así que la lista de
candidatos dice **qué falta por modelar**: es un incremento.

La llamada que imprimía a continuación usa `base_pre_path`, y su semántica es la
contraria: hereda armónicos, intervenciones y media, y **sustituye** el ARMA por
el `(p,q)` que se le pase.

Las dos mitades son correctas por separado y no encajan. Sobre `PGAS_m03`, que ya
lleva **MA(1)** y cuyos residuos piden **q=1**, la herramienta imprimía
`*(Sugerencia: p=0, q=1)*`. Pasar eso no da un MA(2): da otra vez el MA(1).

El orden correcto —**MA(2)**— es el que acabó siendo el modelo final de PGAS en
los dos carriles del RUN 2, y **bate a la referencia del modo guiado** (AIC
584,56 contra 585,49). O sea que el analista tuvo que corregir la herramienta a
mano para llegar al mejor modelo de la serie.

## Fix

La sugerencia pasa a ser el orden **total**, y se dice la aritmética:

```
*(Sugerencia: p=0, q=2 — incremento 0,1 sobre la base 0,1)*

> ⚠ La lista de arriba es un INCREMENTO, no un total. Se ha identificado sobre
> los residuos de `PGAS_m03.pre`, que ya lleva p=0, q=1: lo que ves es lo que
> FALTA por modelar, no el modelo entero.
>
> Y `base_pre_path` sustituye el ARMA, no lo añade. Si pasas la sugerencia tal
> cual reestimas el mismo modelo. Los órdenes que hay que pasar son los
> totales: p=0+0=0, q=1+1=2.
>
> La suma es la regla práctica del ciclo iterativo, no una identidad:
> MA(1)∘MA(1) no es exactamente un MA(2). Estima y mira si el coeficiente nuevo
> se sostiene.
```

El último párrafo importa. La suma es la heurística del ciclo Box-Jenkins, no
álgebra: componer dos MA(1) no produce un MA(2). Presentarla como regla exacta
sería cambiar un error por otro, así que se da como punto de partida que hay que
contrastar estimando.

Cuando la base **no** lleva ARMA, incremento y total coinciden y no se imprime
nada: el aviso sólo aparece donde hay algo que advertir.
