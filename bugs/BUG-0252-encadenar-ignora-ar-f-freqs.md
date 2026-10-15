---
id: BUG-0252
title: confirm_and_estimate con base_pre_path ignora en silencio ar_f_freqs y estima el modelo sin el factor de frecuencia fija
status: fixed
severity: medium
component: pipeline
found_in: 0.2.3.dev0
fixed_in: 0.2.3
reported: 2026-10-14
reporter: David / Claude — al arreglar BUG-0245 (la misma clase, con los armónicos)
tags:
  - confirm_and_estimate
  - encadenamiento
  - frecuencia-fija
references:
  - src/art/mcp_server.py confirm_and_estimate (~l. 7555): la rama de base_pre_path llama a _build_arma_on_model sin ar_f_freqs
  - src/art/pipeline.py _build_arma_on_model: hereda los ar_f del .pre
---

## Summary

En modo nuevo `ar_f_freqs=[k]` añade un AR(2) de frecuencia fija 2πk/s. Al
encadenar (`base_pre_path`) el argumento se descarta: el modelo hereda los
factores de frecuencia fija del `.pre` y no añade el pedido, sin decirlo.

Minneapolis (`flour_prices.csv`), desde el AR(1) m02.pre:

    confirm_and_estimate(inp, m03.inp, base_pre_path=m02.pre, p=1, q=0, ar_f_freqs=[2])

da m02 otra vez: 0 factores de frecuencia fija, frente a 1 en modo nuevo.

## Impact

Medio: es la versión contrastable de «este factor es estacional», y se pide
justo cuando el modelo ya tiene intervenciones y armónicos que no se quieren
rehacer, que es para lo que se encadena. El analista cree haber estimado el
modelo con el factor; sólo se ve leyendo la ecuación. Misma clase que BUG-0245.

## Reproduction

`python3 bugs/BUG-0252-repro/repro.py` — con los datos del ejemplo
(`flour_prices.csv`); sale con 1 mientras el bug siga abierto.

## Root cause

La rama de `base_pre_path` de `confirm_and_estimate` no pasa `ar_f_freqs` a
`_build_arma_on_model`, que copia los `ar_f` de la base.

## Fix

`_build_arma_on_model` recibe `ar_f_freqs` y AÑADE los AR(2) de frecuencia
fija que pide y la base no lleva, con la misma semilla que el modo nuevo. Los
heredados no se tocan: son estructura (BUG-0034), y ahí vive el testigo del
MEG. `confirm_and_estimate` lo pasa y la salida dice «AR(2) de frecuencia fija
añadidos: k = …», o que el `.pre` ya lleva ese factor y se hereda. El aviso de
los armónicos (BUG-0245) se suma al de estos, no lo pisa. Test:
`tests/test_bug_0252_encadenar_ar_f_freqs.py` (3); fallan sin el arreglo.

## Validation

El repro sale con 0: encadenado con `ar_f_freqs=[2]`, m03 lleva el mismo
factor que el modelo nuevo (1 y 1).
