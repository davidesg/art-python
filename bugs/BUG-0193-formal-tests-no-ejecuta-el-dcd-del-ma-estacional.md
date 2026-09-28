---
id: BUG-0193
title: formal_tests no ejecuta el DCD del MA estacional — dcd_s existe y está validado (BUG-0039), pero sólo lo consume el carril autónomo, así que en guiado un modelo B2 sigue sin poderse refutar
status: fixed
severity: high
component: formal-tests
found_in: 0.2.3.dev0
fixed_in: 0.2.3.dev0
reported: 2026-09-28
reporter: David — análisis guiado del airline (serie G de Box-Jenkins), preparación de la P03
tags:
  - dcd
  - seasonality
  - guided
  - wiring
references:
  - src/art/describe.py (bloque de contrastes formales, ~l. 2140-2230)
  - src/art/formal_tests.py::dcd_s
  - src/art/pipeline.py::_seasonal_ma_invertible — hoy su ÚNICO consumidor
  - bugs/BUG-0039-the-seasonal-lag-MA-had-no-non-invertibili.md
---

## Summary

`formal_tests` sobre un airline, (0,1,1)(0,1,1)₁₂, informa del DCD del MA
**regular** (H₀: θ = 1) y del DCD de sobrediferenciación regular, dice «MEG no
aplica: requiere D=0 con armónicos», y **no dice nada del MA estacional**. Es
justo el contraste que decide la ruta B2: si Θ̂ se apila en la frontera, la
`(1 − ΘB¹²)` cancela la `(1 − B¹²)` y la diferencia estacional sobraba. BUG-0039
lo implementó (`dcd_s`, con la ley de Davis, Chen y Dunsmuir, Tabla 3.2), pero el
informe de `describe.py` que alimenta `formal_tests` importa y ejecuta `dcd`,
`dcd_f`, `rv`, `meg`, `shin_fuller` y `dcd_overdiff_regular` — y **no `dcd_s`**.
El único consumidor es `pipeline._seasonal_ma_invertible`, del carril autónomo.

## Impact

Alto. BUG-0039 existía para que «un modelo B2 se pueda refutar», y en el carril
guiado —el que usan los alumnos y el analista— sigue sin poderse: el informe
calla, y el silencio se lee como «no hay nada que contrastar». Además la
asimetría es engañosa: sobre B1 el informe ofrece el MEG, sobre B2 no ofrece
nada, así que el par que adjudica la ruta estacional sólo existe de un lado.

## Reproduction

```python
from art.mcp_server import _load_ts_model
from art.formal_tests import dcd_s

ts, m = _load_ts_model(".../03-datos/ejemplos/AIRLINE/AIRLINE_m01.inp")  # airline, serie G
m.fit()
for r in dcd_s(m):
    print(r.coef_free, r.lr, r._crit_override)
# 0.5569  30.631  {'10%': 1.36, '5%': 2.31, '2.5%': 3.44, '1%': 5.12}
```

`formal_tests(inp_path=".../AIRLINE_m01.inp")` sobre el mismo modelo: aparecen
«DCD — no invertibilidad MA regular» y «DCD sobre-diferenciación regular»; el
MA estacional no aparece.

El `.inp` sale de `load_data(airline.csv, freq=12, start_year=1949)` +
`confirm_and_estimate(lam=0, d=1, D=1, q=1, Q=1, estimate_mu=False)`.

## Root cause

`src/art/describe.py`, bloque de contrastes formales: la lista de ejecuciones
(`dcd_res`, `od_res`, `ud_res`, `dcd_f_res`, `rv_res`, `meg_res`) no incluye
`dcd_s`, y no hay sección que lo presente. BUG-0039 cableó el contraste al
consumidor autónomo (`_seasonal_ma_invertible`) y no al informe.

## Fix

- En `describe.py`: `dcds_res = _try(lambda: dcd_s(model), [])` junto a `dcd_res`,
  y una sección «DCD — no invertibilidad MA estacional (H₀: Θ=1, ley DCD Tabla
  3.2, s=…)» con Θ̂, LR, crítico al 5 % de `_crit_override` y el veredicto en los
  términos de la escuela: LR ≥ crítico ⇒ la ∇ₛ es genuina (estacionalidad
  estocástica); LR < crítico ⇒ la ∇ₛ sobra (volver a B1).
- Que el texto de «MEG no aplica» sobre un modelo con D=1 remita a este contraste
  como el lado B2 del par, en vez de dejar la ruta sin nada.
- Que el mismo veredicto entre en la lógica de «Reformulación necesaria».

## Validation

- Airline (serie G): Θ̂ = 0,557, LR = 30,6 frente a 2,31 al 5 % ⇒ «la ∇₁₂ es
  genuina». Debe aparecer en el informe.
- Un caso de frontera —p. ej. el HICP de Chequia o de Luxemburgo 2002-2019, con
  Θ̂ ≈ 0,95 en (1,1,0)(0,1,1)₁₂— debe dar «la ∇₁₂ sobra».
- Test: `formal_tests` sobre un modelo con `ma_s` libre contiene la sección del
  DCD estacional.

## Resolution (2026-09-28)

`describe_formal_tests` (the report of `formal_tests`) now runs `dcd_s`
beside `dcd`, as proposed:

- a section «DCD — no invertibilidad MA estacional (H₀: Θ=1, ley DCD Tabla
  3.2, s=…)» with Θ̂, LR, the 5 % critical value of the DCD law, and the
  verdict in the school's terms (LR ≥ crit ⇒ the ∇ₛ is genuine; LR < crit ⇒
  (1 − ΘBˢ) cancels (1 − Bˢ), the ∇ₛ is superfluous, route B1);
- «MEG no aplica» on a model with ∇ₛ now points to that section as the B2
  side of the pair;
- a Θ on the wall enters «Reformulación necesaria» (back to B1, D = 0 with
  harmonics, and the MEG per frequency);
- `data["dcd_s"]` carries the same for whoever reads the structure.

**Validation:** `tests/test_bug_0193_formal_tests_ejecuta_el_dcd_estacional.py`.
Airline, series G: Θ̂ = 0.5569, LR = 30.631 against 2.31 ⇒ the ∇₁₂ is genuine
(the report's figures). The boundary case is a synthetic series with
deterministic seasonality (`tests/fixtures/bug_0193/`, seed 7): Θ̂ = 1.0000,
LR = 0.000 ⇒ the ∇₁₂ is superfluous, and the recommendation says so. The
Czech/Luxembourg HICP cases of the report were not at hand; the synthetic
case covers the same branch.
