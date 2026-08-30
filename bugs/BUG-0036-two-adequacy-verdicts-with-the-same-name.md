---
id: BUG-0036
title: two adequacy verdicts with the same name and no rule — confirm_and_estimate publishes residuals_ok while formal_tests keeps its own failure list, and they diverge in BOTH directions
status: fixed
severity: high
component: formal-tests
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-27
reporter: David / réplica TFM Bolivia
tags:
  - diagnosis
  - contradictory-output
  - autonomous
references:
  - src/art/describe.py (describe_formal_tests, la guarda de BUG-0025)
  - src/art/diagnosis.py (DiagnosisResult.residuals_ok / .clean)
  - bugs/BUG-0036-repro/repro.py
  - tests/test_bug_0035_0036_0037_verdicts_files_and_map.py
---

## Summary

El mismo modelo, el mismo `.inp`, dos veredictos opuestos del mismo sistema:

```
confirm_and_estimate  → Veredicto: **APROBADO ✓**
formal_tests          → ⚠ **Este modelo todavía NO es adecuado.**
```

No era un error de cálculo. Eran **dos predicados distintos con el mismo
nombre**: `confirm_and_estimate` publica `DiagnosisResult.residuals_ok`, y la
guarda de `formal_tests` (introducida por BUG-0025, con buen motivo) construía su
propia lista de fallos.

Y no es que uno fuera un caso particular del otro. **Divergían en las dos
direcciones:**

| criterio | `residuals_ok` | guarda de `formal_tests` |
|---|---|---|
| ruido blanco (Q) | sí | sí |
| normalidad (JB) | sí | sí |
| **residuos extremos** | **no** — y a propósito | **sí** |
| **estacionalidad residual** | **sí** | **no** |
| media centrada | no (está en `.clean`) | no |

El docstring de `residuals_ok` explica por qué deja los extremos fuera: gobiernan
el **bucle de intervenciones**, no la adecuación — *«añadir una intervención
arregla un residuo que se porta mal; no arregla una media que falta»*. Es una
distinción deliberada y correcta. El problema es que la otra mitad del sistema no
la conocía.

## Por qué importa más de lo que parece

A un analista humano le irrita y sigue. A un LLM decidiendo solo **le deja sin
regla**, y encontrado así: en el recorrido autónomo de ITCER, el modelo m21
aprobaba la diagnosis y `formal_tests` lo rechazaba por un único residuo con
z=+3,36 y JB=0,873 (p=0,65).

Y el incentivo que crea es el peor posible: **añadir un parámetro no
significativo para hacer desaparecer el extremo y cerrar la guarda**. En ese caso
concreto el candidato era un segundo impulso con ω = +2,4744, t = 1,66, que
empeoraba el BIC. Un criterio de presentación no justifica un parámetro que no
está.

## Fix

Un solo predicado, el que ya existía, y los extremos como **aviso**:

```python
if not _dg.white_noise:            _dg_fallos.append(...)
if not _dg.normal:                 _dg_fallos.append(...)
if not _dg.centred:                _dg_fallos.append(...)   # faltaba
if _dg.seasonal detectada:         _dg_fallos.append(...)   # faltaba
if _dg.extreme:                    _dg_avisos.append(...)   # ya no bloquea
```

Cuando no hay fallos pero sí extremos, la salida los nombra sin bloquear:

> ℹ La diagnosis es adecuada, y queda una salvedad: 1 residuo(s) extremo(s), el
> mayor obs 21 con z = +3.36.
>
> No invalida lo que sigue —las nulas de esta etapa suponen ruido blanco, y el
> modelo lo es— pero conviene saber que está ahí: un extremo aislado suele
> señalar un episodio cuya FORMA todavía no está bien especificada. Añadir un
> parámetro no significativo sólo para hacerlo desaparecer no es la respuesta.

Ese último matiz es el que importa: en ITCER el extremo **sí** señalaba algo real
—el rebote de 2009:2, que pide un ω(B) que ART todavía no expresa— y la respuesta
correcta no era ni bloquear ni ignorarlo, sino nombrarlo.

## Lo que NO cambia

La guarda de BUG-0025 sigue en pie y sigue siendo necesaria: un contraste formal
sobre un modelo inadecuado no es un contraste débil, no es un contraste. Lo único
que cambia es **qué cuenta como inadecuado**, que ahora es una sola cosa.

## Repro

`bugs/BUG-0036-repro/repro.py` — paseo aleatorio con un salto aislado
**calibrado**: Q pasa, JB pasa, y queda un residuo por encima de |z|=3. Un salto
mayor rompe también la JB y entonces los dos veredictos coinciden en rechazar —
por eso el testigo se calibra y no se exagera.
