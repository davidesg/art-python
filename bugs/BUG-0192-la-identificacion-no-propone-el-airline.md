---
id: BUG-0192
title: La identificación no propone el airline sobre la serie G de Box-Jenkins — la plantilla teórica del MA lleva el signo fijado en (1 + θB)(1 + ΘBˢ), así que cada MA que se añade AUMENTA la distancia a una FAS con barras negativas
status: fixed
severity: high
component: identification
found_in: 0.2.3.dev0
fixed_in: 0.2.3.dev0
reported: 2026-09-28
reporter: David — análisis guiado de la serie de pasajeros aéreos (preparación de la P03 de Econometría Aplicada)
tags:
  - identification
  - suggest_orders
  - seasonal
  - airline
references:
  - src/art/model_detection.py::_theoretical_acf_pacf
  - src/art/model_detection.py::_pattern_similarity
  - Box, Jenkins (1970), serie G; modelo (0,1,1)×(0,1,1)₁₂
---

## Summary

Sobre ∇∇₁₂ ln de la serie G de Box-Jenkins —el caso canónico del modelo de las
líneas aéreas— `guided_identification` (Call 4, `lam=0, d=1, D=1`) propone en
primer lugar (0,1,1)(0,1,0)₁₂ y (0,1,0)(0,1,1)₁₂, empatados (0,736 y 0,729), y deja
el airline (0,1,1)(0,1,1)₁₂ en **cuarto** lugar (0,710). La FAS empírica tiene
exactamente las dos barras del airline: r₁ = −0,341 y r₁₂ = −0,387, con la FAP
decayendo en 1 y en 12. Estimados los tres, el airline es el único adecuado:

| Modelo | σ̂ₐ | BIC | Q(39) |
|---|---:|---:|---|
| (0,1,1)(0,1,1)₁₂ — airline, 4.º de la lista | 3,64 % | 726,9 | 37,7 (p = 0,44) ✓ |
| (0,1,1)(0,1,0)₁₂ — 1.º de la lista | 4,27 % | 757,5 | 68,0 (p = 0,002) ✗, falla en 12, 24, 36 |
| (0,1,0)(0,1,1)₁₂ — 2.º de la lista | 3,89 % | 739,9 | 64,5 (p = 0,005) ✗, falla en 1 |

La herramienta lo marca además como «decisión ambigua» entre los dos primeros,
lo que empuja al analista a comparar dos modelos incompletos.

## Impact

Alto. Es la identificación de la serie estacional más conocida de la literatura
y el ejemplo con el que se enseña la ruta B2. Un alumno que siga la lista estima
un modelo que deja memoria en 12, 24 y 36 (o en 1) y tiene que reformular para
llegar a donde la FAS ya apuntaba. Y no es exclusivo del airline: **cualquier
serie con MA de coeficiente positivo en el convenio de la escuela (barras
negativas en la FAS) sale penalizada por cada MA que se le añade**, regular o
estacional.

## Reproduction

```python
import art
from art.mcp_server import _load_ts_model
import art.model_detection as md

ts, _ = _load_ts_model(".../03-datos/ejemplos/AIRLINE/AIRLINE.inp")   # serie G, 1949-1960
for sp in art.suggest_orders(ts, d=1, D=1, lam=0.0, top_n=6):
    print(sp.p, sp.q, sp.P, sp.Q, round(sp.similarity, 3))
# 0 1 0 0 0.736    <- (0,1,1)(0,1,0)
# 0 0 0 1 0.729    <- (0,1,0)(0,1,1)
# 1 0 0 0 0.715
# 0 1 0 1 0.710    <- el airline, cuarto

a, _ = md._theoretical_acf_pacf(0, 1, 0, 1, 12, 39)
print(a[0], a[11])        # +0.275 +0.275   (empírico: −0.341 −0.387)
```

La serie es la G de Box-Jenkins (`bjg.gdt` de gretl, variable `g`), exportada a
`airline.csv`; el `.inp` lo escribe `load_data(freq=12, start_year=1949)`.

## Root cause

`_theoretical_acf_pacf` construye la plantilla del MA con signo **más** y
coeficientes positivos fijos:

```python
ma_reg  = np.r_[1.0, theta]            # (1 + θ₁B + …),  θ₁ = 0.3
ma_seas[(i + 1) * s] = v               # (1 + Θ₁Bˢ + …), Θ₁ = 0.3
```

