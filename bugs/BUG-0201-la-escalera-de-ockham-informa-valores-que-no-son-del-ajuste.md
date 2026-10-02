---
id: BUG-0201
title: La escalera de Ockham informa de un AIC y un ω que no son los del ajuste final — y con ese ω de signo cambiado avisa de «una caída permanente» donde hay una subida
status: open
severity: medium
component: interventions
found_in: 0.2.3.dev0
fixed_in:
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
