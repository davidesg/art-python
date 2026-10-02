---
id: BUG-0199
title: Con base_pre_path, confirm_and_estimate ignora la d pedida y conserva la del .pre — pero la cabecera anuncia la d pedida, así que el analista lee un ARIMA(0,2,2) que en realidad es un ARIMA(0,1,2)
status: fixed
severity: high
component: estimation
found_in: 0.2.3.dev0
fixed_in: 0.2.3.dev0
reported: 2026-10-02
reporter: David / Claude — evaluación del carril autónomo (IPC_ES del pass-through)
tags:
  - confirm_and_estimate
  - base_pre_path
  - silencioso
references:
  - src/art/mcp_server.py, confirm_and_estimate — spec_str (≈6554) con el d del argumento
  - src/art/pipeline.py ≈974, la construcción incremental desde el .pre
  - docs/STUDY-autonomous-lane-and-the-domain.md §5
---

## Summary

`confirm_and_estimate(inp_path=<m02.pre>, base_pre_path=<m02.pre>, d=2, p=0, q=2)`
estimó con la d del `.pre` (d=1) y la cabecera dijo lo contrario:

    ## 1 · ESPECIFICACIÓN
    **ARIMA(0,2,2) + 12 interv. [desde IPC_ES_m02.pre]**
    ...
    (2)  ∇Nₜ = (1 + 0.5411·B + 0.1560·B²) aₜ          ← ∇, no ∇²
    ── Estado ──  decidido: log · d=1 · ... ARMA(0,2)

El modo incremental está documentado como «reemplaza SÓLO la parte ARMA», así
que conservar la d puede ser lo querido; lo que no lo es es que la cabecera
imprima la d del argumento.

## Impact

Alto, y de la peor clase: el modelo que se cree estimado no es el estimado. En
la corrida, el analista (el LLM) estimaba el candidato d+1 que pedía el DCD, y
obtuvo un ARIMA(0,1,2) sin μ cuya media residual (t=5.25) parecía un defecto del
modelo d=2. Sólo la ecuación (∇ y no ∇²) delataba el error.

## Reproduction

/tmp/claude-1000/-home-david-Dropbox-SRC-atws/64d092c5-5f90-4f6e-bc4e-790912c74c98/scratchpad/passthrough_autonomo/IPC_ES/work/IPC_ES_m02.pre (o cualquier .pre con d=1):

    confirm_and_estimate(inp_path=m02.pre, output_path=m06.inp,
                         base_pre_path=m02.pre, lam=0, d=2, D=0, p=0, q=2)

La cabecera dice ARIMA(0,2,2); la ecuación y el estado, d=1.

## Root cause

`spec_str` se compone con los argumentos `p, d, q` de la llamada; el modelo
incremental (`pipeline`, construcción desde el .pre) hereda λ, d y D del .pre.

## Fix

Una de dos, y la decisión es de diseño:
1. Rechazar en modo incremental una d (o D, o λ) distinta de la del .pre, con
   el mensaje «cambiar d es reformular: estima desde el .inp»; o
2. Aplicarla (reconstruir el operador no estacionario) y decirlo.

En cualquier caso la cabecera se compone del MODELO estimado, no de los
argumentos.

## Validation

Un test que encadene con d distinta y exija (1) el rechazo o (2) que la
ecuación lleve la d pedida; y que la cabecera y el estado digan lo mismo.

## Resolution (2026-10-02)

**Fix: option 2 for d, option 1 for λ and D.**

- `lam`, `d` and `D` default to `None`. Chaining from a `.pre`, `None`
  inherits the `.pre`'s value. On a fresh model, `None` gives the old
  defaults (λ=0, d=1, D=0).
- **A different d is APPLIED** (`_build_arma_on_model(d=)`). This is the d+1
  candidate the protocol asks for, and the deterministic terms are kept. The
  `.pre`'s mean is not inherited, because the mean of ∇^d is a different
  quantity. Without `estimate_mu=True` the model has no μ; with it, μ is
  re-seeded on the new d. The output says so: «d cambiada: 1 → 2».
- **A different λ or D is REFUSED**, with «es REFORMULAR, no encadenar», and
  nothing is written. λ rescales every ω; D clashes with the inherited
  harmonics and `ifadf`.
- The header, the scan and the guion read d and D from the ESTIMATED model, as
  λ already did.

An existing test (`test_bugs_0169_0170…`) passed `lam=0.0` while chaining from
a levels `.pre`. That is this bug's very pattern, ignored until now. The test
now inherits.

**Validation:** `tests/test_bug_0199_d_al_encadenar.py`, 7 tests:
- d applied and header in agreement;
- μ not inherited across a d change;
- d inherited when omitted;
- the same d is not a change;
- λ and D refused;
- the fresh defaults kept.

