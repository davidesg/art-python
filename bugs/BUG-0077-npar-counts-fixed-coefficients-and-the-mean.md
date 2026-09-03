---
id: BUG-0077
title: la corrección de grados de libertad del Ljung-Box cuenta coeficientes FIJOS y cuenta la media — el motor no hace ninguna de las dos cosas
status: fixed
severity: high
component: diagnosis
found_in: 0.1.12
fixed_in: 0.2.0 (unreleased)
reported: 2026-09-03
reporter: David / run 5 guiado sobre ITCER
tags:
  - ljung-box
  - degrees-of-freedom
  - adequacy
  - fixed-coefficients
references:
  - src/art/diagnosis.py:461 (_npar)
  - tests/test_bug_0077_npar.py
  - BUG-0074, BUG-0075 (el mismo estadístico, la misma sesión)
---

## Summary

```python
def _npar(model) -> int:
    """Count free ARMA + mu parameters (used for Q df correction)."""
    for factor in (model.ar or []):
        n += len(factor)          # cuenta TODOS los coeficientes
    ...
    if model.mu0 != 0.0:
        n += 1                    # y cuenta la media
```

Dos errores, y el `.out` del motor los delata a los dos.

**Cuenta coeficientes FIJOS.** `len(factor)` ignora `ar_free`/`ma_free`. Y hay
un caso que aparece constantemente: el artificio `ar=[[0.0]]` con
`ar_free=[[False]]` que la interfaz usa cuando no hay ARMA que estimar. Un
coeficiente clavado en cero no consume grado de libertad ninguno, y se estaba
restando.

**Cuenta la media.** La corrección clásica de Ljung-Box es `m − p − q`: los
órdenes ARMA. El motor no resta μ.

## Repro

ITCER m01 — `d=1`, μ libre, **sin ARMA**, con el artificio `ar=[[0.0]]` fijo:

| retardo | Q | DF del `.out` | p correcta | DF de art | p de art |
|---|---|---|---|---|---|
| 4 | 6.78 | **4** | **0.1478** | 2 | **0.0337** |
| 8 | 8.05 | 8 | 0.4289 | 6 | 0.2347 |
| 12 | 8.98 | 12 | 0.7042 | 10 | 0.5335 |
| 15 | 10.40 | 15 | 0.7940 | 13 | 0.6612 |

**El veredicto de adecuación se invierte**: art declara que el modelo no es
ruido blanco (p=0.0337 < 0.05) cuando el motor dice que lo es con holgura
(p=0.1478).

Y el sesgo es sistemático y crece con el modelo: cada determinista y cada
coeficiente fijo que se añade resta un grado de libertad que no debería, así
que **cuanto más deterministas lleva un modelo, más inadecuado parece**.

Comprobación por el otro lado: PGAS m20 —AR(1) **libre**, sin μ— da en el
`.out` `15.27  14`, es decir `lags − 1`. El motor sí resta el parámetro ARMA
libre. La regla es exactamente ésa y ninguna otra.

## Fix

`_npar` cuenta **sólo los coeficientes ARMA con su flag `free` en True**, y no
cuenta μ:

    df = retardos − (nº de coeficientes ARMA LIBRES)

que es lo que hace el motor y lo que dice el convenio de Box-Jenkins.

## Nota sobre el artificio `ar=[[0.0]]`

Este bug lo destapó, y conviene dejarlo escrito: la interfaz mete un factor AR
de coeficiente 0 y flag `False` cuando no hay ARMA que estimar. Es inofensivo
para la estimación pero **contamina cualquier recuento de parámetros que no
mire los flags**. Ya está anotado como pendiente en el TODO; este bug es la
primera consecuencia medida.

## Test

`tests/test_bug_0077_npar.py`
