---
id: BUG-0021
title: formal_tests crashes with AttributeError on any model carrying an AR(2) factor — the report reads r.freq_hat, RVResult exposes freq_estimated
status: fixed
severity: high
component: formal-tests
found_in: 0.1.11
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-25
reporter: David / réplica TFM Bolivia
tags:
  - dcd
  - rv
  - crash
references:
  - src/art/describe.py:1617 (bloque «RV — frecuencia de AR(2)»)
  - src/art/formal_tests.py:939-951 (dataclass RVResult)
  - src/art/formal_tests.py:1087-1097 (construcción de RVResult)
  - bugs/BUG-0021-repro/repro.py
---

## Summary

`formal_tests` aborta con `AttributeError: 'RVResult' object has no attribute
'freq_hat'` en cuanto el modelo lleva un factor **AR(2) de raíces complejas**.
El bloque que imprime el contraste RV lee `r.freq_hat`; el dataclass `RVResult`
declara el campo como `freq_estimated`. Es una discordancia de nombre entre el
motor y la capa de presentación, y no hay ninguna prueba que recorra ese camino.

El efecto no se limita al bloque RV: la excepción sube desde
`describe_formal_tests` y **se pierde el informe entero** — Shin-Fuller, el DCD
de sobrediferenciación y el par confirmatorio en f=0 ya estaban calculados
(minutos de optimización) y no llegan a imprimirse. El analista no recibe nada.

## Impact

Alta. Deja `formal_tests` —la herramienta que ART designa como el contraste
formal que decide el orden de integración sobre el modelo estimado— inutilizable
para toda una clase de modelos, y precisamente la clase en que uno quiere mirar
la frecuencia del factor: un AR(2) complejo es lo que se ajusta a una serie con
ciclo o con una raíz casi unitaria de frecuencia baja.

Pasó desapercibido porque el camino sólo se activa con AR(2) **y** raíces
complejas (`φ₁² + 4φ₂ < 0`). Con AR(1), MA(1) o un AR(2) de raíces reales
`rv_res` sale vacío, el bucle no itera y no se toca el atributo inexistente.

Descubierto aplicando ART al precio de exportación del gas boliviano
(`ln PGAS`, 2004:1–2024:4, n=84), cuyo AR(2) en niveles da
φ̂ = (1.5708, −0.6191) → discriminante −0.0090 → raíces complejas.

## Reproduction

```
python3 bugs/BUG-0021-repro/repro.py
```

Sintético y autocontenido: simula un AR(2) con par complejo, lo estima con
`confirm_and_estimate(p=2, q=0)` y llama a `describe_formal_tests`. Antes del
arreglo termina en `AttributeError`. El script imprime además los campos reales
de `RVResult`, que es el invariante que se rompió:

```
campos de RVResult: ['ar_factor_index', 'freq_estimated', 'freq_null',
                     'loglik_constrained', 'loglik_free', 'lr', 'phi1',
                     'phi2', 'pvalue', 'rho']
  tiene 'freq_estimated'?  True
  tiene 'freq_hat'?        False  <- describe.py leia ESTE
```

## Root cause

`src/art/formal_tests.py:942` declara

```python
freq_estimated: float   # estimated resonant frequency f̂ (harmonic units)
```

y `src/art/formal_tests.py:1089` lo construye como `freq_estimated=freq_hat`,
donde `freq_hat` es la **variable local** de la rutina. El nombre local se
filtró a la plantilla de `describe.py`, que quedó leyendo un atributo que nunca
existió en el objeto.

## Fix

`src/art/describe.py:1617` — leer el campo declarado:

```python
-  lines.append(f"- f̂={r.freq_hat:.3f}, H₀:f={r.freq_null}: "
+  lines.append(f"- f̂={r.freq_estimated:.3f}, H₀:f={r.freq_null}: "
```

## Validation

`tests/test_bug_0021_rv_block_renders.py` ajusta un AR(2) de raíces complejas,
comprueba que `describe_formal_tests` no lanza y que el bloque RV aparece en el
informe; además fija el contrato de nombres afirmando que `RVResult` expone
`freq_estimated` y no `freq_hat`, para que la discordancia no pueda volver por
el otro lado.
