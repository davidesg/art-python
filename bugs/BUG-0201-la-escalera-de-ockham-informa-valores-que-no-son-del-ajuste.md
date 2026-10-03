---
id: BUG-0201
title: La escalera de Ockham informa de un AIC y un ω que no son los del ajuste final — y con ese ω de signo cambiado avisa de «una caída permanente» donde hay una subida
status: fixed
severity: medium
component: interventions
found_in: 0.2.3.dev0
fixed_in: 0.2.3.dev0
reported: 2026-10-02
reporter: David / Claude — evaluación del carril autónomo (IPC_ES del pass-through)
tags:
  - escalera
  - intervenciones
references:
  - src/art/escalera.py — peldaños; aviso de dominio (≈433, DOMINIOS_SIN_CAIDA_PERMANENTE)
  - docs/STUDY-autonomous-lane-and-the-domain.md §5
---

## Summary

`suggest_intervention_form(IPC_ES_m00.pre, date="09/2012", form="auto")` (la
subida del IVA de septiembre de 2012):

    `1a` escalón en el nivel (permanente) · AIC 77.44 · ω(1)=-0.4282 · inadecuado ◀ elegido
    ...
    **Dominio**: en una serie de clase `price_index` una caída PERMANENTE de nivel es poco usual.

y el modelo estimado con esa misma intervención:

    + 0.8761 ξₜ^{S,9/2012}   (0.2755)        AIC = 69.90

El peldaño elegido y el ajuste final difieren en AIC (77.44 frente a 69.90) y en
el SIGNO de ω (−0.43 frente a +0.88). El aviso de dominio sale del ω del
peldaño (`p1a.omega[0] < 0`), así que es el mismo defecto: la escalera evalúa
algo distinto de lo que luego se estima.

## Impact

Medio. La escalera es el argumento que el nodo de intervención ofrece para la
forma; si sus números no son los del modelo, el argumento no se sostiene, y el
aviso de dominio empuja en la dirección equivocada (desconfiar de una subida de
IVA como si fuera una caída).

## Reproduction

/tmp/claude-1000/-home-david-Dropbox-SRC-atws/64d092c5-5f90-4f6e-bc4e-790912c74c98/scratchpad/passthrough_autonomo/IPC_ES/work/IPC_ES_m00.pre (armónicos + μ, d=1);
la llamada de arriba.

## Root cause

Por investigar: la escalera ajusta sus peldaños sobre otra base (¿otra fecha,
otra semilla, el modelo sin μ?) o con otro convenio de signo que el ajuste
final.

## Fix

Que los peldaños se estimen sobre el mismo modelo base que el ajuste final y
que el peldaño elegido reproduzca su AIC y su ω; un test que lo exija.

## Validation

Sobre el caso del IVA: AIC y ω del peldaño 1a iguales a los del modelo
estimado; sin aviso de «caída».

## Resolution (2026-10-02)

**Root cause, measured.** The ladder and the final fit were on the same base
with the same sign convention, but at different DATES:

- `suggest_intervention_form` aligns the ladder with the mechanism's winning
  configuration (BUG-0156). For the VAT, that configuration starts in 05/2012
  with 5 steps.
- The alignment moved ALL three rungs to 05/2012. The «1a» was therefore a
  step four months before the only extreme (ω=−0.43, AIC 77.44).
- When 1a was chosen, the tool built the step at the requested date, 09/2012
  (ω=+0.88, AIC 69.90).
- The domain warning («caída permanente») read the 05/2012 ω.

**Fix.** The scalar rungs (1a, 1b) now sit at the date of the event, and rung
2 is still the configuration from its own start:
- `escalera_de_ockham(at_simple=, fecha_simple=)`. The default is the
  episode's first extreme; it no longer follows `at`.
- `suggest_intervention_form` passes the requested (or auto-detected) date,
  so the rung that is judged is the rung that is built. That is BUG-0156's
  own principle, now applied to the scalar rungs too.
- The 1a step is one of rung 2's steps, so the rungs are still nested.
- The report states both dates.

On the VAT case, after the fix:
- 1a has AIC 69.90 and ω(1)=+0.8761, identical to the estimated model;
- there is no «caída permanente» warning.

**Validation:** `tests/test_bug_0201_peldanos_escalares_en_la_fecha.py`, on
BUG-0156's witness (the mechanism starts one period before the first
extreme):
- scalar rungs at the event, rung 2 at the mechanism;
- `at_simple` wins over the episode;
- the 1a AIC and ω reproduce a step fitted at the event date on the same base;
- the report states both dates;
- the tool passes the requested date.

