---
id: BUG-0026
title: _write_inp emits an EMPTY ifadf line when the model carries an empty list instead of None, and the file it produces cannot be read back
status: fixed
severity: high
component: inp-builder
found_in: 0.1.11
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-26
reporter: David / réplica TFM Bolivia
tags:
  - inp-format
  - round-trip
  - ifadf
references:
  - src/art/pipeline.py:270-276 (_write_inp, la guarda `is None`)
  - src/art/pipeline.py:73-74 (create_inp — el otro escritor, que sí lo hace bien)
  - fue/src/fue/inp.py (el lector: cuenta posiciones en esa línea)
  - bugs/BUG-0026-repro/repro.py
---

## Summary

La línea `ifadf` del `.inp` especifica las **diferencias por frecuencia** e
indexa **desde f=0**, así que tiene siempre `freq//2 + 1` entradas:

| frecuencia | línea | frecuencias |
|---|---|---|
| trimestral (4) | `0 0 0` | f=0, f=1, f=2 |
| mensual (12) | `0 0 0 0 0 0 0` | f=0 … f=6 |

`_write_inp` la emitía **vacía** cuando el modelo llevaba una lista vacía. La
guarda comprueba `is None`:

```python
ifadf = getattr(model, "ifadf", None)
if ifadf is None:                     # <- fue.Model guarda [], no None
    ifadf = [0] * (freq // 2 + 1)
lines.append(" ".join(str(v) for v in ifadf))
```

y `fue.Model(ts, d=1)` sin `ifadf` lo almacena como **`[]`**, no como `None`. El
`join` sobre lista vacía produce la cadena vacía, y el lector —que cuenta
posiciones en esa línea— se desincroniza: toma la **siguiente** línea, la del
Box-Cox (` 1.00  1  0`), como si fuera la de `ifadf` e intenta `int('1.00')`.

**Un modelo que el motor acepta y estima produce un fichero que el motor no
puede leer.**

## Impact

Alta. El `.pre` es el **contrato de la suite**: `drvec` y `drtran` entran por él.
Un `.pre` ilegible no rompe sólo a ART, rompe el escalón siguiente de la
escalera — y lo hace con un `ValueError` sobre `'1.00'` que no apunta ni de lejos
a la causa.

No muerde en el flujo normal de ART, que puebla `ifadf` en todos sus caminos. Sí
muerde a quien construya un `fue.Model` mediante código — que es exactamente lo
que hacen los tests y lo que hará cualquier herramienta nueva que escriba
modelos. Apareció al preparar el banco de pruebas de las intervenciones con
función de transferencia (ω(B)/δ(B)), donde los modelos se construyen a mano.

El otro escritor del mismo módulo, `create_inp` (pipeline.py:73), lo hace bien
—`" ".join(["0"] * n_ifadf)`— lo que confirma que la forma correcta estaba
establecida y que esto es un descuido de una sola rama.

## Reproduction

```
python3 bugs/BUG-0026-repro/repro.py
```

Antes del arreglo, en trimestral y en mensual:

```
  fue.Model(...).ifadf = []   (no None: la guarda no lo cubre)
  linea ifadf escrita : ''  -> 0 entradas (esperadas 3)
  relectura           : FALLA -> ValueError: invalid literal for int() with base 10: '1.00'
```

## Root cause

`src/art/pipeline.py:272`. La guarda `if ifadf is None:` no cubre el valor que el
motor usa realmente para «sin diferencias por frecuencia», que es la lista vacía.
Es el clásico fallo de comprobar identidad con `None` donde lo que se quiere es
falsedad.

## Fix

```python
-        if ifadf is None:
+        if not ifadf:
             ifadf = [0] * (freq // 2 + 1)
```

Cubre `None` y `[]` a la vez. La longitud `freq//2 + 1` ya era la correcta.

## Validation

`tests/test_bug_0026_ifadf_line_never_empty.py`: para freq 4 y 12, que un modelo
construido sin `ifadf` escribe la línea con `freq//2 + 1` ceros y que el fichero
**se relee**; que un `ifadf` no trivial (una frecuencia activada) se conserva en
el round-trip; y que la línea nunca queda vacía. El invariante que se fija es el
del formato —número de entradas = `freq//2 + 1`— no la cadena literal.
