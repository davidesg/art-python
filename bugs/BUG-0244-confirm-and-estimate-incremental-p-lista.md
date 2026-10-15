---
id: BUG-0244
title: confirm_and_estimate con base_pre_path no acepta `p` como lista de factores (TypeError en _arma_starts), así que no se puede sobreajustar AR(1)·AR(2) conservando las intervenciones
status: fixed
severity: low
component: pipeline
found_in: 0.2.3.dev0 (+ arreglos sin commit)
fixed_in: 0.2.3
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

## Fix

`_build_arma_on_model` (`src/art/pipeline.py`) reparte `p` con `ordenes_ar`, como
`_make_model`: las semillas de Yule-Walker se piden para el orden TOTAL y se usan si
hay un solo factor; con varios factores, las semillas del llamador (`ar_seeds`, que
ahora `confirm_and_estimate` pasa también en el modo incremental) o neutras (0), igual
que en el modo nuevo. Lo propuesto —arrancar los factores con el Yule-Walker del total—
no vale tal cual: las semillas del operador completo no son las de sus factores, y el
modo nuevo ya había resuelto eso con `ar_seeds`.

Test: `tests/test_bug_0244_encadenar_p_lista_de_factores.py` — `p=[1, 2]` sobre un base
con escalón construye dos factores libres y conserva la intervención; `ar_seeds` se
respeta; un entero sigue siendo un operador; y por el servidor, con los ficheros de la
repro. Falla sin el arreglo.

## Validation

`python3 bugs/BUG-0244-repro/repro.py` sale con 0: el `.pre` lleva AR(1)·AR(2) y las
dos intervenciones heredadas (escalón ×3, impulso ×2):
`(1 + 0.2060·B) (1 − 0.6106·B + 0.2881·B²) (∇Nₜ − 0.1933) = aₜ`, ℓ = 33.40.
