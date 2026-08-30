---
id: BUG-0035
title: meg_reformulate never writes the .inp it was given and labels the equation with the PREVIOUS model's name — it returns a path that does not exist, so the next step dies with FileNotFoundError
status: fixed
severity: medium
component: mcp-tools
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-27
reporter: David / réplica TFM Bolivia
tags:
  - pre-contract
  - meg
  - file-convention
references:
  - src/art/mcp_server.py (meg_reformulate)
  - bugs/BUG-0035-repro/repro.py
  - tests/test_bug_0035_0036_0037_verdicts_files_and_map.py
---

## Summary

El convenio de ficheros de la suite tiene tres piezas:

```
.inp   la ESPECIFICACIÓN — los valores son semillas
.out   el registro completo de una estimación Y SU DIAGNOSIS
.pre   ese mismo .inp con las estimaciones como nuevos valores iniciales:
       un ÓPTIMO en forma reejecutable
```

Todas las herramientas de estimación escriben la terna. `meg_reformulate`
escribía `.pre` y `.out` y **no el `.inp` de `output_path`** — el fichero cuya
ruta el llamador acababa de pasarle:

```python
base = os.path.splitext(output_path)[0]
pre_path = base + ".pre"
mc.write_pre(pre_path)
mc.write_out(base + ".out")        # el .inp no se escribe nunca
```

Consecuencia inmediata, y así se encontró:

```
formal_tests(".../RATIO_m40.inp")
❌ FileNotFoundError: File not found: .../RATIO_m40.inp
```

Y consecuencia de fondo: **ese eslabón no se puede reestimar**. Reejecutar un
`.pre` VERIFICA que los parámetros no se mueven, no estima — así que sin `.inp`
no hay de dónde sacar errores típicos válidos (BUG-0027), que es justamente lo
que hace falta después de una reformulación.

## El rótulo, del mismo descuido

La ecuación se componía del modelo en memoria:

```python
eq = _equation_for_prompt(ts, mc)
```

y `ts` venía de cargar el modelo de ORIGEN, así que llevaba su nombre. La
reformulación de RATIO salía rotulada **`MODELO ESTIMADO: RATIO_m30`** estando en
`RATIO_m40`. Un bloque que se presenta al analista *tal cual* y que nombra otro
modelo es peor que uno sin nombre.

## Fix

Escribir el `.inp` y **reestimar desde él** antes de presentar:

```python
_write_inp(ts, mc, output_path)
ts, mc = _load_fitted(output_path)      # el nombre sale ya del fichero escrito
mc.write_pre(pre_path)
mc.write_out(base + ".out")
```

Reestimar no es redundante: es lo que garantiza que el `.inp` escrito reproduce
el modelo, que es la propiedad que lo hace útil. Y de paso el rótulo pasa a ser
el del fichero que el analista tiene delante.

El pie de la salida pasa a nombrar las tres rutas, como hace
`confirm_and_estimate`.

## Repro

`bugs/BUG-0035-repro/repro.py` — serie trimestral con estacionalidad estocástica,
línea base determinista, una llamada a `meg_reformulate`, y comprueba qué
ficheros aparecen y con qué nombre sale el rótulo.
