---
id: BUG-0189
title: art lee la media por getattr(model, 'mu'), y el atributo se llama mu0: el guion registra mu=0.0 SIEMPRE, y los clones de la escalera y del barrido pierden la semilla heredada
status: fixed
severity: high
component: guion
found_in: 0.2.1
fixed_in: 0.2.2
reported: 2026-09-16
reporter: David (estudio del contrato de ficheros)
tags:
  - mu
  - guion
  - escalera
references: []
---

## Summary

`fue.Model` guarda la semilla de la media en **`mu0`** (`fue/model.py:219`:
`self.mu0 = float(mu)`). El argumento del constructor se llama `mu`; el
atributo, no. `Model.add_intervention` lo tiene en cuenta y hace
`mu=self.mu0` al clonarse (`model.py:243`).

art lo lee por el nombre del argumento en tres sitios, y en los tres
`getattr` devuelve el valor por defecto sin que nada falle:

| sitio | qué hace | consecuencia |
|---|---|---|
| `art/guion.py:1107` | `"mu": float(getattr(model, "mu", 0.0) or 0.0)` | **el spec registrado en el guion dice `mu: 0.0` siempre** |
| `art/escalera.py:257` | `"mu"` en la lista de atributos a clonar | el clon no hereda la media: reempieza en 0 |
| `art/configuracion.py:621` | `"mu"` en la misma lista | ídem en el barrido de configuraciones |

Y hay un daño de segundo orden que el propio código anticipa y no ve venir:
`guion.py:1341` es `elif spec.get("mu"):` — la rama que añade la constante a
la ecuación impresa cuando la media está FIJA. Como `spec["mu"]` vale siempre
0.0, **esa rama no se ejecuta nunca**. El comentario de `guion.py:1334-1338`
dice que se escribió precisamente para que «la presentación no mienta».

## Impact

Alto, y del tipo peor: no rompe nada, falsifica el registro.

- El guion es el registro científico del recorrido —grafo de versiones, nodos
  de decisión con razón y evidencia, integridad por sha—. Un modelo con media
  fija no nula queda anotado con `mu: 0.0` y se dibuja sin su constante. La
  ecuación publicada no es el modelo estimado.
- En `escalera.py` y `configuracion.py` el clon pierde la semilla y arranca μ
  en 0 conservando `estimate_mu=True`. El optimizador la recupera casi
  siempre, pero desde otro punto de partida: los AIC de los candidatos se
  comparan contra una base que se sembró distinto, y ese es justo el número
  que decide qué configuración gana.

## Reproduction

```python
import fue
ts, m = fue.load("RIPC.3.inp")      # corpus de conformidad

print(m.mu0)                         # -88.717979
print(hasattr(m, "mu"))              # False
print(getattr(m, "mu", 0.0))         # 0.0   <-- lo que art registra
```

En el guion, sobre cualquier modelo con media:

```python
from art.guion import _spec_de   # el que construye guion.py:1107
_spec_de(m)["mu"]                 # 0.0, con m.mu0 = -88.72
```

## Root cause

El nombre del argumento y el del atributo difieren en `fue.Model`
(`model.py:197` y `:219`). art usa el del argumento para leer y el `getattr`
con valor por defecto convierte el error de nombre en un cero plausible.
`grep -n 'getattr(.*["\']mu["\']' src/art/*.py` da hoy una sola línea
—`guion.py:1107`— porque las otras dos entran por la lista de atributos.

## Fix

Leer `mu0` y seguir pasando `mu=`:

```python
# guion.py:1107
"mu": float(getattr(model, "mu0", 0.0) or 0.0),
```

```python
# escalera.py:257 y configuracion.py:621 — fuera de la lista genérica
for a in (..., "estimate_mu", "boxlam", "refactor"):      # sin "mu"
    ...
v = getattr(model, "mu0", None)
if v is not None:
    kw["mu"] = v
```

Conviene además que `fue.Model` exponga `mu` como propiedad de sólo lectura
sobre `mu0`, para que la próxima vez el `getattr` acierte. Eso es cosa del
registro de fue.

## Validation

- Un test que cargue un `.inp` con media fija no nula y compruebe que
  `_spec_de(m)["mu"] == m.mu0`.
- Un test sobre `guion.py:1341`: que la ecuación impresa de un modelo con
  `estimate_mu=False` y `mu0 != 0` contenga la constante.
- Para los clones: que `escalera`/`configuracion` produzcan un modelo con el
  mismo `mu0` que el de partida.

## Resolución (0.2.2)

Confirmado en los tres sitios.

- `guion.py::_extract_spec` lee `mu0`. Con eso la rama `elif spec.get("mu")` de
  la ecuación (μ FIJA no nula) vuelve a ejecutarse.
- `escalera.py::_clona_con` y `configuracion.py` sacan `mu` de la lista genérica
  y pasan `mu=model.mu0`.
- Hermano encontrado al arreglarlo: `_write_inp` escribía `0` en la línea de la
  media siempre que `estimate_mu` fuera falso, así que una μ FIJA no nula
  desaparecía al releer. Ahora sale `<μ exacta> 0`.
- En fue: `Model.mu` es ahora una propiedad de sólo lectura sobre `mu0`, así que
  un `getattr(model, "mu")` futuro acierta.
- Los valores FIJOS (ARMA, ω, δ, frecuencia fija, λ, armónico) se escriben en
  `_write_inp` con la representación exacta, igual que en fue/BUG-0021; las
  semillas libres conservan `.6f`.

Validación: `tests/test_bug_0187_0189_contrato_ficheros.py`.
