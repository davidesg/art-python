---
id: BUG-0245
title: confirm_and_estimate con base_pre_path ignora en silencio n_harmonics/seasonal: estima el modelo SIN armónicos, lo registra en el guion con el nombre y la razón de los armónicos y dice «se conservan sus armónicos»
status: fixed
severity: medium
component: pipeline
found_in: 0.2.3.dev0
fixed_in: 0.2.3.dev0
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

## Fix

Se aplican (la opción 2), que es la útil y la del resto de argumentos del modo incremental:
la `d` (BUG-0199) y `easter` (BUG-0170) ya se honran al encadenar; sólo λ y D se rechazan,
porque reescalan los ω o chocan con los deterministas. Rechazar dejaba sin vía el caso del
informe salvo editar el `.pre` a mano.

- `confirm_and_estimate` (`src/art/mcp_server.py`): `n_harmonics` pasa de `5` a `None`.
  En un modelo nuevo `None` sigue siendo 5; al encadenar, `None` (y `seasonal=None`) hereda
  el bloque del `.pre`. Hacía falta: con el defecto `5` no se distinguía «no lo he pedido»
  de «quiero 5», y honrarlo habría puesto 5 pares en todo encadenamiento.
- `_build_arma_on_model` (`src/art/pipeline.py`) recibe `n_harmonics`/`seasonal` y, si
  llega alguno, `_rehaz_armonicos` deja el bloque como el pedido, con el convenio de
  `_make_model`: `seasonal` decide si hay bloque (por defecto `n_harmonics > 0`) y
  `n_harmonics` cuenta pares k = 1…n (con el mismo tope y aviso). Lo que ya estaba conserva
  su ω; lo nuevo parte de 0. El `alter` va con un bloque nuevo y, si el base ya tiene
  bloque, se hereda como esté; `seasonal=True` sin `n_harmonics` sobre un base con bloque no
  lo toca (no resucita un par que una simplificación quitó). `seasonal=False` lo quita.
- Con un `.pre` de D = 1 pedir armónicos se rechaza con la razón (serían redundantes con la
  diferencia estacional).
- La salida dice qué cambió («**Armónicos cambiados** respecto de X: ninguno → cos 1, sin 1,
  alter. Los nuevos … parten de 0»), y «se conservan sus intervenciones y armónicos» sólo
  nombra lo que el `.pre` tenía y se ha conservado. La cabecera separa intervenciones y
  términos armónicos. Docstring (y `docs/TOOLS.md`, regenerado) e instrucciones del
  servidor ya no dicen que se ignoran.

Test: `tests/test_bug_0245_encadenar_armonicos.py` — herencia por defecto, añadir sobre un
base sin armónicos, quitar con `seasonal=False`, ω conservadas al recortar pares, bloque
simplificado intacto con `seasonal=True`, `alter` heredado como esté, rechazo con D = 1, y
el caso del informe por el servidor (ℓ −140.69 y el texto). Falla sin el arreglo.

## Validation

`python3 bugs/BUG-0245-repro/repro.py` (nuevo) sale con 0: con `seasonal=True,
n_harmonics=2` el `.inp` difiere del de sin armónicos, lleva `step`, `cos 1`, `sin 1`,
`alter` (trimestral: 2 pares se recortan a 1, con aviso) y reproduce ℓ = −140.69 del
fichero a mano.
