---
id: BUG-0171
title: La fecha extramuestral se compara como TEXTO — `03/2022` no encuentra `3/2022`, y la información del analista se pierde en silencio
status: open
severity: high
component: interventions
found_in: 0.2.0
fixed_in:
reported: 2026-09-11
reporter: David — run 3 de SF_MEG, incidencia C-15
tags:
  - intervenciones
  - extramuestral
references:
  - BUG-0155
  - BUG-0157
---

## Summary

`evento_desde="03/2022"` sobre un conjunto que contiene `3/2022×4` responde:

    ⚠ La fecha declarada (03/2022) no coincide con ningún arranque candidato.

Y la tabla de arriba, en la misma salida, lista `3/2022×4`. Medido:

    evento_desde='03/2022'  →  fija NADA  (la información se pierde)
    evento_desde='3/2022'   →  fija 3/2022×4

La causa es una comparación de cadenas:

```python
# configuracion.py — fijado_por_lo_extramuestral
return next((c for c in self.vivos if c.fecha == self.info.desde), None)
```

y las etiquetas se construyen **sin cero a la izquierda** (`f"{q}/{a}"`), mientras
que la llamada 1 del nodo escribe las fechas **con** cero. **El uso normal falla**:
el analista copia la fecha de la salida anterior y no se la aceptan.

## Impact

Alto, y es de método. `evento_desde` es una de las dos cosas que **identifican de
verdad** la configuración cuando el dato no identifica — el propio informe lo
dice: «la fecha en que empezó el suceso fija el arranque, y con el arranque fijo
el resto se estima». Perderla:

* deja la elección a merced del AIC, que es lo que BUG-0157 acaba de documentar
  como peligroso;
* y hace que la comparación con la naturaleza declarada se haga contra el
  candidato de **mejor AIC** en vez de contra el que el analista nombró.

En el run 3, con la fecha ya declarada, el «Veredicto», la figura y la «Siguiente
llamada» seguían proponiendo `2/2022×5` — otra configuración— sin que nada
indicara que la declaración se había descartado.

Y el aviso que sale es **engañoso**: «no coincide con ningún arranque candidato»
sugiere que el analista se equivocó de fecha, cuando la fecha es exactamente la
que la herramienta imprimió.

## Fix propuesto

Comparar **fechas**, no cadenas: normalizar las dos partes a `(período, año)`
antes de comparar. Un `03/2022`, `3/2022` y `Q1/2022` mal escrito son problemas
distintos y sólo el último merece un aviso.

Y el aviso, cuando de verdad no haya coincidencia, debe **listar los arranques
disponibles** en vez de dejar al analista adivinando cuál esperaba la herramienta.

## Validation

`evento_desde` con y sin cero a la izquierda fija el mismo candidato. Y una fecha
que de verdad no esté entre los candidatos produce un aviso que dice cuáles hay.
