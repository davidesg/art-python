---
id: BUG-0203
title: La línea de la media del listado se contradice — «t=+0.83 → Sí, estimate_mu=True» — porque el «sí» viene de que el modelo base ya lleva μ, no del t que imprime
status: fixed
severity: low
component: identification
found_in: 0.2.3.dev0
fixed_in: 0.2.3.dev0
reported: 2026-10-02
reporter: David / Claude — evaluación del carril autónomo (WTI del pass-through)
tags:
  - media
  - listado
references:
  - src/art/mcp_server.py ≈5422, mu_decision (_mu_in_base)
  - BUG-0013
---

## Summary

`guided_identification(WTI.inp, lam=0, d=1, D=0, pre_path=WTI_m05.pre)`:

    **¿Incluir media (μ)?** Deriva de ∇^1∇_s^0 y(λ=0.0): μ̄=0.0050, SE=0.0060,
    t=+0.83 → **Sí, `estimate_mu=True`** — el modelo base ya la lleva estimada …

El t de la deriva de la serie (0.83) diría «no»; el «sí» sale de `_mu_in_base`.
En WTI la μ del modelo base es significativa (t=2.28) porque las intervenciones
de las caídas dejan una deriva en el resto: son dos medidas distintas en una
línea.

## Impact

Bajo: el lector ve una regla (|t|>2) contradicha por su propio número.

## Fix

Cuando la decisión viene del modelo base, imprimir el t de ESA μ (y decir que
es la del modelo base); el de la serie diferenciada, aparte y como contexto.

## Validation

Test: con μ en el modelo base, la línea cita su t y no el de la serie.

## Resolution (2026-10-03)

**Fix.** When the base model carries μ, the line now cites THAT μ by name,
and the drift of the differenced series follows as context:

    **¿Incluir media (μ)?** **Sí, `estimate_mu=True`** — el modelo base
    `WTI_m05.pre` ya la lleva estimada (μ̂=0.0118, SE=0.0052, t=+2.28) y se
    hereda al encadenar por `base_pre_path`.
    *Contexto: la deriva de ∇^1∇_s^0 y(λ=0) sin el resto del modelo da
    μ̄=0.0050, SE=0.0060, t=+0.83. No es la misma medida: la del base es la
    deriva que queda una vez puestos sus deterministas.*

- The new `_mu_del_base(model)` returns (μ̂, SE, t) in the scale of the
  series. μ is the last free parameter; its SE is divided by `refactor`. It
  returns `None` when there is no usable SE, and the line then says the t
  is not available.
- Without μ in the base, the line is unchanged.
- The BUG-0013 note is kept, because it still explains the context figure.

**Validation:** `tests/test_bug_0203_la_media_del_base.py`:
- the line cites the base's t and its file;
- the series' t goes on a separate context line;
- without a base, the line is unchanged;
- μ̂ is in the scale of ∇ln y.

