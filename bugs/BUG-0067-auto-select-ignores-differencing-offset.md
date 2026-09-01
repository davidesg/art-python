---
id: BUG-0067
title: el auto-select de suggest_intervention_form mapea la fecha del residuo sin el desfase de la diferencia (d + D·s) — con un modelo diferenciado la intervención cae en el mes equivocado
status: fixed
severity: medium
component: mcp-tools
found_in: 0.1.12 (unreleased)
fixed_in:
reported: 2026-09-01
reporter: David / benchmark guiado ES_CORE — D=1 (∇∇₁₂), auto-select erróneo
tags:
  - intervention
  - auto-select
  - differencing
  - date-mapping
references:
  - src/art/mcp_server.py (suggest_intervention_form — rama date=="")
  - src/art/diagnosis.py (DiagnosisResult.extreme — índice 1-based del RESIDUO)
  - bugs/BUG-0067-repro/repro.py
---

## Summary

El **auto-select** de `suggest_intervention_form` (rama `date==""`) mapea el
residuo más extremo a una fecha usando el índice del **residuo** como si fuera
el índice de la **serie**, sin compensar el desfase que introduce la
diferenciación (`d + D·s` observaciones perdidas). Para un modelo diferenciado,
la intervención auto-detectada cae en el mes equivocado.

Caso real — ES_CORE D=1 (∇∇₁₂, desfase 13):

```
escaneo → obs 57 (1-based del residuo)   z=+3.36
auto-select → at_0 = 57−1 = 56 → 09/2006   ← fecha EQUIVOCADA
correcto   → 56 + 13 = 69     → 10/2007   ← el anómalo real
```

El step añadido cayó en 09/2006 (ω=+0.049, t≈0.4, insignificante) y **no
capturó** el anómalo; el residuo siguió en z=+3.32 y el AIC empeoró. El step
correcto (10/2007) sí funcionó (ω=+0.389, t≈3.6).

## Root cause

`diagnose()` devuelve `extreme` como `(i+1, z)` donde `i` es el índice **0-based
del residuo** (diagnosis.py: `extreme = [(i + 1, float(z)) for i, z in
enumerate(r_z) …]`). El auto-select hace:

```python
_, obs_1based = max(candidates)
at_0 = obs_1based - 1            # índice del RESIDUO, no de la serie
total = (s0p - 1) + at_0
auto_date = f"{total % 12 + 1:02d}/{s0y + total // 12}"
```

`at_0` es el índice del residuo, pero se usa como índice de la serie. Para d=1,
D=1 (desfase 13) la fecha sale 13 meses antes. Para d=1, D=0 (desfase 1) sale
1 mes antes — error pequeño pero presente en la ruta más común.

## Fix

Sumar el desfase de la diferenciación antes de mapear la fecha (y antes de crear
la intervención, cuyo `at` también debe ser el índice de la serie):

```python
resid_start = m_src.d + m_src.D * freq
at_0 = obs_1based - 1 + resid_start
```

(equivale a usar `_resid_start(m_src)` de `describe.py`).

## Validation

`bugs/BUG-0067-repro/repro.py` — serie sintética mensual con un escalón conocido
en 2003-01, modelo d=1 D=1 sin la intervención; comprueba que el auto-select
mapea el residuo más extremo 13 meses antes de la fecha real. Sale 1 con el bug.


---

## Arreglado el 2026-09-02 — y eran TRES sitios, no uno

Confirmado sobre el ITCER de la réplica (d=1, desfase 1): el escaneo de anómalos
dice —bien— «Q4/2008», y el auto-select colocaba la intervención en **Q3/2008**.
Un trimestre antes del desplome de Lehman, en silencio, y sobre el modelo que se
estima. **Una fecha equivocada es un modelo equivocado.**

Al arreglarlo aparecieron otros dos usos del mismo desajuste en el mismo bloque:

1. **La fecha auto-seleccionada** — `at_0 = obs_1based − 1`, el índice del
   residuo tomado como el de la serie. Es el que este informe describía.
2. **La comprobación de «ya cubierto»** — `(obs − 1) not in existing_at`
   comparaba un índice de residuo contra `itv.at`, que es de la serie. Daba por
   cubierta la intervención equivocada, así que podía volver a proponer un punto
   ya intervenido y saltarse otro.
3. **`decide_form(at_0 + 1, extreme_obs)`** — decide escalón contra impulso
   mirando si un vecino también es extremo, y recibía un índice de serie contra
   un conjunto de índices de residuo. **Este afectaba también a la rama de fecha
   MANUAL**, donde `at_0` siempre estuvo en el espacio de la serie: o sea que la
   forma se decidía con los vecinos desplazados aunque la fecha fuera correcta.

La corrección convierte **una vez**, al entrar, y a partir de ahí todo va en
índices de la serie; los extremos se suben al mismo espacio en vez de bajar
`at_0`, que es el que acaba en el modelo.

Tests en `tests/test_bug_0067_desfase_de_la_diferenciacion.py`: la fecha, el `at`
que llega al modelo, y la no repetición.

## Nota

Este número colisionó con un informe de la réplica del TFM de Bolivia escrito el
mismo día; aquél se renumeró a BUG-0070. Ver `bugs/README.md`.
