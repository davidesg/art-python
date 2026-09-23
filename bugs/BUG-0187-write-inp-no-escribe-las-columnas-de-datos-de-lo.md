---
id: BUG-0187
title: _write_inp no escribe las columnas de datos de los deterministas NO ESTANDAR: un regresor externo vuelve identicamente cero y el lector lo relee sin avisar
status: fixed
severity: high
component: inp-builder
found_in: 0.2.1
fixed_in: 0.2.2
reported: 2026-09-16
reporter: David (estudio del contrato de ficheros, bateria de conformidad)
tags:
  - inp
  - deterministas
  - contrato
references: []
---

## Summary

El `.inp` lleva los datos en columnas: la primera es la serie, y **detrás va
una columna por cada determinista NO ESTÁNDAR** — el regresor externo que el
usuario aporta, lo que el formato llama «non-standard deterministic
variables» en la propia etiqueta de la sección:

    ** Time series (stochastic and non-standard deterministic variables):

`_write_inp` escribe sólo la primera. El bucle de `pipeline.py:738-739` itera
sobre `ts.data` y nada más; ninguna de las 180 líneas anteriores mira
`intervention.data`.

El fichero que sale no está roto a la vista —tiene el determinista declarado,
con su tipo, su orden de ω y su valor inicial— pero **su contenido ha
desaparecido**. Y no salta ningún error al releerlo, porque el lector rellena
la columna que falta con ceros (`fue/inp.py:502`). El modelo que vuelve tiene
un regresor idénticamente nulo, con su ω estimable, que no puede explicar
nada. La estimación converge, el diagnóstico aprueba y el efecto medido es
cero.

## Impact

Alto, y silencioso en los dos extremos. Cualquier modelo con un regresor
externo que pase por `_write_inp` pierde el regresor. No hay excepción, ni
aviso, ni diferencia visible en el fichero salvo contar las columnas.

Es además la mitad de una pareja: `fue/inp.py:502` es el eslabón que lo
convierte en corrupción en vez de en un error. Reportado aparte en el
registro de fue.

Fuera de Python el mismo fichero es peor: `fue` 1.14 lo RECHAZA
(«observation NN of MM expected»), pero `fue` 1.13 lo lee en silencio
inventándose observaciones.

## Reproduction

Con un `.inp` que tenga un determinista no estándar con datos — por ejemplo
`R.2_5.inp` del corpus de conformidad (68 observaciones, un regresor de tipo
`custom` en la posición 3):

```python
import fue
from art.pipeline import _write_inp
import numpy as np

ts, m = fue.load("R.2_5.inp")
print(np.asarray(m.interventions[3].data)[:4])
# [-1.6672321  -1.54633496 -1.46869694 -1.52820563]

_write_inp(ts, m, "ida_y_vuelta.inp", refactor=m.refactor)

ts2, m2 = fue.load("ida_y_vuelta.inp")
print(np.asarray(m2.interventions[3].data)[:4])
# [0. 0. 0. 0.]          <-- sin una sola advertencia
```

Contando columnas en los dos ficheros:

    $ awk '/Time series/{f=1;next} f&&NF{print NF; exit}' R.2_5.inp
    2
    $ awk '/Time series/{f=1;next} f&&NF{print NF; exit}' ida_y_vuelta.inp
    1

## Root cause

`src/art/pipeline.py:736-739`:

```python
    "** Time series (stochastic and non-standard deterministic variables):",
]
for v in np.asarray(ts.data, dtype=float):
    lines.append(f"{v:.6f} ")
```

La etiqueta que la propia función escribe anuncia las columnas que la función
no escribe.

El escritor hermano en el mismo módulo, `_write_bare_inp` (línea 81), tiene el
mismo hueco; y los dos declaran en el docstring replicar
`gtk_fue file_io.c:write_inp_file()`, que **sí** las escribe
(`gtk_fue.09/src/file_io.c:226-244`), igual que `fue/report.py::write_pre`
(`report.py:1216-1223`) y que el motor en C (`fue-1.14/src/fue.c:2333-2339`).
De las cinco implementaciones del formato, ésta es la única que no.

## Fix

Emitir las columnas junto a cada observación, en el orden en que los
deterministas no estándar aparecen declarados — que es el orden que el lector
asume (`fue/inp.py:492-506`):

```python
nonstd = [it for it in (model.interventions or []) if it.type == "custom"]
cols   = [np.asarray(it.data, dtype=float) for it in nonstd]
for i, v in enumerate(np.asarray(ts.data, dtype=float)):
    fila = f"{v:.10f}" + "".join(f" {c[i]!r}" for c in cols)
    lines.append(fila)
```

Y negarse a escribir —como hace `report.py:1555-1558` ante un tipo sin
representación— si un determinista no estándar viene sin datos: escribir la
declaración sin la columna es exactamente lo que produce el fichero que miente.

El `.10f` de la serie es el otro defecto de la misma línea, reportado aparte.

## Validation

La batería de conformidad del formato univariante
(`atws/conformidad/bateria.sh`), que lee el fichero original y el reescrito
con `fue.load()` y compara el MODELO y no los bytes. El actor `pyart` acusa
hoy 884 diferencias de la forma `model.interventions[i].data[i]` repartidas
por los ficheros de la familia `R.*`. La corrección tiene que llevarlas a
cero sin mover las de los demás campos.

## Resolución (0.2.2)

Confirmado tal cual: `_write_inp` sólo escribía la columna de la serie.

- `_write_inp` emite, detrás de cada observación, una columna por cada
  determinista `custom` en el orden de declaración (el que asume `fue.load`).
- Se NIEGA a escribir (`ValueError`) si un determinista no estándar no trae
  datos para las `n` observaciones: la declaración sin su columna es el fichero
  que miente.
- `_write_bare_inp` no tiene el hueco: no declara deterministas (`0`). Sí tenía
  el de BUG-0188, arreglado allí.
- Ojo con el fix propuesto en el informe: `f" {c[i]!r}"` sobre un array de
  numpy escribe `np.float64(...)` en numpy 2. Se escribe `float(c[i])!r`.
- Mismo linaje, arreglado de paso: la línea de un `compimp` ANUAL salía como
  `impulse` (otro regresor), y el armónico de un `cos`/`sin` pasaba por `int()`
  (cos 1.5 → cos 1).
- Del lado de fue: el lector ya no rellena con ceros (fue/BUG-0017), y
  `write_pre` se niega igual ante un `custom` sin datos.

Validación: `tests/test_bug_0187_0189_contrato_ficheros.py`; batería
`bateria.sh pyart`: 0 diferencias en `model.interventions[i].data` (eran 884).
