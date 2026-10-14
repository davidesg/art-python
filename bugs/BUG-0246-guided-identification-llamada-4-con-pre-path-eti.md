---
id: BUG-0246
title: guided_identification (llamada 4 con pre_path) etiqueta el nodo estacionalidad como «D=0 (B1, armónicos deterministas)» en la Decisión A, sin armónicos, y lo escribe como un nodo nuevo duplicado
status: fixed
severity: low
component: guion
found_in: 0.2.3.dev0
fixed_in: 0.2.3.dev0
reported: 2026-10-09
reporter: David / Claude — revisión del paper de dolarización (GAPGDPD/GDPDEC guiados)
tags:
  - guided_identification
  - estacionalidad
references:
  - src/art/mcp_server.py guided_identification, l. ~5563: _texto_D(D, …, b1=bool(pre_path))
  - src/art/mcp_server.py _texto_D
---

## Summary

En `guided_identification`, la llamada 4 con `pre_path` (identificar el ARMA sobre los
residuos de un modelo con intervenciones) escribe el nodo `estacionalidad` con
`_texto_D(D, …, b1=bool(pre_path))`. Tener `pre_path` no implica la ruta B1: el protocolo
manda también a la Decisión A (sin estacionalidad) a calibrar anómalos con un modelo base y
volver con su `.pre`. El nodo sale «D=0 (B1, armónicos deterministas)» en un modelo sin
armónicos, y además como **nodo nuevo**: el de estacionalidad ya estaba confirmado
(«D=0 (sin estacionalidad)», al estimar el modelo base).

## Impact

Bajo, pero en el registro que se usa para reconstruir el análisis. En GAPGDPD (guion
`BUG-0246-repro`, del análisis real) el mapa queda:

```
4 estacionalidad = D=0 (sin estacionalidad)
7 estacionalidad = D=0 (B1, armónicos deterministas)   <- falso y duplicado
```

y lo mismo en GDPDEC. Quien lea el guion entiende que se pasó a estacionalidad determinista.
Hubo que corregirlo con `guion_annotate`.

## Reproduction

`python3 bugs/BUG-0246-repro/repro.py` — el guion real de GAPGDPD hasta el n6 y la
llamada 4 con `GAPGDPD_m01_s0804.pre`; sale con 1 mientras el bug siga abierto.

1. `guided_identification(GAPGDPD.inp, lam=0, d=1)` → HAC p 0.29, Decisión A.
2. `confirm_and_estimate(..., p=0, q=0, n_harmonics=0, seasonal=False)` → nodo
   «D=0 (sin estacionalidad)».
3. Intervención (`GAPGDPD_m01_s0804.pre`).
4. `guided_identification(GAPGDPD.inp, lam=0, d=1, D=0, pre_path=GAPGDPD_m01_s0804.pre)`
   → «◆ guion n7: estacionalidad = D=0 (B1, armónicos deterministas)».

## Root cause

`b1=bool(pre_path)` toma la presencia de `pre_path` por la ruta B1. La ruta la dice el
`.pre`: B1 si lleva cos/sin/alter, A si no. Y el nodo se escribe aunque ya hubiera uno
confirmado con el mismo valor de D.

## Fix

Lo propuesto, en una pieza: con la etiqueta correcta no hace falta una regla
aparte contra el duplicado.

- `_ruta_estacional_del_pre(pre_path)` (`src/art/mcp_server.py`) lee la ruta
  del `.pre`: «B1» si lleva cos/sin/alter, «A» si no.
- En `guided_identification`, al cerrar el nodo `estacionalidad`, esa ruta va
  como `seasonal_hint` de `_texto_D` y gana sobre la propuesta del nodo
  pendiente (el `.pre` es el hecho). Se quita el parámetro `b1` de `_texto_D`,
  que sólo servía para esta llamada.
- Con la etiqueta «D=0 (sin estacionalidad)», `_confirma_nodo` ve que el último
  nodo ya dice lo mismo y no escribe otro (su regla de siempre). Si el `.pre`
  cambia de ruta respecto al nodo confirmado, sí se escribe, como «se vuelve al
  nodo».

Test: `tests/test_bug_0246_pre_path_no_es_ruta_b1.py` — Decisión A confirmada
y llamada 4 con un `.pre` sin armónicos: un único nodo «D=0 (sin
estacionalidad)»; ruta B1 pendiente y `.pre` con armónicos: «D=0 (B1, armónicos
deterministas)»; y la ruta leída del `.pre`. Sin el arreglo fallan el de la
Decisión A y el de la lectura; el de B1 pasaba ya (en esa ruta la etiqueta era
correcta) y queda como guarda.

## Validation

El repro sale con 0: el guion de GAPGDPD tras la llamada 4 tiene un solo nodo
de estacionalidad, «D=0 (sin estacionalidad)». Antes del arreglo salía con 1
(el n7 «D=0 (B1, armónicos deterministas)»).
