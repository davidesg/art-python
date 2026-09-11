---
id: BUG-0169
title: `load_data` lee un índice `YYYY-MM` como ANUAL y afirma «fechas inferidas del índice» — es la primera llamada de cualquier análisis
status: open
severity: critical
component: mcp-tools
found_in: 0.1.0
fixed_in:
reported: 2026-09-11
reporter: David — run 3 de SF_MEG, incidencia C-1
tags:
  - datos
  - numero-incorrecto
references:
  - BUG-0018
---

## Summary

Con un CSV cuyo índice es `2002-01, 2002-02, …` y sin declarar `freq`:

    ## Serie cargada: value
    Período: 2002 → 2294  (n=293, anual)
    Fechas inferidas del índice.

**No las infirió: las ignoró**, y dice lo contrario. El índice es inequívocamente
mensual. Hay que pasar `freq=12, start_year=2002, start_period=1` a mano.

Declarándolo:

    Período: 01/2002 → 05/2026  (n=293, mensual)

## Impact — CRÍTICO

Es **la primera llamada de cualquier análisis**, y de `freq` cuelga el método
entero: la estacionalidad, los armónicos, los retardos de la Q (`3f+3`), el MEG,
las fechas de toda intervención. Un IPC mensual leído como anual de 2002 a 2294
no es un análisis peor: es otro análisis, sobre una serie que no existe.

Y no avisa. La frase «Fechas inferidas del índice» **afirma que se hizo la
comprobación**, así que un analista que la lee no vuelve a mirar. En el run 3
costó rehacer la carga; en un carril autónomo no habría nadie que lo notara.

La telemetría del run lo deja ver de refilón: `load_data` aparece **4 veces** para
una sola serie en dos etapas.

## Repro

```python
ld = getattr(srv.load_data, "fn", srv.load_data)
ld(source_path="data/ES_CPI.csv", output_inp=..., column="value")
# → «Período: 2002 → 2294 (n=293, anual)»  ·  «Fechas inferidas del índice.»
```

`data/ES_CPI.csv` es `date,value` con `date` = `2002-01`, `2002-02`, …

## Fix propuesto

1. **Inferir de verdad.** Un índice `YYYY-MM` es mensual; `YYYY-QN` o `YYYYQN`,
   trimestral; `YYYY` a secas, anual. Es reconocimiento de formato, no adivinación.
2. **Y si no se puede inferir, DECIRLO** en vez de caer a anual en silencio. «No
   he sabido leer las fechas; declara `freq`» es una respuesta; «anual» es una
   afirmación falsa.
3. La frase «Fechas inferidas del índice» sólo puede imprimirse cuando de verdad
   se hayan inferido.

## Validation

`load_data` sobre un CSV con índice `YYYY-MM` y sin `freq` tiene que dar
mensual — o negarse diciendo que no sabe. Y sobre `YYYY`, anual. En ningún caso
afirmar que ha inferido lo que no ha mirado.
