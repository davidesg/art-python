---
id: BUG-0208
title: Qué hacer con las figuras en el modo autónomo — hoy se dibujan, se escriben y se devuelven como imagen en cada llamada, aunque nadie las mire; ART_NO_VIEWER sólo cierra la ventana (A DISCUTIR)
status: fixed
severity: medium
component: figuras
found_in: 0.2.3.dev0 @a33b893
fixed_in: 0.2.3.dev0
reported: 2026-10-06
reporter: David / Claude — resolución de la P02 de Econometría Aplicada (UCM) con art en modo autónomo, 15 series y cuatro analistas
tags:
  - diseño
  - a-discutir
  - autonomo
  - rendimiento
  - contexto
references:
  - src/art/mcp_server.py (_imagen, _result, _show_fig, _visor_procede: ART_NO_VIEWER)
  - src/art/mcp_server.py:9244 (build_model con_figuras, la única llave real)
  - src/art/describe.py (_fig_b64)
  - bugs/BUG-0208-repro/repro.py
---

## Summary

En el carril GUIADO las figuras son fundamentales: el analista decide mirándolas. En el
AUTÓNOMO el analista es el LLM y no las mira, pero cada herramienta las sigue dibujando
(matplotlib), escribiendo en disco y devolviendo como `ImageContent` en la respuesta.

Las llaves que hay no lo resuelven: `ART_NO_VIEWER` sólo impide abrir la ventana del visor;
`build_model(con_figuras=False)` es la única que apaga el dibujo, y no es el carril autónomo
(BUG-0180).

## Impact

Medido sobre `confirm_and_estimate` (IPC_US, AR(2), `ART_NO_VIEWER=1`, caché caliente):
1,71-1,91 s con figura frente a 0,84-0,89 s con `savefig` vacío: **el dibujo es el 48-56 % de
la llamada**. Y cada llamada mete ≈ 58 KB de PNG en base64 en el contexto del modelo
(`guided_identification` paso 3: dos figuras, 125 KB). En la P02, cuatro analistas autónomos
hicieron 86-148 llamadas cada uno.

## Reproduction

`bugs/BUG-0208-repro/repro.py`, bloque 0208.

## Root cause

No hay una llave de figuras ligada a `modo`: el modo decide si la salida PARA (BUG-0181), no si se dibuja.

## Fix

**A discutir** (David, 6-oct-2026): ¿no hacer las figuras, o hacerlas sin renderizarlas? Las
figuras «van con los modelos» —son parte de su registro— y el guion podría ir sin ellas. Tres
opciones:

- (a) **No dibujar** en autónomo. El guion va sin gráficos. Lo más barato; las figuras no
  existen salvo que se pidan.
- (b) **Dibujar y guardar** el PNG junto al modelo (`.inp/.out/.pre` + figura), pero **no
  devolverlo** como imagen. Ahorra el contexto, no el tiempo: el coste está en rasterizar, que es
  lo mismo que escribir el PNG.
- (c) **Diferido**: no dibujar en la llamada; el modelo y el guion guardan lo necesario y la
  figura se regenera bajo demanda desde el `.inp` (lo que ya hace `guion_evidencia`, y
  `export_guion` al construir el HTML).

En los tres, el guiado no cambia, y `con_figuras=True` debería poder pedirlas en autónomo.

## Validation

Tras decidir: tiempo de una llamada autónoma y bytes de imagen devueltos (repro, bloque 0208); y que el guiado sigue devolviendo sus figuras.

## Resolution (2026-10-06)

**Decision (b)** (David, 6-oct-2026). In the autonomous lane the figure is still
drawn and saved with the model; it is not sent back as an image. The new
`_figuras_del_carril` (applied by the `_figuras_por_carril` decorator to
`estimate_and_diagnose`, `confirm_and_estimate`, `guided_intervention` and
`suggest_intervention_form`) does this when `modo="autonomo"`:
- writes each figure as `<stem>__<huella>.png` next to the `.inp/.out/.pre`;
- drops the `ImageContent`;
- states the path(s) in one line of the text.

The guided lane is unchanged. A new `con_figuras=True` returns the images in
autonomous mode too, as `build_model` already did. Tools without `modo` keep
their behaviour (`guided_identification`, `formal_tests`, `intervention_analysis`,
`test_interventions`).

The report's script, measured on IPC_US AR(2) `confirm_and_estimate`:

    before: autonomous → images [58532] bytes
    after:  autonomous → images [] · w__ce5b06b8934b.png saved next to w.inp
            guided → [58532] · autonomous + con_figuras=True → [58532]

The drawing time is not saved; that would need option (c).

**Validation:** `tests/test_bug_0208_figuras_del_autonomo.py`:
- an autonomous call returns no image, the PNG exists next to the model, and its
  absolute path is in a single line;
- a guided call still returns the image;
- autonomous + `con_figuras=True` returns it;
- every tool with `modo` exposes `con_figuras` in its MCP schema.
