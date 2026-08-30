---
id: BUG-0027
title: Un-updated BFGS directions come back as covariance — total when niter=0 (a .pre, or any closed-form model), PARTIAL when the optimiser updates only some directions, and converged=True hides both
status: fixed
severity: high
component: estimation
found_in: 0.1.11
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-26
reporter: David / réplica TFM Bolivia
tags:
  - pre-contract
  - covariance
  - standard-errors
references:
  - src/art/diagnosis.py:254-262 (param_correlation lee cov_matrix)
  - src/art/interventions.py:326 (test_intervention lee cov_matrix)
  - src/art/mcp_server.py:1175 (ar_factorization lee cov_matrix)
  - src/art/describe.py:678, 2271 · src/art/full_report.py:219 (tablas de parámetros)
  - bugs/BUG-0027-repro/repro.py
---

## Summary

El invariante del `.pre` es que los parámetros **no se muevan**: *«corre `fue`
sobre un `.pre` y los números NO se mueven»*. Se cumple, y es lo correcto. Pero
tiene una consecuencia que nadie comprueba: el optimizador arranca **ya en el
óptimo**, para en `niter = 0`, y el factor BFGS de la inversa del hessiano
—inicializado como un múltiplo escalar de la identidad— **nunca llega a
actualizarse**.

Resultado: `cov_matrix = c · I`. **Todos los errores típicos valen lo mismo.**

Y el resultado se declara `converged = True` con `termcode = 1`, así que nada
avisa. No falla ruidosamente: el valor que sale es pequeño y creíble, de modo que
los estadísticos `t` salen enormes y falsos.

Medido sobre `PGAS_FINAL.pre` (AR(2) + escalón, 3 parámetros):

```
   niter     = 0        converged = True     termcode = 1
   cov_matrix = [[0.024096, 0, 0], [0, 0.024096, 0], [0, 0, 0.024096]]
   ee         = [0.15523, 0.15523, 0.15523]
```

frente a los del mismo modelo ajustado en memoria desde valores iniciales
lejanos: `[0.0631, 0.1064, 0.1078]`.

## Impact

Alta, y **sobre el fichero de contrato de la suite**. Todo lo que lea errores
típicos de un `.pre` devuelve basura con aspecto de dato:

- las **tablas de parámetros** que ART imprime — el caso se detectó viendo un
  bloque donde el alter, el coseno, el seno, los dos ω y Φ tenían *todos* la
  misma cifra entre paréntesis, `(0.1552)`;
- **`ar_factorization`**, cuyos `d ± SE` y `per ± SE` salen del método delta
  sobre esa covarianza;
- **`test_intervention`** y **`simplify_interventions`**, cuyos `t` salen de ahí.

**Se comió un resultado ya reportado.** La caracterización del AR(2) de `ln PGAS`
se dio como `d = 0,51 ± 0,15` y `periodo = 8,59 ± 4,68`, y con la covarianza
correcta es `d = 0,514 ± 0,105` y `periodo = 8,59 ± 2,09`. El error típico del
periodo estaba **inflado ×2,2**, y con él se concluyó que «la frecuencia no está
identificada, el intervalo va de 0 a 18». Con el valor correcto el intervalo al
95% es ≈[4,4 · 12,8] y **excluye** los periodos estacionales 4 y 2 — la
conclusión sustantiva era la misma pero por el motivo equivocado, y la
incertidumbre reportada era falsa.

Y no siempre muerde: `ITCER_FINAL.pre` devuelve `ee = [0.0182, 0.0194, 0.1465,
0.0031]`, correctos. La diferencia es si el optimizador llega a dar alguna
iteración desde los valores del `.pre`. Que unas veces sí y otras no es lo que
hace el defecto especialmente difícil de ver.

## Reproduction

```
python3 bugs/BUG-0027-repro/repro.py
```

Sintético y determinista (semilla 19), AR(2) sobre un paseo aleatorio, n=120:

