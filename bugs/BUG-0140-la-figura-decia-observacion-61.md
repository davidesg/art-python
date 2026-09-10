---
id: BUG-0140
title: Las figuras del nodo de intervención rotulaban «observación 61» teniendo el calendario en la mano
status: fixed
severity: medium
component: figuras
found_in: 0.2.2
fixed_in: 0.2.2
reported: 2026-09-10
reporter: David
tags:
  - figuras
  - intervenciones
references:
  - BUG-0067
  - BUG-0135
  - BUG-0139
---

## Summary

La escalera de Ockham y la superposición —las dos figuras del nodo de
intervención— rotulaban su eje-x con **índices de observación**:

    observación (residuos)      ← escalera
    Overlay around obs 65       ← superposición

El analista no trabaja en ese idioma en ningún otro sitio. Escribe la fecha en
el `.inp`:

    step 4 2008

la lee en el `.out`, la discute con ella —«el escalón de 4Q/2008»— y la publica
así. La figura era el **único** punto del flujo donde tenía que traducir a mano
de un índice a un trimestre. Y encima con una trampa: sobre residuos de un
modelo diferenciado el índice **no** es el de la serie, porque `d + D·s`
observaciones se las comió la diferenciación (BUG-0067). La conversión correcta
exige saber `start`, `freq` y el desfase, y hacerla de cabeza cada vez.

**El calendario ya estaba ahí.** `model.series` lleva `start` y `freq`; el
desfase sale de `model.d` y `model.D`. No faltaba un dato: faltaba leerlo.

## Repro

```python
import numpy as np, fue
from art.episodes import agrupa_episodios
from art.escalera import escalera_de_ockham, describe_escalera

rng = np.random.default_rng(11)
y = rng.standard_normal(120); y[64] += 9.0
ts = fue.TimeSeries(y.tolist(), freq=4, start=(2004, 1), name="SINT")
m = fue.Model(ts, d=0, mu=0.0, estimate_mu=False); m.fit()
r = np.asarray(m._result.residuals, float); z = (r - r.mean()) / r.std(ddof=0)
ext = [(i+1, float(z[i])) for i in range(len(z)) if abs(z[i]) > 3]
ep = max(agrupa_episodios(ext, ventana=2, d=0), key=lambda e: e.z_max)
describe_escalera(escalera_de_ockham(m, ep))   # eje: 55, 60, 65, 70…
```

La serie arranca en 2004Q1 y el suceso está en la observación 65 — Q1/2020. La
figura decía `65`.

## Fix

Un solo helper, `describe._eje_de_fechas(ax, freq, start, desfase)`, con un
`FuncFormatter` sobre el eje: los ticks los sigue eligiendo matplotlib y sólo
cambia cómo se escriben. Se usa en las dos figuras.

- **escalera** — deriva el calendario de `vivos[0].model.series` y el desfase de
  `d + D·s`. No hizo falta tocar ninguna firma: el dato ya cruzaba la frontera.
- **superposición** — recibe `observado` como una **lista pelada**, así que sí
  hizo falta. Tres parámetros nuevos, `freq`, `start` y `desfase`, que viajan
  **juntos** porque por separado no significan nada. Sin ellos la figura sigue
  diciendo `observation`, que es lo honrado cuando de verdad no hay calendario
  —y así lo mantienen los usos sueltos y los tests—.
- Los dos sitios del servidor que la llaman (`intervention_plot` y
  `guided_intervention`) pasan el calendario, con el desfase que corresponde:
  cero sobre la serie, `d + D·s` sobre residuos.

El título también: `Overlay around obs 65` → `Overlay around Q1/2020`.

## Test

`tests/test_bug_0140_fechas_en_los_ejes.py`. Lo que de verdad podía romperse es
**la cuenta**, y va primero: la misma fecha alcanzada por tres desfases
distintos (serie, `d=1`, `d=1 D=1 s=4`) tiene que dar `Q2/2020` en los tres.
Luego los ticks del helper —incluido `Q4/2008`, que es la cuenta que escribe
`step 4 2008`—, las dos figuras, y el contrato de la lista pelada: sin
calendario, `observation` y ninguna fecha inventada.
