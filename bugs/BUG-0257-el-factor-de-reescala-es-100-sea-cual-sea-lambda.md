---
id: BUG-0257
title: El factor de reescala es 100 sea cual sea λ y el tamaño de la serie — nadie comprueba que lo que el optimizador recibe esté en la banda en que trabaja
status: fixed
severity: high
component: pipeline
found_in: 0.2.4
fixed_in: 0.2.5
reported: 2026-11-15
reporter: David / Claude — revisión de incoherencias entre componentes antes de mtram
tags:
  - scale
  - lambda
  - refactor
  - suite
references:
  - src/art/pipeline.py:939 (_RESCALE_FACTOR = 100.0), :1539 (_build_arma_on_model), :78 (el esqueleto)
  - src/art/mcp_server.py:2882 (create_inp), _write_inp (el aviso de BUG-0085 cuando el factor no es 100)
  - drtran pre.check_scale (la banda 0.01-100 y la medición de drtran BUG-3)
  - BUG-0033, BUG-0085, BUG-0253, BUG-0258, BUG-0259 (la misma escala por otros caminos)
---

## Summary

fue estima sobre `refactor`·BoxCox_λ(y), y art escribe siempre `refactor=100`:
lo fija al crear el `.inp` (`create_inp`, antes de saber λ) y al construir cada
modelo (`_build_arma_on_model`), y `_write_inp` avisa si un modelo trae otro
(BUG-0085). Con logaritmos ×100 es lo que se quiere: pone la serie en tanto por
ciento. Con λ ≠ 0 el tamaño de lo que fue optimiza va como
**100·cv·nivel^λ**, y el ×100 deja de servir:

| nivel | λ | sd de 100·BoxCox(y) (variación del 1 %) |
|---|---|---|
| 100 | 1 | 121 |
| 100 | 0 | 1.21 |
| 100 | −1 | 0.0121 |
| 10 000 | 1 | 12 500 |
| 10 000 | −0.5 | 0.0125 |
| 10 000 | −1 | 0.000125 |

El optimizador (qnewtopt, con el tamaño típico de los parámetros fijo en 1)
solo es sensible a la escala por μ, los ω deterministas y los coeficientes
cruzados; AR y MA no dependen de ella. Medido en fue, drtran y drvarma
(estudio del 15-nov-2026), hay dos condiciones:

- la **dispersión** de la serie estacionaria: banda segura [0.1, 1000]; los
  fallos empiezan una década más allá por cada lado;
- con d = 0, la **razón nivel/dispersión**: a 10⁶ es marginal y a 10⁸ falla
  aunque la dispersión sea 1. Ningún factor la arregla, y es lo que agrava
  λ < 0: (y^λ − 1)/λ vale ≈ −1/λ más una variación diminuta.

Con logaritmos y 100 el corpus de la suite está siempre dentro (71 modelos:
0.29 a 39). Fuera de los logaritmos no hay garantía, y art ni lo mide ni lo
dice.

## Impact

Medido con dos series sintéticas, Yₜ = 0.5Yₜ₋₁ + 0.4Xₜ₋₁ + aₜ en logs, en torno
a 10 000, λ = −1, cada una un AR(1) con μ estimado por fue y llevado a mtram
(`BUG-0257-repro/transfer.py`):

```
refactor=100   status: stopped without improvement (termcode=3, iterations=3)
               GANANCIA = omega(1) = +0.533722   (e.t. 84.775248,  t = 0.01)
refactor=1e6   status: CONVERGED (step) (termcode=2, iterations=16)
               GANANCIA = omega(1) = +0.385311   (e.t. 0.046545,  t = 8.28)
```

Con el factor de art la transferencia no se estima (caso marginal: depende de
la muestra): se queda en la semilla, con un error típico de 85 y t = 0.01, y mtram lo lee como «ω no se distingue de −1:
el tiempo muerto es mayor» — una conclusión sobre el modelo que es un artefacto
de la escala. Con el factor que deja la serie en ~1, t = 8.28. Con nivel 100 y
λ = −1 (sd 0.012) todavía converge: el fallo empieza entre 1e-2 y 1e-4.

Y en sima, con las mismas series (200 observaciones), el VARMA no se mueve del
sistema diagonal y lo presenta como resultado:

```
factor=100   optimiser: stopped: the last step found no lower point (1 iterations)
             AR1[Y<-X]   0.000000   0.100000   0.00
             against the diagonal system: LR = 0.000, df = 3, p = 1.0000
factor=1e4   AR1[Y<-X]   0.457730   0.037614  12.17 *
             against the diagonal system: LR = 120.927, df = 3, p = 0.0000
```

«No hay dinámica cruzada» es aquí un artefacto de la escala.

Dentro de art λ < 0 no lo propone la política (`decide_lambda` da 0 o 1), y
`guided_identification` y `build_model` no lo aceptan: `lam=-1` es su centinela
de «decide tú». Entra por `confirm_and_estimate`, por un `.inp` escrito a mano,
y por cualquier `.pre` que fue o el analista traigan a mtram o sima, que
aceptan cualquier λ.

## Reproduction

`bugs/BUG-0257-repro/repro.py`: dos series en torno a 10 000 (λ = 1 y λ = −1)
estimadas con `confirm_and_estimate`; mide la sd de lo que fue optimiza con el
factor que art escribió. Sale con 1 mientras alguna queda fuera de
[0.1, 1000] sin que art lo diga. `transfer.py`, al lado, es lo que cuesta en
mtram (necesita drtran; no cuenta para el código de salida).

## Root cause

La convención se escribió para logaritmos (docs/RESCALING_ARCHITECTURE.md:
«estima sobre 100·log y, que es lo que hace que σ̂ₐ se lea en tanto por
ciento») y se aplica a todo λ. Además se decide al crear el `.inp`, antes de
que λ exista.

## Fix

`pipeline.factor_de_reescala`, con la regla de `fue.scale` (fue ≥ 0.1.22), una
para toda la suite:

- **100 sigue siendo la convención.** Con logaritmos cae siempre dentro de la
  banda y no se elige por los datos.
- Al construir el modelo —con λ, d y D ya fijados— se mide lo que recibirá el
  optimizador. Si con 100 la dispersión cae fuera de [0.1, 1000] se elige otra
  potencia de 10 que el formato aguante; el factor del fichero base se hereda
  mientras valga.
- La ecuación avisa (`describe.aviso_de_escala`) cuando la serie queda fuera
  de la banda con el factor que trae el fichero —p. ej. logaritmos con factor
  1, lo que escribe la GUI de atsw-gui— o cuando el nivel es más de un millón
  de veces la dispersión, que ningún factor arregla.
- `_write_inp` escribe el factor sin perderlo (0.001 salía «0.00») y su aviso
  de BUG-0085 compara con la regla, no con 100.

Queda para después: `compare_versions` y el mapa del guion siguen AVISANDO y
suprimiendo la comparación entre escalas distintas; pueden compararse con
`fue.scale.loglik_y`, que no depende del factor.

## Validation

El repro sale 0: nivel 10 000 con λ = 1, factor 1 (d.t. 122); con λ = −1,
factor 10⁶ (d.t. 1.21). `tests/test_bug_0257_0258_0259_escala.py`. La batería:
2 446 pasan.