```
(1) ajuste normal (arranca en 0):
    niter = 5   converged = True   termcode = 1
    params = [0.83548, -0.3324]
    ee     = [0.08596, 0.0858]   -> degenerada? False

(2) reestimado desde su propio .pre:
    niter = 0   converged = True   termcode = 1
    params = [0.83548, -0.3324]     <- identicos: el invariante SI se cumple
    ee     = [0.12964, 0.12964]  -> degenerada? True
    cov_matrix = [[0.016807, 0], [0, 0.016807]]
```

## Root cause

`fue` inicializa la aproximación BFGS de la inversa del hessiano como `c · I` y la
actualiza en cada iteración. Con `niter = 0` no hay ninguna actualización, así que
lo que se devuelve como covarianza **es la semilla**. `fit()` no expone opción de
hessiano por diferencias finitas, de modo que desde ART no se puede reconstruir la
covarianza sin volver a optimizar desde otro punto.

**El disparador es estrecho y hay que decirlo con precisión: la semilla EXACTAMENTE
en el óptimo.** Medido sobre tres ficheros del mismo trabajo:

| fichero | \|semilla − óptimo\|max | niter | covarianza |
|---|---|---|---|
| `PGAS_m10.pre` (escrito por `confirm_and_estimate`) | 4,07·10⁻⁵ | 3 | ok |
| `ITCER_FINAL.pre` | 5,74·10⁻⁷ | 4 | ok |
| **`PGAS_FINAL.pre`** (escrito por `_write_inp` tras ajustar en memoria) | **0** | **0** | **degenerada** |

A 5,74·10⁻⁷ del óptimo el optimizador todavía da cuatro iteraciones y construye el
hessiano. Sólo la coincidencia exacta lo mata. Por eso el defecto es intermitente y
difícil de ver: la mayoría de los `.pre` que ART escribe llevan valores redondeados
y **no** lo disparan.

**Y por debajo hay una cuestión de convenio, que es la lectura correcta del
problema.** El convenio de la suite es explícito:

> `.inp` una **especificación**; los valores son **semillas**, un punto de partida.
> `.pre` ese mismo `.inp` con las estimaciones como valores iniciales: **un óptimo**
> en forma reejecutable. Invariante comprobable: corre `fue` sobre un `.pre` y los
> números NO se mueven.

Correr `fue` sobre un `.pre` es, por diseño, **la verificación de ese invariante**,
no una estimación. Y un `.pre` **no puede llevar covarianza**: el formato guarda
valores y banderas de libertad, no la matriz. De modo que pedir errores típicos a
la reejecución de un `.pre` es pedir algo que el fichero no está en condiciones de
dar — con o sin este defecto.

**La estimación va desde el `.inp`.** El defecto es que ART no lo impone ni lo
avisa: acepta un `.pre`, lo reejecuta, y publica como errores típicos lo que en
realidad es la semilla del BFGS.

## Fix

Como la covarianza no se puede recuperar sin reoptimizar, ART **no debe fingir que
la tiene**:

- `art.diagnosis.covariance_is_degenerate(result)` — `True` cuando `niter == 0`
  **y** la covarianza es un múltiplo escalar de la identidad (diagonal constante,
  fuera de la diagonal nula). Las dos condiciones a la vez, para no marcar un
  modelo de un solo parámetro ni una covarianza casualmente diagonal.
- Los consumidores de errores típicos consultan el predicado y, si es cierto,
  **omiten los `±` y los `t` y avisan** en lugar de imprimir cifras falsas:
  `ar_factorization`, `test_intervention` y las tablas de parámetros.
- El aviso dice **qué hacer, y es la regla del convenio**: *«estos errores típicos
  no son válidos — la semilla coincide con el óptimo y el optimizador paró en
  `niter=0`. Reestima desde el `.inp` (semillas), no desde el `.pre` (óptimo): la
  reejecución de un `.pre` verifica el invariante, no estima.»*

