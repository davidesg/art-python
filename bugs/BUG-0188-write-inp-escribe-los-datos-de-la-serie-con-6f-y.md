---
id: BUG-0188
title: _write_inp escribe los datos de la serie con %.6f y los trunca: el mismo defecto que el GUI en C documenta haber arreglado, y su escritor hermano _write_bare_inp usa .10f
status: fixed
severity: medium
component: inp-builder
found_in: 0.2.1
fixed_in: 0.2.2
reported: 2026-09-16
reporter: David (estudio del contrato de ficheros, bateria de conformidad)
tags:
  - inp
  - precision
  - contrato
references: []
---

## Summary

`_write_inp` escribe cada observación con `f"{v:.6f} "`. Seis decimales fijos.
Una serie cuyos datos vengan con más precisión —que es lo normal en un índice
deflactado o en una serie en logaritmos por 100— sale redondeada, y el
redondeo es permanente: el fichero es la única copia.

No es una diferencia estética. El `.inp` es la entrada de una estimación por
máxima verosimilitud exacta; cambiar el sexto decimal de la serie cambia la
verosimilitud, y con ella los parámetros, ℓ, AIC y BIC. Dos modelos
comparados a través de ficheros escritos por rutas distintas se comparan sobre
datos distintos.

## Impact

Medio. No corrompe la estructura del modelo —el fichero se lee bien— pero
degrada los datos en cada paso del ciclo `.inp → .pre → .inp`, y lo hace de
forma acumulativa si el ciclo se repite.

El propio módulo se contradice: su escritor hermano `_write_bare_inp`
(`pipeline.py:81`) usa `.10f`. Las otras implementaciones del formato están
por encima: el motor en C y `report.py::write_pre` usan `%.10f`
(`fue-1.14/src/fue.c:2335`, `report.py:1220`), y el GUI en C usa un formato de
precisión exacta —el mínimo de decimales que relee idéntico— tras arreglar
exactamente este defecto (`gtk_fue.09/src/file_io.c:226-244`, con el
comentario que lo documenta).

## Reproduction

```python
import fue
from art.pipeline import _write_inp

ts, m = fue.load("RIPC.3.inp")      # corpus de conformidad
_write_inp(ts, m, "vuelta.inp", refactor=m.refactor)
ts2, _ = fue.load("vuelta.inp")

for i, (a, b) in enumerate(zip(ts.data, ts2.data)):
    if abs(a - b) > 1e-12:
        print(i, repr(a), repr(b))
```

```
72 0.446725567 0.446726
73 0.4496349247 0.449635
74 0.452366535 0.452367
75 0.4564665218 0.456467
76 0.4574022922 0.457402
77 0.4562660489 0.456266
```

Seis observaciones de 78 cambian. Las 72 primeras sobreviven sólo porque ya
venían con seis decimales o menos.

## Root cause

`src/art/pipeline.py:738-739`:

```python
for v in np.asarray(ts.data, dtype=float):
    lines.append(f"{v:.6f} ")
```

El `.6f` es correcto para los PARÁMETROS —son semillas, y seis decimales
sobran— y se copió a los DATOS, que no son semillas: son la observación.

## Fix

Escribir la representación más corta que relea exacta, que en Python es
`repr(float)`:

```python
for v in np.asarray(ts.data, dtype=float):
    lines.append(f"{v!r} ")
```

`.10f` también vale y es lo que hace el resto de la familia, pero fija el
número de decimales en vez de la identidad del valor. La prueba de que un
formato de datos es correcto es `float(escrito) == original`, y sólo `repr`
la cumple para todo float.

Lo mismo en `_write_bare_inp` (`pipeline.py:81`), que con `.10f` está mejor
pero no es exacto.

## Validation

La batería de conformidad (`atws/conformidad/bateria.sh`, actor `pyart`)
reporta hoy 27 ficheros con diferencias en `ts.data` / `model.series.data`.
La corrección tiene que llevarlas a cero. El criterio de la batería es el
correcto: no compara bytes, compara lo que el lector ve.

## Resolución (0.2.2)

Confirmado. `_write_inp` y `_write_bare_inp` escriben los datos con
`repr(float(v))`, la representación más corta que relee idéntica (el `float()`
evita el `np.float64(...)` de numpy 2).

Consecuencia que conviene saber: `fue.write_pre` escribía los datos a `.10f`,
así que un `.inp` exacto y su `.pre` pasaban a estimar sobre datos distintos. Se
arregla en fue (los datos del `.pre` salen exactos, mismo byte cuando `.10f` ya
basta). `test_bug_0090::test_los_valores_coinciden...` comparaba parámetros con
`atol=1e-6`, lo que cumplían por casualidad los datos a `.6f`; con los datos
exactos el AR del `.pre` (sembrado a `.4f`, una iteración) queda a 1,8e-6 con ℓ
igual a 1e-6. Se ajusta a `atol=1e-5` —la tolerancia del optimizador— con la
explicación en el test.

**Y un testigo que dependía del redondeo.**
`test_bugs_0161_0163::test_la_semilla_va_en_cero_y_eso_esta_MEDIDO` mide que la
semilla δ=0,9 cae en un óptimo espurio (AIC 1864,56 contra 1616,41). Ese
óptimo sólo existe sobre la serie redondeada a `.6f`; con los datos exactos las
dos semillas convergen al mismo sitio. El test reproduce ahora la serie tal como
se midió (redondeada) y lo dice en su docstring. La regla de sembrar δ en 0 no
cambia, pero su evidencia es más frágil de lo que el test daba a entender.

Validación: `tests/test_bug_0187_0189_contrato_ficheros.py`; batería
`bateria.sh pyart`: 0 ficheros con diferencias en `ts.data` (eran 27).
