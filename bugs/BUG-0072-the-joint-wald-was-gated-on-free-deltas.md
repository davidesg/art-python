---
id: BUG-0072
title: el Wald conjunto sólo corría si había δ libres, así que para N escalones en el nivel sin denominador —el caso del nodo de episodios— no se ejecutaba nunca
status: fixed
severity: high
component: interventions
found_in: 0.1.12
fixed_in: 0.2.0 (unreleased)
reported: 2026-09-02
reporter: David / auditoría previa al nodo de intervención por episodios
tags:
  - intervention
  - wald
  - gain
  - episodes
references:
  - src/art/interventions.py (test_intervention — la guarda del Wald)
  - tests/test_bug_0071_wald_es_la_ganancia.py::test_el_contraste_corre_sin_denominador
  - docs/DISENO-nodo-intervencion.md §2.2, §4.1
  - BUG-0071 (el mismo bloque; el contraste equivocado)
---

## Summary

```python
if k > 1 and any(f for f in dlf):     # dlf = delta_free
```

La guarda exigía **δ libres** para producir el contraste conjunto. Una
intervención con varios ω y sin denominador —que es la forma general de un
episodio: N escalones consecutivos en el nivel— no recibía ningún contraste
conjunto, sin aviso y sin excepción: `wald_stat` y `wald_p` volvían `None`.

Es exactamente al revés de lo que hace falta. El contraste que el nodo de
intervención por episodios necesita es el de **ganancia nula sobre N escalones
sin δ**, y era el único caso excluido.

## Cause

Escrito como «contraste extra para FLT con denominador» en vez de como «contraste
de ganancia sobre el numerador». Con el encuadre correcto —H₀: ω(1)=0— el
denominador es irrelevante (ver BUG-0071: un cociente es cero cuando lo es su
numerador), y la guarda sobra.

## Fix

La guarda pasa a ser `if k > 1`: el contraste corre para cualquier intervención
con más de un ω libre, lleve denominador o no. `omega_1` y `gain` se calculan
siempre que haya ω, incluso con uno solo, donde el contraste conjunto no aplica
pero la ganancia sí se puede leer.

## Test

`tests/test_bug_0071_wald_es_la_ganancia.py::test_el_contraste_corre_sin_denominador`
— intervención `step` con tres ω libres y sin δ; afirma que la intervención no
tiene denominador y que `wald_stat`/`wald_p` no son `None`. Con la guarda vieja
eran `None` sin excepción.