Lo que **no** se toca: el invariante del `.pre`. Los parámetros deben seguir sin
moverse — es la propiedad que hace útil al fichero.

## Validation

`tests/test_bug_0027_degenerate_covariance_from_pre.py`: sobre el DGP del repro,
que un ajuste normal da `niter > 0` y errores típicos distintos entre sí; que
reestimar desde el `.pre` da `niter == 0`, parámetros idénticos (el invariante) y
covarianza `c·I`; que `covariance_is_degenerate` distingue los dos casos; y que
los consumidores omiten los `±` y avisan en vez de publicar la cifra falsa.


## Ampliación (2026-08-27) — el primer arreglo tenía dos agujeros

Encontrados **usando la herramienta**, al rehacer una serie con el detector ya
puesto. Los dos dejaban fuera casos frecuentes.

### Agujero 1 — se excluía `npar = 1`, que es la línea base de todo

El primer detector exigía `cov.shape[0] >= 2`, razonando que con un solo
parámetro una `c·I` es indistinguible de una covarianza legítima.

Era un error, y del peor tipo: **el modelo de media sola sin ARMA cae de lleno
ahí**, y es el `m00` con que empieza cualquier análisis. Su estimador
máximo-verosímil es la media muestral, o sea tiene **solución cerrada**: el
optimizador no tiene nada que hacer, para en `niter = 0`, y devuelve la semilla.

Medido en `ITCER_m00` (λ=0, d=1, sólo μ):

```
**** CONVERGENCE OBTAINED AFTER 0 ITERATIONS
Mean parameter (mu):   -0.720153  (0.155230)
```

Ese `0.155230` es √(2/83). El error típico muestral de la deriva era **0.30 %**,
que da t = −2.41; el falso da **t = −4.64**. Casi el doble.

**Y es una segunda causa, distinta de la del `.pre`.** Aquí no hay semilla
colocada en el óptimo: hay un modelo sin nada que optimizar. Reestimar desde el
`.inp` no lo arregla. El aviso se generalizó para decir las dos causas y qué
hacer en cada una.

### Agujero 2 — la degeneración PARCIAL, que es la peligrosa

El detector exigía diagonal constante y fuera de la diagonal nula. Pero con
`niter = 1` el BFGS actualiza **una** dirección y deja el resto intacto. Medido
sobre `RATIO_m31.pre`, 7 parámetros:

```
diag = [0.00605273, 0.02409626, 0.02409634, 0.02409638, 0.02409639, …]
             ↑ movida        ↑ las demás, todavía la semilla
```

**Cinco de siete errores típicos inservibles y dos válidos, sin nada que los
distinga en la salida.** Peor que la degeneración total, porque la total al menos
salta a la vista: todas las cifras iguales.

### La semilla es 2/n, no una constante

Lo que hace detectable la degeneración parcial. Primero se midió idéntica
(0.02409639) en dos modelos con σ² de 0.0063 y de 7.30 y se dio por constante —
**y era falso**: en un sintético de 120 observaciones vale 0.016807. La relación
es exacta:

| n residuos | semilla | 2/n |
|---|---|---|
| 83 | 0.0240964 | 2/83 |
| 119 | 0.0168067 | 2/119 |

`bfgs_seed_var(result)` la calcula, y `degenerate_variance_indices(result)`
devuelve **qué parámetros** están afectados, que es lo que permite decir «5 de
los 7» en vez de un binario.

### Y donde más falta hacía: el bloque de la ecuación

La ecuación con los parámetros y sus errores típicos debajo es **la forma en que
este sistema presenta un modelo**. Si esos errores son la semilla, presentarlos
es peor que no presentarlos: son pequeños y creíbles. `_equation_for_prompt`
emite ahora el aviso, diciendo cuántos de cuántos están afectados.
