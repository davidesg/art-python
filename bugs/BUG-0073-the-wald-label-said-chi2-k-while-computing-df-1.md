---
id: BUG-0073
title: summary() rotulaba el Wald como χ²(k) mientras el cálculo usaba df=1 — el número bien y la tabla de referencia mal
status: fixed
severity: low
component: interventions
found_in: 0.1.12
fixed_in: 0.2.0 (unreleased)
reported: 2026-09-02
reporter: David / auditoría previa al nodo de intervención por episodios
tags:
  - intervention
  - wald
  - presentation
  - degrees-of-freedom
references:
  - src/art/interventions.py (InterventionTestResult.summary)
  - tests/test_bug_0071_wald_es_la_ganancia.py::test_el_rotulo_dice_chi_cuadrado_de_uno
  - bugs/README.md (la clase «la presentación contradice al contenido»)
---

## Summary

```python
lines.append(f"       Wald χ²({len(self.omega)})={self.wald_stat:.3f} …")
```

El rótulo anunciaba **χ²(k)**, con k el número de ω, mientras el cálculo era

```python
wald_p = float(sp_stats.chi2.sf(wald_stat, df=1))
```

El **p-valor estaba bien** —`g` es un escalar y el estadístico es χ²(1)—; lo que
mentía era el rótulo. Un lector que comprobase el estadístico contra la tabla
que el rótulo anuncia leería mal el contraste: con k=3, χ²(1) al 5% es 3,84 y
χ²(3) es 7,81, y todo lo que caiga entre medias cambia de veredicto.

## Cause

Presentación escrita a partir de la forma del vector ω en vez de a partir de la
restricción que se contrasta. Es **UNA** combinación lineal —ω(1)=0—, luego un
grado de libertad, con independencia de cuántos ω entren en ella.

Pertenece a la clase que fue **12 de 25** defectos de la sesión anterior: la
presentación contradiciendo al contenido, con el estadístico bien calculado.

## Fix

El rótulo dice χ²(1), y de paso el bloque imprime **lo que se está
contrastando** —el valor de ω(1)— y la lectura en una línea:

```
ganancia ω(1)=-0.1420   Wald χ²(1)=2.510  p=0.1131
H₀: ganancia nula ⇒ efecto TRANSITORIO  (no se rechaza)
```

Sin el valor de ω(1) a la vista, el p-valor era un número sin cantidad detrás.

## Test

`tests/test_bug_0071_wald_es_la_ganancia.py::test_el_rotulo_dice_chi_cuadrado_de_uno`
— exige `χ²(1)` en el texto y prohíbe `χ²(3)` con tres ω.
