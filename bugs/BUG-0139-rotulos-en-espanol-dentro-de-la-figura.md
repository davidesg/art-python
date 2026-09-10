---
id: BUG-0139
title: Tres figuras rotulaban en español dentro del dibujo — el único texto de art que nadie traduce
status: fixed
severity: low
component: figuras
found_in: 0.2.2
fixed_in: 0.2.2
reported: 2026-09-10
reporter: David
tags:
  - figuras
  - i18n
references:
  - BUG-0135
  - BUG-0137
---

## Summary

De las ocho figuras que sobreviven al censo, **tres seguían rotulando en
español**: la calibración de distorsiones (`describe_prelim_scan`), la escalera
de Ockham (`describe_escalera`) y la respuesta de la FLT (`describe_ltf`).

Regla del analista, sentada en el censo al revisar la superposición:

> *«Los labels y nombres deberían estar en inglés dado que usamos acf/pacf, que
> son siglas en inglés… impulse en lugar de impulso, etc.»*

Y hay una razón operativa detrás, no sólo de estilo. `art` tiene dos canales de
texto y **sólo uno pasa por un traductor**:

| | quién lo escribe | quién lo traduce |
|---|---|---|
| `Description.summary` | el módulo, en español | **el asistente**, al idioma del usuario (instrucciones del servidor) |
| la FIGURA | matplotlib | **nadie** — los píxeles llegan como se dibujaron |

Un rótulo en español dentro de una figura es texto que ningún paso posterior
puede tocar. Un analista que trabaja en inglés recibía `acf` y `pacf` en inglés
y `Retardo k` debajo, en la misma figura.

## Repro

```python
from art.ltf import describe_ltf
from matplotlib.text import Text
import art.describe as d

vistas = []
real = d._fig_b64
d._fig_b64 = lambda f, *a, **k: (vistas.append(
    [t.get_text() for t in f.findobj(Text)]), real(f, *a, **k))[1]

describe_ltf([2.5, -1.0], K=12)
print([t for t in vistas[0] if "retardo" in t.lower() or "Respuesta" in t])
# ['retardo k', 'retardo k', 'Respuesta de la FLT — ω(2.5, -1.0)']
```

Lo mismo con `describe_escalera` (`peldaño 1a`, `observación (residuos)`,
`Residuos en el entorno del suceso, bajo cada peldaño`) y con
`describe_prelim_scan` (`Retardo k`, `Contribución outlier(s)`, `tipificada`,
`ACF — decide el orden MA`, y el pie entero: `omitiendo:`, `calibrado por`).

## Fix

Todo lo que se DIBUJA, en inglés. Todo lo que se NARRA se queda como está.

- `describe.py` — `outlier contribution`, `lag k`, `standardised`,
  `ACF — sets the MA order · red = the outlier's share` (ídem PACF), y el pie:
  `omitting: +12% (the anomaly was masking structure)`, `calibrated by
  threshold |z| > 3.0`.
- `escalera.py` — `rung 1a`, `residual observation`, `Residuals around the
  event, under each rung`, y los estados `holds` / `leaves a neighbour` /
  `inadequate`.
- `ltf.py` — `IRF — level`, `SRF — level (the level path)`, `first
  differences`, `gain`, `lag k`, `LTF response`.

El punto fino está en el nombre del peldaño. `Peldano.nombre` («escalón en el
nivel (permanente)») viaja a **tres sitios**: la figura, la tabla del `summary`
y el dict de datos. Traducirlo habría arrastrado la tabla al inglés y le habría
quitado al asistente el texto que sabe traducir. Así que la figura tiene su
propio nombre, `_nombre_en(p)`, derivado de `p.tipo` y `p.n_omega`, y la
narrativa no se toca.

## Test

`tests/test_bug_0139_rotulos_en_ingles.py` — recoge TODO el texto de cada
figura (`fig.findobj(Text)` más las leyendas) y busca castellano. Con el código
anterior fallan tres de las cinco; con el arreglo pasan las cinco. La quinta
prueba cierra el otro lado del reparto: verifica que `Peldano.nombre` **sigue en
español** en la tabla, para que nadie «arregle» esto traduciendo el sitio
equivocado.
