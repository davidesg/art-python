---
id: BUG-0165
title: Dos renderizadores para la MISMA diagnosis — `record_version` y `full_report` se saltan `describe_diagnosis` y salen con el dibujo anterior a pyfug
status: open
severity: medium
component: figuras
found_in: 0.2.1
fixed_in:
reported: 2026-09-11
reporter: David — run 3 de SF_MEG, primer modelo de ES_CPI
tags:
  - figuras
  - duplicacion
references:
  - BUG-0081
  - BUG-0119
  - BUG-0121
---

## Summary

En el primer nodo del run 3, un mismo modelo dejó **dos figuras de residuos +
ACF/PACF con formatos distintos** —`art_diagnosis_*.png` y
`art_record_version_*.png`—, y la segunda «parece una versión antigua del
gráfico». Lo es.

Hay **dos constructores** de la figura de diagnosis y no uno:

```python
# describe.py — describe_diagnosis(), la que usa TODO el carril guiado
if _PYFUG and model.residuals is not None:
    fig_acf  = _pyfug_combined(pf, d=0, title=title_acf)     # el formato actual
    fig_hist = _pyfug_histogram(pf, d=0, title=title_hist)
else:
    fig = plot_diagnosis(result, model)                      # el respaldo

# mcp_server.py — record_version(), y full_report.py:92
fig = plot_diagnosis(diag_result, m)                         # SIEMPRE el respaldo
```

`_PYFUG` es **True** en esta instalación, así que el carril guiado toma siempre
la rama de pyfug y `record_version` **nunca**. No es un respaldo que se dispara
cuando falta algo: es una bifurcación permanente.

Medido sobre el mismo modelo:

    describe_diagnosis   1662 × 617 px  (pyfug) + histograma aparte
    plot_diagnosis       3 paneles, 15 × 5,5 in, sin títulos, ejes con
                         `$\bar{w}$ = 0.19  (0.02)` y `Q(28) = 96.1`

## Lo que NO pasa, y hay que decirlo

**Los números de debajo son los mismos.** Las dos salen de `diagnose(m)`:
`white_noise=False`, `normal=False` en las dos vías. No hay ningún valor que
discrepe — es la misma diagnosis dibujada de dos maneras.

## Impact

Medio. El daño es de **identidad de la figura**, que en este proyecto ya ha
mordido dos veces: BUG-0081 (dos series escribían el mismo
`art_boxcox_<pid>.png` y el analista leía el diagrama de la otra) y BUG-0119. En
un carril guiado el analista decide **mirando figuras**; dos dibujos distintos
del mismo modelo, en la misma pantalla y sin nada que diga que son el mismo, se
leen como que algo ha cambiado.

Costó tiempo en la corrida real: el analista paró a preguntar.

## Root cause

La de siempre, en su variante de figura: **un concepto con dos implementaciones,
y una se quedó atrás.** Cuando entró pyfug se cambió `describe_diagnosis` —la
puerta del carril— y los dos sitios que llamaban a `plot_diagnosis` por debajo
no se tocaron, porque seguían funcionando.

## Fix propuesto

Una línea en cada sitio: que `record_version` y `full_report` pidan la figura a
**`describe_diagnosis(m)`** en vez de construirla. Un solo constructor, y el
respaldo sigue siendo el respaldo para quien no tenga pyfug.

`record_version` **no puede limitarse a no dibujar**: existe para registrar un
modelo estimado por otra vía, y ahí su figura es la única que hay.

## ¿Entra en la 0.2.1 congelada?

**No, por el criterio de `ESTADO.md`.** Es «un número correcto mal presentado»,
no un número incorrecto, y ninguna puerta queda cerrada. Queda para la 0.3 salvo
que el analista lo juzgue de otro modo.

## Validation

Que las dos vías devuelvan la MISMA figura para el mismo modelo —misma huella—,
y que sin pyfug las dos caigan juntas al respaldo.
