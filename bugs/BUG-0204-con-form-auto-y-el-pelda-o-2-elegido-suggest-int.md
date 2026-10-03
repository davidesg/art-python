---
id: BUG-0204
title: Con form=auto y el peldaño 2 elegido, suggest_intervention_form construye un escalón de UN ω — n_omega=0 se convierte en 1 antes de leerse como «pedido» y pisa los escalones de la configuración
status: open
severity: high
component: interventions
found_in: 0.2.3.dev0
fixed_in: 
reported: 2026-10-03
reporter: David / Claude — carril autónomo de WTI para los fixtures de drtran
tags:
  - escalera
  - suggest_intervention_form
  - silencioso
references:
  - src/art/mcp_server.py ≈8821-8822, suggest_intervention_form — n_omega y _n_omega_pedido
  - src/art/mcp_server.py ≈8931, «if _n_omega_pedido: n_omega = _n_omega_pedido»
  - BUG-0079 (n_omega explícito manda), BUG-0156 y BUG-0201 (el peldaño juzgado es el construido)
---

## Summary

`suggest_intervention_form(form="auto")` corre la escalera de Ockham, y cuando
ésta elige el peldaño 2 —la configuración del mecanismo, N escalones desde su
arranque— la herramienta construye **un escalón de UN solo ω** en ese arranque.
El modelo estimado no es ninguno de los tres peldaños: ni el elegido (N ω), ni
el escalar en la fecha del suceso. La salida anuncia «◀ elegido» sobre el
peldaño 2 y debajo imprime la ecuación de otro modelo, sin aviso.

Sobre WTI, en la caída de 12/2014 (OPEP), la escalera dice:

    - `2` la configuración del mecanismo — 3 escalones en el nivel · AIC 1482.95 · ω(1)=-58.0750 · se sostiene ◀ elegido

y el modelo construido es:

    − 10.761 ξₜ^{S,11/2014}      AIC = 1497.90

Un ω en 11/2014, 15 puntos de AIC peor que el peldaño elegido; los residuos
siguen mostrando 12/2014 y 01/2015 como extremos (z −3.27 y −3.04).

## Impact

Alto, y silencioso. Cada vez que la escalera sube al peldaño 2 —que es
justamente cuando el suceso dura más de un período— el modelo que sale no es el
que se razonó. El carril autónomo lo encadena sin enterarse; en guiado, el
analista sólo lo ve si compara el número de ω de la ecuación con la línea de la
escalera. Viola el principio de BUG-0156 y BUG-0201: el peldaño que se juzga es
el que se construye.

Afecta desde 0.2.0 (`9cc69fe`), cuando se introdujo `_n_omega_pedido`.

## Reproduction

Script autocontenido; sólo necesita el CSV del pass-through
(`levels_2002_2019.csv`, columna WTI):

```python
import os, tempfile, warnings
warnings.simplefilter("ignore")
import fue
import art.mcp_server as A

CSV = ("/home/david/Dropbox/Nivel de Precios y Energia/passthrough_multiart"
       "/data/levels_2002_2019.csv")
d = tempfile.mkdtemp()
f = lambda n: os.path.join(d, n)
fn = lambda t: getattr(t, "fn", t)
txt = lambda out: "\n".join(x if isinstance(x, str) else getattr(x, "text", "")
                            for x in out)

fn(A.load_data)(CSV, f("WTI.inp"), column="WTI", series_name="WTI",
                freq=12, start_year=2002, start_period=2)
fn(A.confirm_and_estimate)(f("WTI.inp"), f("m00.inp"), lam=0, d=1, D=0, p=0,
                           q=0, n_harmonics=0, seasonal=False)
fn(A.suggest_intervention_form)(f("m00.pre"), f("m01.inp"), date="10/2008",
                                form="step", n_omega=3)
out = txt(fn(A.suggest_intervention_form)(f("m01.pre"), f("m02.inp"),
                                          date="12/2014", form="auto"))
print([l for l in out.splitlines() if l.startswith("- `2`")][0])
_, m = fue.load(f("m02.pre")); m.fit()
built = [(i.at, len(i.omega)) for i in m.interventions if i.type == "step"][-1]
print("built: step at obs", built[0] + 1, "with", built[1], "omega(s);",
      "AIC", round(m.aic, 2))
```

Salida (art 0.2.3.dev0, f22e2fc… 7c9c194):

    - `2` la configuración del mecanismo — 3 escalones en el nivel · AIC 1482.95 · ω(1)=-58.0750 · se sostiene **◀ elegido**
    built: step at obs 154 with 1 omega(s); AIC 1497.9

Esperado: 3 ω en obs 154 y AIC 1482.95.

## Root cause

`src/art/mcp_server.py`, `suggest_intervention_form`:

```python
n_omega = max(1, int(n_omega)) if n_omega else 1        # ≈8821
_n_omega_pedido = int(n_omega) if n_omega else 0         # ≈8822
...
if rec == "2": form, n_omega = "step", n_esc; at_0 = at_esc
...
if _n_omega_pedido:                                      # ≈8931
    n_omega = _n_omega_pedido
```

La primera línea normaliza `n_omega=0` (el defecto, «no pedido») a 1, y la
segunda lee el valor YA normalizado: `_n_omega_pedido` vale siempre ≥ 1, así
que la cláusula de BUG-0079 —«lo que el analista pide explícitamente manda»—
se dispara siempre y devuelve `n_omega` a 1 después de que la escalera lo puso
en `n_esc`. La fecha sí se mueve a `at_esc`, de ahí el escalón de un ω en el
arranque del mecanismo.

Los peldaños 1a/1b no se ven afectados (son de un ω de todos modos); sólo el 2.
Ningún test cubría la construcción del peldaño 2 por `form="auto"`: los de
BUG-0156 comprueban el orden del código fuente, y los de BUG-0201 el peldaño 1a.

## Fix

Leer el pedido ANTES de normalizar:

```python
_n_omega_pedido = int(n_omega) if n_omega else 0
n_omega = max(1, int(n_omega)) if n_omega else 1
```

y un test de extremo a extremo: con `form="auto"` y peldaño 2 elegido, el
modelo construido lleva `n_esc` ω en `at_esc` y su AIC es el del peldaño.

## Validation

El script de arriba: «built: … with 3 omega(s); AIC 1482.95». Y que
`n_omega=3` explícito con `form="auto"` siga mandando (BUG-0079).
