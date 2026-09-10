---
id: BUG-0141
title: Dos intervenciones compartían etiqueta — la tabla de sobreparametrización decía ω(S) sin decir cuál
status: fixed
severity: medium
component: diagnosis
found_in: 0.2.2
fixed_in: 0.2.2
reported: 2026-09-10
reporter: David
tags:
  - sobreparametrizacion
  - etiquetas
references:
  - BUG-0137
  - BUG-0061
  - BUG-0140
---

## Summary

`_build_param_labels` rotulaba cada intervención por su **tipo**: `ω(S)` un
escalón, `ω(I)` un impulso, `δ(l1)` un denominador. Con dos sucesos en el
modelo —que es lo normal en cuanto la serie tiene más de uno— salían dos
`ω(S)` idénticas.

Quedó anotado durante el censo de figuras, al retirar el heatmap de BUG-0137, y
la nota decía que afectaba **también a la tabla**, que es lo que quedaba en pie:

> *«Lo que sí quedó anotado del censo y no se arregla aquí: las etiquetas no
> distinguen dos parámetros distintos —`ω(S)` aparecía dos veces, una por
> intervención, sin la fecha—, y eso afecta también a la TABLA.»*

Y esa tabla existe para una sola cosa: decir **qué par de parámetros hay que
tocar**. Una etiqueta que no identifica su parámetro no contesta esa pregunta.
Sobre el `m41` de la réplica —`impulse 2 2020` y `step 4 2008`— las etiquetas
eran `ω(I)`, `ω(I,l1)`, `ω(S)`: legibles por casualidad, porque los tipos eran
distintos. Con dos escalones no lo habrían sido.

## Repro

```python
import numpy as np, fue
from art.diagnosis import _build_param_labels

rng = np.random.default_rng(3)
y = np.cumsum(rng.normal(0, 1.0, 120)) + 100.0
ts = fue.TimeSeries(data=y.tolist(), freq=4, start=[2004, 1], name="X")
m = fue.Model(ts, d=1, boxlam=1.0, mu=0.0, estimate_mu=False, interventions=[
    fue.Intervention("step", at=19, omega=[0.0], omega_free=[True]),
    fue.Intervention("step", at=65, omega=[0.0], omega_free=[True]),
])
m.fit()
print(_build_param_labels(m))   # [..., 'ω(S)', 'ω(S)', ...]
```

## Fix

La fecha, que estaba a mano: `Intervention.at` y `series.start`, con
`guion._at_to_date` —el mismo conversor que ya usa el resto del paquete—.

    ω(S)      →  ω(S,Q4/2008)
    ω(I,l1)   →  ω(I,Q2/2020,l1)
    δ(l1)     →  δ(Q4/2008,l1)

Y es la MISMA fecha que el analista escribió en el `.inp` (`step 4 2008`) y que
lee en el `.out`: el registro queda en un solo idioma de punta a punta.

Las armónicas y `alter` **no** llevan fecha, y no es un olvido: actúan sobre
toda la muestra, su `at` no significa nada, y lo que las identifica —el orden
del armónico— ya estaba en la etiqueta.

## Test

`tests/test_bug_0141_omega_con_su_fecha.py`. La primera prueba es el defecto
exacto: dos escalones, y `labels.count("ω(S)") == 0` más
`len(set(labels)) == len(labels)`. Las demás cierran los bordes: que la fecha
sea la del `.inp`, el episodio de varias ω con fecha **y** retardo, las
armónicas sin fecha, y la ruta mensual.
