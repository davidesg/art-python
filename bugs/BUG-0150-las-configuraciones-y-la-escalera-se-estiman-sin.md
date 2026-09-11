---
id: BUG-0150
title: Las configuraciones y la escalera se estiman SIN las intervenciones que ya lleva el modelo base
status: fixed
severity: high
component: interventions
found_in: 0.2.2
fixed_in: 0.2.1
reported: 2026-09-10
reporter: David — corrida guiada fase 1, ITCER
tags:
  - fase-1
  - intervenciones
references:
  - BUG-0083
  - BUG-0085
  - BUG-0149
---

## Summary

La llamada 2 de `guided_intervention` —el árbitro de la forma— estima cada
configuración candidata sobre un clon del modelo base que **conserva sólo los
armónicos** (`cos`, `sin`, `alter`) y **tira todas las intervenciones de
suceso** que el modelo ya lleva. Con un segundo suceso en la misma serie, la
tabla compara formas sobre un modelo que no es el del analista: los AIC, las
ganancias ω(1), sus IC y el veredicto permanente/transitorio son los de otro
modelo.

La escalera de Ockham (`escalera=True`) tiene el mismo filtro.

## Impact

Alto, y silencioso. Todo el nodo de intervención es iterativo por diseño —«una
intervención cada vez», «la escalada no para sola»—, así que **a partir de la
segunda intervención** cada tabla de configuraciones está calculada sobre la
base equivocada, y nada lo dice. Afecta a:

- la ELECCIÓN de la forma (los ΔAIC entre configuraciones);
- la ganancia y su IC, que es lo que se lee como permanente o transitorio;
- el aviso «la explicación no concuerda con el contraste», que desautoriza la
  información extramuestral del analista con esos números;
- la regla de Treadway de cada candidato (los vecinos se miden sobre residuos
  que aún llevan el suceso anterior sin intervenir).

La llamada 3 (construir) sí parte del `.pre` con todo, así que el modelo que
finalmente se construye es correcto; lo que está mal es la evidencia con la que
se eligió.

## Reproduction

ITCER, λ=0, d=1, D=0 + μ (corrida guiada fase 1). `m01` lleva ya la caída de
2008 como `Q2/2008×3`. Llamada 2 sobre `ITCER_m01.pre`, `date="Q2/2009"`:

| configuración | AIC publicado | ω(1) publicada | AIC sobre m01 (correcto) | ω(1) sobre m01 |
|---|---|---|---|---|
| Q2/2009×1 | 396,86 | +7,3680 | **373,92** | +7,11 |
| Q2/2009×2 | 396,16 | +11,6438 | **372,54** | +11,13 |
| Q2/2009×3 | 396,43 | +15,0718 | **372,43** | +14,30 |

Los valores publicados coinciden **al decimal** con m00 + el candidato, es decir,
sin la intervención de 2008 (AIC 396,86 y ω(1) 7,37 recalculados por MCO, que
es el MV exacto sin ARMA). El síntoma visible sin recalcular nada: los tres AIC
salen ~15 puntos **peores** que el del propio m01 (381,93), al que sólo se
AÑADE un parámetro que capta un residuo de |z| = 3,05.

La construcción posterior (`form="step", n_omega=1` sobre el mismo `.pre`) da
AIC 373,92 — el de la columna correcta.

## Root cause

`configuracion.py`, `evalua_configuraciones` (l. 372):

```python
base_itvs = [i for i in (model_base.interventions or [])
             if i.type in ("cos", "sin", "alter")]
...
m = fue.Model(model_base.series, interventions=base_itvs + [itv], **kw)
```

y `escalera.py`, `_estructurales` (l. 256), con el mismo filtro.

El docstring dice que `model_base` es «el modelo AJUSTADO **sin** la
intervención» — la que se estudia. El filtro implementa algo más fuerte: sin
NINGUNA intervención de suceso. Las dos cosas coinciden en la primera
intervención de una serie, que es donde se escribió y se probó.

## Fix

Conservar todas las intervenciones del base salvo, si acaso, la que cae en la
MISMA fecha/episodio que se está estudiando (el caso de «rehacer la forma de un
suceso ya intervenido»), y decirlo en la salida cuando se retira alguna. Lo
mismo en `_estructurales` de la escalera.

## Fix aplicado (11-sep-2026)

`escalera.hereda_del_base(model, at_estudiado, ventana)` — un solo sitio, que
`configuracion.py` importa. Antes el mismo filtro estaba escrito dos veces, que
es cómo se consigue arreglar la mitad.

Devuelve `(heredadas, retiradas)`: retirar una intervención en silencio es
cambiar el modelo base sin avisar, y el caso legítimo —rehacer la forma de un
suceso ya intervenido— tiene que poder decirse en la salida.

Verificado sobre el caso real: la llamada 2 en `Q2/2009` sobre `ITCER_m01.pre`
da ahora **373,92** para `Q2/2009×1` —el número calculado a mano en las notas de
la corrida— y los tres candidatos por debajo del base (381,93), con **2**
intervenciones cada uno en vez de 1.

## Validation

Prueba sobre ITCER: llamada 2 sobre `m01.pre` en `Q2/2009` debe dar para
`Q2/2009×1` el AIC de construirla (373,92 ± 0,01), y todos los AIC de la tabla
por debajo del de `m01`. Una segunda, genérica: para cualquier base con k
intervenciones de suceso, el modelo de cada candidato lleva k+1.
