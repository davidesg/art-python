---
id: BUG-0090
title: `_load_fitted` estima un `.pre` sin avisar — y un `except: pass` se tragaba la guarda que SÍ lo detectaba, con lo que `test_interventions` respondía «no hay intervenciones» teniendo una delante
status: fixed
severity: high
component: pipeline
found_in: 0.1.12
fixed_in: 0.1.12
reported: 2026-09-05
reporter: David / Claude — estudio del contrato de ficheros
tags: [contrato, semillas, covarianza, arquitectura]
references:
  - docs/ESTUDIO-contrato-de-ficheros-y-semillas.md §2 y §4-V1
  - src/art/pipeline.py:86 (_load_fitted)
  - src/art/diagnosis.py:216 (AVISO_COV_CASI_SEMILLA)
  - BUG-0027 (la covarianza que se queda en la semilla)
---

## Summary

El convenio es `.inp(t−1) → .pre(t−1) → .inp(t) → .pre(t)`: **sólo el `.inp` se
usa para estimar**; el `.pre` sirve para modificar y crear el `.inp` siguiente.

`_load_fitted` acepta los dos y ajusta lo que le den. Su docstring lo dice:

```python
def _load_fitted(path: str):
    """Load and fit a model from .pre or .inp file."""
```

Reestimar desde un `.pre` arranca **en el óptimo**, así que BFGS no itera y la
covarianza se queda en la semilla (2/n). Los valores salen bien —la
verosimilitud coincide a seis decimales— y **las desviaciones típicas no**.

## Impact

**17 herramientas** ajustan lo que se les dé; **14 acaban consumiendo la
covarianza**: `ar_factorization`, `compare_versions`, `confirm_and_estimate`,
`formal_tests`, `full_report`, `guided_identification`, `meg_frequency`,
`meg_reformulate`, `model_histogram`, `overparameterization_analysis`,
`seasonal_param_analysis`, `suggest_intervention_form`, `test_interventions`,
`test_seasonal_simplification`.

Medido sobre `FOOD_UEM_m05_ep17b`, los mismos 15 parámetros:

| | SE `.inp` | SE `.pre` | pre/inp |
|---|---|---|---|
| ω₀ | 0.049755 | 0.096436 | **1.938** |
| ω₁ | 0.022767 | 0.079061 | **3.473** |
| μ | 0.215293 | 0.108990 | **0.506** |

**En las dos direcciones**, entre 0.46× y 3.47×. No se puede firmar el sesgo,
así que no hay corrección ni forma de detectarlo mirando la salida.

Sobre `test_interventions`, cuya salida es toda razones t y un Wald:

```
FOOD_UEM_m06_flt17.inp   ω[0]=+0.5700  SE=0.1096  t=+5.200   Wald p=0.2679
FOOD_UEM_m06_flt17.pre   ω[0]=+0.5700  SE=0.0978  t=+5.825   Wald p=0.2600
```

Y el `.pre` está al lado del `.inp`, mismo nombre, tres letras de diferencia.

## Root cause

La covarianza **no es una propiedad del óptimo**: es un subproducto del CAMINO
del optimizador, que BFGS acumula iteración a iteración. Arrancar en el óptimo
no acumula nada. Por eso un fichero que guarda sólo el óptimo **no puede** llevar
la curvatura, y el `.pre` parece hacer round-trip aunque no lo haga: mismos
valores, misma ℓ, misma ecuación, otras SE.

El contrato es correcto; lo que falla es que **nada lo hace cumplir**. Una ruta
es un `str` y la distinción vive en tres letras que ningún tipo mira.

## Fix (propuesto)

Guarda en `_load_fitted`: si la extensión es `.pre`, avisar **y decir si afecta a
la tarea**. Para residuos, figuras y diagnosis no —dependen de los valores, que
son exactos—; para cualquier tabla de parámetros sí.

Que el aviso traiga su propia respuesta no es cosmética: sin ella el LLM gasta
tokens averiguando si el aviso le concierne, que es el coste que motivó el
estudio.

Después, la separación de contratos (§6-B del estudio): `estimar(inp)` que exige
`.inp` y promete SE, frente a `mirar(inp|pre)` que acepta ambos y no las promete.

