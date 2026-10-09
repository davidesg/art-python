---
id: BUG-0246
title: guided_identification (llamada 4 con pre_path) etiqueta el nodo estacionalidad como «D=0 (B1, armónicos deterministas)» en la Decisión A, sin armónicos, y lo escribe como un nodo nuevo duplicado
status: open
severity: low
component: guion
found_in: 0.2.3.dev0
fixed_in: 
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

## Fix (propuesto)

- `b1` = el `.pre` tiene deterministas armónicos (leerlos del `.pre`), no `bool(pre_path)`.
- Si el nodo `estacionalidad` ya está confirmado con el mismo D, no escribir otro (o
  escribirlo sólo si cambia la ruta).

## Validation

La repro deja un único nodo de estacionalidad, «D=0 (sin estacionalidad)».