La plantilla del (0,1,1)(0,1,1)₁₂ tiene por tanto ρ₁ = ρ₁₂ = **+0,275**, y la FAS
empírica −0,341 y −0,387: el error en cada uno de esos dos retardos es ≈ 0,62-0,66.
El (0,1,1)(0,1,0)₁₂ sólo se equivoca de signo en el retardo 1 y en el 12 pone un
cero, que está más cerca de −0,387 que +0,275. **Añadir el MA que falta empeora
la similitud**, justo al revés de lo que debe pasar. El AR tiene el mismo defecto
(φᵢ = 0,5/(i+1) > 0 siempre), aunque aquí no muerde.

El docstring lo da por bueno —«the structural pattern (cut-offs, decay, seasonal
peaks) is determined by (p,q,P,Q,s), not by exact coefficients»—: el corte sí, el
**signo** de la barra no, y la similitud (`_pattern_similarity`) compara valores
con signo, `abs(theo − emp)`.

Comprobación de la causa: con la plantilla en el convenio de la escuela,
(1 − θB)(1 − ΘBˢ), y todo lo demás igual, el ranking sobre la misma serie queda:

```
(0,1,1)(0,1,1)12  0.879   <- el airline, primero y con margen
(0,1,0)(0,1,1)12  0.820
(0,1,1)(0,1,0)12  0.817
```

## Fix

No basta con invertir el signo fijo: la serie del caso de clase de la P03 (HICP de
España, ∇∇₁₂ ln) tiene r₁ = **+0,24**, y ahí la plantilla invertida fallaría igual
en el sentido contrario. Propuesta: que el signo de cada coeficiente de la
plantilla lo diga la muestra —para cada operador, el signo de la barra empírica
en su retardo (1 para θ₁/φ₁, s para Θ₁/Φ₁)—, o evaluar las dos variantes de signo
por operador y quedarse con la mejor. Lo que distingue un MA de un AR es el corte
y el decaimiento, y eso no depende del signo; el signo sólo tiene que dejar de
penalizar.

## Validation

- Serie G (airline): el (0,1,1)(0,1,1)₁₂ debe salir primero sobre ∇∇₁₂ ln.
- HICP de España, 2002:01-2019:12 (`prc_hicp_minr`, I25, TOTAL): el
  (0,1,1)(0,1,1)₁₂ también debe salir primero (θ̂ < 0 en el convenio de la escuela,
  r₁ = +0,24; Θ̂ = 0,52).
- Test de regresión en `tests/` con las dos series, para que el signo no vuelva a
  decidir el ranking.

## Resolution (2026-09-28)

**The origin is the port, not the template's idea.** The C (`ARMA.c`,
`calcular_coeficientes_psi`, identical from ART_v1 to ART_18.1) builds the
ψ weights in the Box-Jenkins convention, ψⱼ = −θⱼ and ψ_{js} = −Θⱼ, that is
(1 − θB)(1 − ΘBˢ): its representative θ = 0.3 gives a NEGATIVE bar, as the
airline has. The port replaced that simulator with statsmodels'
`ArmaProcess`, which takes the MA polynomial as written (`ma=[1, θ]` is
1 + θB), and passed the C's θ, Θ > 0 unchanged. The AR was right
(`ar=[1, −φ]` is the C's ψ recursion).

**Fix:** the MA template in the BJ convention, as the C. Nothing else
changes. Series G: the airline is first (0.879); (0,1,0)(0,1,1) 0.820 and
(0,1,1)(0,1,0) 0.817 follow.

**Spain's CPI, decided to leave as it is.** On ∇∇₁₂ ln of the 2002–2019 CPI
(atsw's example, r₁ = +0.37) the airline is third, after (1,1)(0,1) and
(1,0)(0,1): the regular ACF and PACF both cut at 1, so AR(1) and MA(1) are
equally legitimate — a known ambiguity of this series — and a template with
θ > 0 cannot make a positive bar. The C does the same. Taking the MA's sign
from the sample would put the airline first there too, but it would part
from the C for a case whose ambiguity is real; not done.

**Validation:** `tests/test_bug_0192_la_plantilla_del_ma_en_el_convenio_bj.py`
(template signs; series G, airline first; Spain's CPI, the seasonal MA in
every top candidate, the regular part between AR(1) and MA(1)). Data in
`tests/fixtures/bug_0192/`.

**Next (decided 2026-09-28):** port the template from the C without
statsmodels, so the convention cannot drift again.
