---
id: BUG-0065
title: la nula de Shin-Fuller no era la de Shin-Fuller — imponía ρₘ en cada factor y anulaba el resto, así que el mismo modelo daba Φ̂₁ᵤ = 25.746 o 7.632 según cómo se escribiera el AR, y un paseo aleatorio salía «estacionario»
status: fixed
severity: critical
component: formal-tests
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-31
reporter: David — conjetura sobre el PGAS del RUN 4, verificada
tags:
  - shin-fuller
  - integration-order
  - invariance
references:
  - src/art/formal_tests.py (shin_fuller, ShinFullerResult.stationary)
  - src/art/describe.py (presentación del veredicto)
  - tests/test_bug_0065_shin_fuller_una_raiz.py
  - bugs/BUG-0065-repro/repro.py
---

## Summary

Shin-Fuller contrasta **una** raíz en ρₘ = 1 − 4/n **con el resto de la
estructura AR libre** — es la forma aumentada de Dickey-Fuller. El código hacía
otra cosa: recorría **todos** los factores poniendo el primer coeficiente de cada
uno en ρₘ y los demás en cero.

Dos defectos, y son separables.

### (a) El contraste no era invariante a la parametrización

El mismo modelo ajustado, con **idéntica verosimilitud** (logL = −291.073):

| escritura del AR | nula impuesta | Φ̂₁ᵤ | veredicto |
|---|---|---|---|
| `(1 − 1.6390B + 0.6668B²)` | `[ρₘ, 0]` | **25.746** | estacionario |
| `(1 − 0.8890B)(1 − 0.7500B)` | `[ρₘ][ρₘ]` | **7.632** | estacionario |
| **correcta** | ρₘ en la dominante, **resto libre** | **0.298** | **raíz unitaria → d+1** |

La segunda impone **dos** raíces casi unitarias, que no es H₀. Un contraste cuyo
veredicto depende de cómo se teclee un operador no es un contraste.

### (b) Al anular el resto, medía otra cosa

Con la estructura restante en cero, Φ̂₁ᵤ deja de responder «¿la raíz dominante es
1?» y pasa a responder «¿el AR completo ajusta mejor que un AR(1) en ρₘ?». Con
una raíz cerca de 1 y otra claramente estacionaria, **la segunda infla el
estadístico y tapa a la primera**.

### (c) Y no tenía dirección

Φ̂₁ᵤ = L_libre − L_restringido crece cuando ρ̂ se aleja de ρₘ **en los dos
sentidos**, y se leía como si sólo creciera hacia la estacionariedad. Un **paseo
aleatorio puro** —ρ̂ = 0.9973 contra una nula de 0.98, o sea *más* integrado que
H₀— daba Φ̂₁ᵤ = 4.883 y se declaraba «Estacionario ✓».

## Cómo se encontró

Conjetura del analista humano sobre el PGAS del RUN 4, donde un carril se quedó
en **d=0** con un modelo cuya Q fallaba en cuatro retardos, apoyándose en el
veredicto «Estacionario ✓» de este contraste:

> *«Si en el PGAS de DS hubiera convergido si existieran dos cosas. Primero al
> llegar al modelo factorizar el AR(2) en dos AR(1) y luego SF, eso le hubiera
> puesto en d=1.»*

Verificada: el AR(2) factoriza en φ = 0.88898 y 0.75003, la dominante está a
t = −0.83 de la raíz unitaria (SE 0.1334) y no se puede rechazar. Con la nula
correcta el contraste da 0.298 y pide d=1 — que es donde los otros carriles
encontraron modelos adecuados (AIC 584.56 y 569.25, frente a 592.15 inadecuado).

La conjetura era correcta y además destapó por qué: **factorizar el modelo no
factorizaba el contraste**.

## Lo que dice el paper, y confirma la conjetura

**Shin & Fuller (1998), §2, ecuaciones (2.2)-(2.3) y la identidad de la p. 592:**

> *«We isolate the possible autoregressive unit root by **reparameterizing (2.1)
> into the two equations**: yₜ = ρyₜ₋₁ + zₜ ; zₜ = α₁zₜ₋₁ + … + αₚzₜ₋ₚ + eₜ − …,
> where {zₜ} is an unobserved **stationary** ARMA(p,q) […] related to the original
> parameter π through the identity*
> **(m^{p+1} − φ₁m^p − … − φ_{p+1}) = (m − ρ)·A(m)**.»

