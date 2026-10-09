---
id: BUG-0244
title: confirm_and_estimate con base_pre_path no acepta `p` como lista de factores (TypeError en _arma_starts), así que no se puede sobreajustar AR(1)·AR(2) conservando las intervenciones
status: open
severity: low
component: pipeline
found_in: 0.2.3.dev0 (+ arreglos sin commit)
fixed_in:
reported: 2026-10-09
reporter: David / Claude — análisis guiado de IPC_US (P02)
tags: [confirm_and_estimate, factores, sobreajuste]
references:
  - src/art/pipeline.py _build_arma_on_model → _arma_starts
---

## Summary

`confirm_and_estimate(..., base_pre_path=IPC_US_m06.pre, p=[1, 2], q=0)` falla con
`TypeError: orden p debe ser un entero, recibido list: [1, 2]`. El modo nuevo sí acepta la
lista; el incremental no.

## Impact

El sobreajuste factorizado que pide el árbol (§5, AR(2) complejo) no se puede hacer sobre un
modelo con intervenciones o armónicos sin reconstruirlo a mano.

## Reproduction

```python
s.confirm_and_estimate("bugs/BUG-0244-repro/IPC_US_m06.inp", "/tmp/x.inp",
                       base_pre_path="bugs/BUG-0244-repro/IPC_US_m06.pre",
                       p=[1, 2], q=0, estimate_mu=True)
```

## Fix (propuesto)

`_build_arma_on_model` debe repartir `p` por factores como el modo nuevo: los arranques por
Yule-Walker del total y los factores construidos con `p` como lista.

## Validation

La repro estima un AR(1)·AR(2) con las dos intervenciones heredadas.
