---
id: BUG-0245
title: confirm_and_estimate con base_pre_path ignora en silencio n_harmonics/seasonal: estima el modelo SIN armónicos, lo registra en el guion con el nombre y la razón de los armónicos y dice «se conservan sus armónicos»
status: open
severity: medium
component: pipeline
found_in: 0.2.3.dev0
fixed_in: 
reported: 2026-10-09
reporter: David / Claude — revisión del paper de dolarización (GDPDEC guiado)
tags:
  - confirm_and_estimate
  - armonicos
  - base_pre_path
references:
  - src/art/mcp_server.py confirm_and_estimate (docstring, l. ~657: «Con base_pre_path, n_harmonics se ignora»)
  - src/art/pipeline.py _build_arma_on_model
---

## Summary

Con `base_pre_path`, `confirm_and_estimate` sólo sustituye el ARMA: `n_harmonics` y
`seasonal=True` se descartan (lo dice el docstring, l. ~657). Pero se descartan **en
silencio**: la salida no avisa, el modelo se estima sin armónicos, se escribe con el
`output_path` y la `guion_rationale` que el analista dio para los armónicos, y el bloque de
decisión afirma «Encadenado desde …: se conservan sus intervenciones y armónicos». El
resultado es un modelo idéntico al de referencia registrado en el guion como si fuera otro.

## Impact

Medido en GDPDEC (deflactor del PIB de Ecuador, en bruto): el analista pidió armónicos
deterministas sobre 2008Q4×2 + AR(2). Las dos llamadas —con `n_harmonics=2, seasonal=True` y
sin ellos— dieron ficheros byte a byte iguales (`diff` vacío) y dos versiones del guion
(v10, v11) con ℓ, AIC y diagnosis idénticos. Sólo se notó al comparar las salidas. Un LR de
«armónicos» calculado entre esas dos versiones sale 0 y se leería como «no significativos».

No hay forma incremental de AÑADIR armónicos a un modelo con intervenciones: hubo que editar
el `.pre` a mano (bloque de deterministas: `step` + `cos 1` + `sin 1` + `alter`, órdenes
`1 0 0 0`), que es justo lo que el contrato `.pre` quiere evitar (BUG-0085).

## Reproduction

```python
s.confirm_and_estimate("bugs/BUG-0245-repro/GDPDEC_m02_s0804x2.pre", "/tmp/h.inp",
    base_pre_path="bugs/BUG-0245-repro/GDPDEC_m02_s0804x2.pre",
    lam=0, d=1, D=0, p=2, q=0, seasonal=True, n_harmonics=2, estimate_mu=True)
s.confirm_and_estimate("bugs/BUG-0245-repro/GDPDEC_m02_s0804x2.pre", "/tmp/n.inp",
    base_pre_path="bugs/BUG-0245-repro/GDPDEC_m02_s0804x2.pre",
    lam=0, d=1, D=0, p=2, q=0, estimate_mu=True)
# diff /tmp/h.inp /tmp/n.inp  -> vacío; el .inp no lleva cos/sin/alter
```

`GDPDEC_armonicos_a_mano.pre` es la especificación correcta construida a mano (ℓ −140.69
frente a −142.11; LR 2.84, 3 gl).

## Root cause

El modo incremental hereda los deterministas del `.pre` y no mira `n_harmonics`/`seasonal`.
Es una decisión de diseño documentada, pero la API acepta los argumentos sin quejarse y la
narrativa de la salida asume que se aplicaron.

## Fix (propuesto)

Una de dos, y en cualquier caso nunca en silencio:

1. **Rechazar** (como ya se hace con un λ o un D distinto, BUG-0199): si llega
   `n_harmonics > 0` o `seasonal=True` y el `.pre` no los lleva, devolver un error que diga
   que el modo incremental no añade armónicos y cómo hacerlo.
2. **Aplicarlos** (como con una d distinta, BUG-0199): añadir los cos/sin/alter que falten
   a los deterministas heredados, con semilla 0, y decirlo en la salida.

La 2 es la útil: el analista que pide armónicos sobre un modelo con intervenciones no tiene
hoy otra vía que editar el `.pre`. Además, el texto «se conservan sus … armónicos» sólo debe
salir si el `.pre` los tenía.

## Validation

La repro: con la opción 1, la primera llamada falla con el mensaje; con la 2, `/tmp/h.inp`
lleva `cos 1`, `sin 1`, `alter` y reproduce ℓ = −140.69 del fichero a mano.
