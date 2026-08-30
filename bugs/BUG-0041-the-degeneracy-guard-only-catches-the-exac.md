---
id: BUG-0041
title: the covariance-degeneracy guard only catches the EXACT BFGS seed, so a direction the optimiser barely moved publishes a standard error half its true size with no warning
status: fixed
severity: medium
component: diagnosis
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-28
reporter: David / réplica TFM Bolivia — hallado por el experimento del chat limpio
tags:
  - standard-errors
  - bfgs
  - incomplete-fix
references:
  - src/art/diagnosis.py (near_seed_variance_indices, near_seed_distances)
  - src/art/mcp_server.py (_equation_for_prompt — el aviso)
  - bugs/BUG-0027-re-estimating-a-model-from-its-own-pre-returns-a.md
  - bugs/BUG-0041-repro/repro.py
  - tests/test_bug_0041_near_seed_variances.py
---

## Summary

BUG-0027 detecta los errores típicos que provienen de la semilla del BFGS (c·I,
con c = 2/n) en vez del hessiano. Su comparación:

```python
return [i for i in range(len(d)) if abs(d[i] - semilla) <= 1e-5 * semilla]
```

Es igualdad. Caza la dirección que el optimizador **no tocó nunca** (`niter=0`)
y nada más. Una dirección que se movió un 7% tampoco lleva información del
hessiano, y no disparaba ningún aviso.

## El testigo

ITCER de la réplica, modelo de dos parámetros (una intervención y μ), `niter=2`:

| | var(μ) | SE(μ) | σ_a/√n |
|---|---|---|---|
| m00, `niter=0` | 0.024096 = **semilla exacta** | 0.1552 | 0.2966 |
| m01, `niter=2` | **0.022473** = 93% de la semilla | **0.1499** | 0.2864 |
| m02, `niter=5` | 0.072188 | 0.2687 | 0.2671 ✓ |

En m02 el error típico coincide con σ_a/√n, que es la respuesta cerrada para un
modelo sin ARMA. **En m01 vale la mitad de lo que debe, y no hay aviso.** Y μ era
justo el parámetro en disputa en ese nodo.

## Cómo se encontró

Lo señaló el experimento del chat limpio — por un motivo equivocado. Comparó el
error típico del **parámetro** μ con el `Standard error of mean` del `.out`, que
está dentro del bloque «Unconditional residuals» y es σ_a/√n: otra cosa. La
lectura era incorrecta y la sospecha buena.

(La confusión de nombres es en sí misma una trampa de presentación: un `.out` que
llama «Mean parameter (mu)» a uno y «Standard error of mean» al otro invita a
compararlos.)

## Fix

Una segunda guarda, **más débil a propósito**:

```python
BANDA_CASI_SEMILLA = 0.25

def near_seed_variance_indices(result, tol=BANDA_CASI_SEMILLA):
    ...  # dentro de `tol` relativo de la semilla, EXCLUYENDO las exactas
```

y un aviso que nombra el parámetro con su distancia:

```
ℹ Errores típicos sospechosos (niter=2): μ (-6.7%) están MUY CERCA de la semilla
  del BFGS (2/n), lo que sugiere direcciones que el optimizador apenas movió…
```

**Es sospecha y no veredicto, y eso es deliberado.** Una varianza puede valer 2/n
legítimamente; marcarla como inválida sería un falso positivo caro. Lo que se
publica es la distancia relativa, para que quien lea decida — y el aviso nombra
las dos comprobaciones disponibles: el `.out`, y σ_a/√n para una media sin ARMA.

Las degeneraciones exactas se excluyen de esta lista: ya tienen el veredicto
fuerte de BUG-0027, y avisar del mismo parámetro dos veces con fuerzas distintas
sería peor que no avisar.