## Validation

Un repro que compruebe (a) que `_load_fitted` sobre un `.pre` avisa, (b) que
sobre un `.inp` no, y (c) que el aviso dice para qué sí y para qué no. Y una
prueba de que las SE de las dos vías difieren, para que el defecto quede fijado.

---

## Lo que apareció al escribir el repro, y es peor que el reporte

El repro sintético destapó un segundo defecto, encadenado con el primero y **más
grave**: `test_intervention` **ya detectaba** la covarianza degenerada y levantaba
un `ValueError` cuyo mensaje nombra esta situación exacta —

> *«…provienen de la semilla del BFGS (c·I), no del hessiano … (a) la estimación
> arrancó ya en el óptimo, que es lo que un `.pre` es por diseño — reestima desde
> el `.inp`…»*

— y `simplify_interventions` lo capturaba tres líneas más allá con un
`except Exception: pass`.

Consecuencia medida: sobre un modelo estimado desde un `.pre`,
`test_interventions` respondía

    *No hay intervenciones no-estructurales en el modelo.*

teniendo una delante. **art sabía exactamente lo que pasaba, lo dijo bien, y lo
tiró a la basura.** Es la lección que ya había aparecido en esta sesión con otro
`except` mudo: *una guarda que calla convierte un fallo en una ausencia, y una
ausencia se lee como «no hay nada que ver»*.

## Fix (aplicado, 2026-09-05)

**1. El sello del origen.** `_load_fitted` marca el modelo con `_art_origen`
(`"inp"` o `"pre"`) y emite un `RuntimeWarning` para el canal de API/pruebas. El
sello va en el OBJETO y no en una global porque una global mutable ya se demostró
el canal equivocado para esto mismo (BUG-0081).

**2. El aviso va donde se IMPRIME una SE, no donde se carga el fichero.** Ésa es
la pieza que hace que responda su propia pregunta: si estás viendo un error
típico, te afecta. Son cuatro sitios, y cubren las 14 herramientas por
construcción:

- `mcp_server._equation_for_prompt` — el embudo de seis herramientas;
- `mcp_server.test_interventions` — su salida es entera razones t y un Wald;
- `describe.describe_seasonal_params`;
- `full_report._section_model`.

El texto dice **a qué afecta y a qué no**: los valores son exactos y por eso
residuos, figuras y diagnosis no están tocados; lo que está tocado es todo lo que
lleve un error típico. Sin eso, el LLM gasta tokens averiguando si el aviso le
concierne — que es el coste que motivó el estudio.

**3. `simplify_interventions` deja de tragarse el motivo.** Parámetro opcional
`fallos: list | None` que recoge `(índice, tipo, motivo)`. Y `test_interventions`
distingue las dos cosas que antes confundía:

- **«no hay»** — ninguna intervención no estructural;
- **«no se pudo»** — las hay y el contraste no es posible, con el motivo.

**4. Complementa, no duplica.** La maquinaria de BUG-0027/0041 detecta el
SÍNTOMA (que la covarianza se parece a la semilla), y es una heurística: sobre
FOOD_UEM m06 no salta, porque las SE sólo se mueven un 12%. El sello detecta la
CAUSA, y es exacto. Los dos hacen falta.

## Validation — resultado

`bugs/BUG-0090-repro/repro.py` — sintético y autónomo, construye su propia serie
en vez de depender del corpus. Sale 0 y mide el defecto de fondo:

```
ℓ desde .inp = -745.616180
ℓ desde .pre = -745.616180   ← el invariante SE CUMPLE
peor desviación de las SE: 99.7%   ← y la curvatura NO
```

Comprueba además que el aviso dice que los valores son exactos, que las figuras
no están afectadas, que las razones t sí, y dónde están las buenas.

`tests/test_bug_0090_estimar_desde_pre.py`, 18 pruebas, incluidas las tres del
hallazgo del repro: que ya no se dice «no hay intervenciones» cuando las hay, que
los fallos se recogen con su motivo, y que `fallos` es opcional (los cinco
llamantes existentes no lo pasan).
