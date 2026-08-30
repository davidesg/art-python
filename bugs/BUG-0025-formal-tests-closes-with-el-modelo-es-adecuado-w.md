---
id: BUG-0025
title: formal_tests closes with "el modelo es adecuado" without ever looking at the model's diagnosis — it runs the MEG and the DCDs on a model whose Q-test, normality or outliers are failing, and says nothing
status: fixed
severity: high
component: formal-tests
found_in: 0.1.11
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-26
reporter: David / réplica TFM Bolivia
tags:
  - diagnosis
  - meg
  - sequencing
references:
  - src/art/describe.py:1502 (describe_formal_tests)
  - src/art/describe.py:1778 (el cierre «El modelo es adecuado»)
  - src/art/diagnosis.py:315 (diagnose — la información estaba disponible y no se consultaba)
  - src/art/mcp_server.py:149,1742,1983 (las tres veces que la capa guiada dice que esto va AL FINAL)
  - bugs/BUG-0010-… (el mismo principio: «una frecuencia sin contrastar no puede terminar en el modelo es adecuado»)
  - bugs/BUG-0025-repro/repro.py
---

## Summary

Los contrastes formales —MEG, Shin-Fuller, los DCD— son la **última** etapa del
ciclo Box-Jenkins-Treadway. Presuponen un modelo escueto, adecuado y con la
diagnosis limpia, porque **sus distribuciones nulas se derivan bajo residuos que
son ruido blanco**. Correrlos sobre un modelo cuya Q, cuya normalidad o cuyos
anómalos están fallando no es una imprecisión: es preguntar por la frontera de
un parámetro a una verosimilitud que todavía no describe los datos.

La capa guiada de ART lo dice tres veces:

| dónde | qué dice |
|---|---|
| `mcp_server.py:149` | «Hipótesis B1 es revisable **al final** mediante MEG» |
| `mcp_server.py:1983` | «El contraste MEG (`formal_tests`) evalúa **al final**…» |
| `mcp_server.py:1742` | «**B) Contrastes formales** (**si los residuos están limpios**)» |

Pero esa condición es **prosa**. `describe_formal_tests` no la comprueba en
ningún momento: construye su lista `issues` sólo con hallazgos de los propios
contrastes formales y, si sale vacía, imprime

> «Los contrastes formales no detectan problemas. **El modelo es adecuado.**»

La primera frase es correcta y está en su ámbito. La segunda es una afirmación
sobre el **modelo** que esta función no está en condiciones de hacer, y que se
emite sin haber mirado la diagnosis ni una vez.

## Impact

Alta, y del tipo que no deja rastro: no falla nada, sale un veredicto plausible,
y el veredicto es sobre **el orden de integración y la naturaleza de la
estacionalidad** — las dos decisiones de las que cuelga el resto del modelo.

Peor aún, es un defecto que **rompe la secuencia del método**. Un analista (o un
asistente) que llame a `formal_tests` en mitad de la construcción recibe
veredictos con aspecto de definitivos, actúa sobre ellos —reformula la
estacionalidad, cambia `d`— y el ciclo queda descabalgado sin que nada lo avise.
Es exactamente lo que ocurrió al encontrarlo: se corrió el MEG sobre el `m00` de
`ln RATIO`, un modelo de armónicos sin ARMA con **Q fallando en los retardos 2,
4, 8 y 12**, se aceptaron sus veredictos de estacionalidad estocástica y se
reformuló el modelo sobre esa base. ART tenía la puerta puesta en la capa
guiada, pero al no estar comprobada en el motor no la cerró.

Y la medida final, sobre el modelo ya reformulado `RATIO_log_m02`:

```
JB = 42.801  (p = 0.0000)      1 residuo extremo, obs 62, z = +4.14
formal_tests →  "Los contrastes formales no detectan problemas.
                 El modelo es adecuado."
```

El precedente está en el mismo fichero, unas líneas más abajo, en el comentario
de BUG-0010: *«una frecuencia sin contrastar no puede terminar en "el modelo es
adecuado"»*. Una diagnosis que falla tampoco.

## Reproduction

```
python3 bugs/BUG-0025-repro/repro.py
```

Sintético y determinista (semilla 12). Paseo aleatorio limpio con **un** anómalo
enorme en la innovación: el modelo correcto es ARIMA(0,1,0) y el caso de libro
es «intervén antes de seguir».

```
DIAGNOSIS del modelo:
  Q  (p-valor minimo) : 0.0163    FALLA
  JB (normalidad)     : 2186.903  p=0.000000  FALLA
  residuos |z|>3      : 1  ['obs 60 z=+7.15']

formal_tests CONCLUYE (antes del arreglo):
   Los contrastes formales no detectan problemas. El modelo es adecuado.
```

## Root cause

`describe_formal_tests` (describe.py:1502) recibe el modelo ajustado y lanza
`shin_fuller`, `dcd`, `dcd_overdiff_regular`, `dcd_f`, `rv` y `meg`. Nunca llama
a `diagnose(model)`, pese a que `art.diagnosis.diagnose` existe, está importado
en el mismo módulo (`describe.py:34`) y devuelve exactamente lo que hace falta:
`q_pvalues`, `jb_pvalue` y `extreme`.

`issues` se llena sólo con hallazgos de los contrastes formales, y `rec`
(describe.py:1778) es un `if issues: … else: "El modelo es adecuado."`. Con la
diagnosis fuera del cómputo, el `else` es alcanzable con cualquier modelo, por
malo que sea.

## Fix

`describe.py`, en `describe_formal_tests`:

1. Al entrar, medir la diagnosis con `diagnose(model)` y recoger los fallos:
   Q (p mínimo ≤ 0.05), normalidad (JB p ≤ 0.05) y residuos extremos.
2. Si hay fallos, un aviso **al principio del informe**, antes de cualquier
   estadístico —porque lo que está en cuestión es si esos números se pueden
   leer—: dice qué falla, recuerda que las nulas suponen ruido blanco, y marca
   lo que sigue como informativo y no concluyente.
3. Ese mismo diagnóstico entra como **primer** elemento de `issues`, de modo que
   el cierre no puede ser «el modelo es adecuado» mientras la diagnosis falle.
4. `data` expone `diagnosis_ok` y `diagnosis_failures`, para quien lea la
   estructura en vez del texto.

No se bloquea la ejecución: correr los contrastes sobre un modelo inadecuado
sigue siendo legítimo como exploración —y `dcd_overdiff_regular` pide
explícitamente la línea base determinista, que no es un modelo final—. Lo que
deja de ser posible es **leer el resultado como un veredicto** sin que nadie
avise.

## Validation

`tests/test_bug_0025_formal_tests_checks_diagnosis.py`: sobre el DGP del repro,
que la diagnosis efectivamente falla (o sea que el caso es el que muerde), que
el informe lleva el aviso arriba, que la recomendación **no** contiene «El
modelo es adecuado» y sí el motivo, y que `data["diagnosis_ok"]` es `False` con
los fallos enumerados. Control con un modelo limpio: el aviso no aparece,
`diagnosis_ok` es `True` y el cierre «el modelo es adecuado» se conserva.