Es literalmente «factorizar AR(1)·AR(p) y contrastar sobre el AR(1)». No es una
aproximación conveniente: es la parametrización del contraste.

Y la **ecuación (3.5)** define el estadístico:

```
Φ̂₁ᵤ = L_μ(μ̂, ψ̂, σ̂ | Y) − L_μ(μ̂₀, θ̂₀, ρₘ, σ̂₀ | Y)   si ρ̂_μ ≤ 1 − 4/n
     = 0                                              si ρ̂_μ > 1 − 4/n
```

Dos cosas que el código no hacía. Primera: bajo la nula **sólo ρ está fijado** —
μ̂₀, θ̂₀ y σ̂₀ llevan sombrero, se reestiman. Una restricción, `df = 1`. Segunda:
el estadístico **es cero por definición** cuando ρ̂ queda por encima de ρₘ.

## Raíces complejas: el contraste no existe, y forzarlo corrompe

La reparametrización exige **ρ ∈ (−1, 1] REAL**. Un par conjugado no se puede
escribir como (m − ρ)·A(m) con ρ real, así que sobre un factor sin raíz real
**Shin-Fuller no aplica**.

Y forzarlo no es un error benigno. Deflactar por una raíz compleja da
coeficientes complejos, y `float()` **descarta la parte imaginaria en silencio**:

```
AR(2) de PGAS_m20, raíces 1.4483 ± 1.3001i
   resto = [1+0j, −0.38235 − 0.34323j]
   float(−c) → 0.38235          ← un factor que NO es el del modelo
```

Un resultado equivocado sin aviso, que es peor que una excepción. El caso real
está en el propio benchmark de esta réplica: el `PGAS_m20` del modo guiado es un
AR(2) con pseudociclo de 8,6 trimestres, y su orden de integración **no puede
cerrarse por este contraste** — hay que leerlo por el par del DCD, o por el
MEG/DCD_f si la sospecha es de no estacionariedad en ω≠0.

## Fix

* La nula impone la raíz **una vez**, sobre el factor cuya raíz está más cerca
  del círculo unidad, y **deja libre el resto**. `df = 1`.
* Cuando ese factor tiene orden ≥ 2 —donde una raíz no es un coeficiente sino una
  función no lineal de todos— el factor **se parte para el contraste**:
  `(1 − ρₘB)` por un factor libre de orden p−1, sembrado con la factorización del
  original. Es exactamente «factorizar y luego contrastar», y es lo que hace la
  nula expresable.
* La raíz que se aísla es la **REAL** más cercana al círculo unidad. Si no hay
  ninguna real, el contraste **se declara no aplicable** con su razón, en vez de
  deflactar por una compleja y perder la parte imaginaria en silencio.
* `Φ̂₁ᵤ = 0` cuando ρ̂ > ρₘ, que es la ecuación (3.5) al pie de la letra. Por
  encima de la nula los datos son al menos tan integrados como H₀, y la distancia
  en esa dirección no es evidencia de estacionariedad.
* La salida dice en qué dirección está la raíz dominante, para que un Φ̂₁ᵤ grande
  no se lea como rechazo cuando no lo es.

## Verificación

| caso | φ̂ dominante | ρₘ | Φ̂₁ᵤ | veredicto |
|---|---|---|---|---|
| paseo aleatorio puro | 0.9973 | 0.98 | 4.883 | **raíz unitaria → d+1** |
| AR(1) con φ=0.35 | 0.3337 | 0.98 | 39.584 | estacionario ✓ |
| PGAS `m14` (d=0) | 0.8890 | 0.9524 | 0.298 | **raíz unitaria → d+1** |
| PGAS `m20` (d=1) | 0.5138 | 0.9524 | 10.919 | estacionario ✓ |
| ITCER `m20` (d=1) | 0.2077 | 0.9524 | 19.006 | estacionario ✓ |

Los dos primeros eran veredictos equivocados; los tres últimos no cambian.

Y sobre `PGAS_m14` los **dos lados del par confirmatorio pasan a coincidir** en
d+1, donde antes discrepaban con el testigo MA fuera del eje f=0.

## Por qué es crítico

Es el contraste que cierra el orden de integración, o sea el nodo del que
dependen todos los demás. Un veredicto equivocado ahí no se corrige aguas abajo:
se hereda. **Bloquea la publicación de 0.1.12 hasta que el RUN 4 se revalide.**
