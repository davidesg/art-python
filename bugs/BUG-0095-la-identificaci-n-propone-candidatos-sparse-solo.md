---
id: BUG-0095
title: La identificación propone candidatos sparse "solo en B^k" — impone una restricción que solo procede a posteriori vía factorización de raíces
status: fixed
severity: medium
component: identification
found_in: 0.1.12
fixed_in: 0.2.0
reported: 2026-09-05
reporter: David / sesión SERV_UEM — identificación regular sobre m03
tags:
  - identificacion
  - sparse
  - restriccion
  - ar_factorization
references:
  - src/art/model_detection.py:617-622 (genera candidatos sparse AR/MA "only at lag k", φ₁=...=φₖ₋₁=0)
  - src/art/model_detection.py:296-317 (sparse_ar_lag/sparse_ma_lag: zero all lags except k)
  - src/art/describe.py:658-661 (etiqueta "AR sólo en B^k" / "MA sólo en B^k")
  - src/art/describe.py:630-640 (_pattern_label: etiqueta del candidato completo)
  - src/art/mcp_server.py (ar_factorization — la vía a posteriori para descomponer raíces)
  - bugs/BUG-0095-repro/repro.py

---

## Summary

La identificación ARMA genera, además de los AR(p)/MA(q) completos, candidatos
**sparse**: un AR o MA con un único coeficiente en el retardo k y todos los
anteriores forzados a cero (φ₁=…=φₖ₋₁=0, φₖ≠0), y los inyecta en el ranking con
la etiqueta "AR sólo en B^k" / "MA sólo en B^k". Esa es una restricción de
identificación impuesta de entrada, cuando la práctica Box-Jenkins estima
siempre el polinomio completo y reserva las restricciones (frecuencia fija,
ciclos, ceros intermedios) para el análisis a posteriori de raíces
(`ar_factorization`). El analista que sigue la lista se lleva un modelo
restringido que no pidió.

## Impact

Contamina el ranking de candidatos con modelos que no son del espacio de
hipótesis legítimo. Medido en SERV_UEM (identificación regular sobre m03):
los candidatos 1 y 3 fueron `ARIMA(0,0,2)(0,0,0)_12 [MA sólo en B^2]` y
`ARIMA(2,0,0)(0,0,0)_12 [AR sólo en B^2]` — el primero con sim=0.780, mejor
que el MA(2) completo. Quien pida "el MA(2) de la lista" se lleva φ₁=0, φ₂≠0,
un modelo distinto del que cree pedir, y la restricción se decidió sin
contraste. La herramienta ya tiene `ar_factorization` para descomponer el
polinomio completo en factores (frecuencia, damping) DESPUÉS de estimar; la
identificación no debe adelantarse.

## Reproduction

En SERV_UEM, identificación sobre `SERV_UEM_m03_sar2.pre`:

```
1. ARIMA(0,0,2)(0,0,0)_12  [MA sólo en B^2]  sim=0.780
2. ARIMA(2,0,0)(0,0,0)_12  [AR sólo en B^2]  sim=0.774
...
```

Los candidatos sparse salen ANTES que los completos del mismo orden. El
analista señaló en la sesión: "nunca estimar solo en B². Eso nunca se hace.
Siempre tienes que estimar un AR(2) completo y un MA(2) completo. Cualquier
restricción es posterior."

## Root cause

`model_detection.py:617-622` añade explícitamente, para cada lag k en
[2, eff_p/q], un candidato `sparse_ar=lag` / `sparse_ma=lag`, que
`model_detection.py:312-317` construye poniendo a cero todos los coeficientes
salvo el k-ésimo. `describe.py:658-661` los etiqueta "solo en B^k". El
comentario del propio código lo admite: "Handles 'AR at lag 2' structures
where lag-1 coefficient is constrained to 0" — una restricción de
identificación impuesta por la herramienta, sin justificación de contrastes,
y que compite en el ranking con los completos. La descomposición en raíces
(frecuencia, período, damping) es exactamente la misión de `ar_factorization`,
que opera sobre el polinomio completo ya estimado; el candidato sparse se la
salta.

## Fix

No generar candidatos sparse en la identificación: que el ranking contenga
solo AR(p)/MA(q)/ARMA(p,q) completos. La estructura "solo en lag k" (si
existe) la revela `ar_factorization` a posteriori sobre el polinomio completo
—por ejemplo un AR(2) con φ₁≈0 es un factor de frecuencia fija, y eso lo dice
la factorización, no una restricción impuesta a mano—. Como mínimo, si se
conservan los sparse, excluirlos del ranking por defecto y mostrarlos aparte,
claramente marcados como "restricción por confirmar, no estimar de entrada".

## Validation

Reidentificar sobre SERV_UEM m03 y comprobar que el ranking no contiene
entradas "[solo en B^k]" entre los candidatos; el MA(2) y el AR(2) completos
deben aparecer sin sufijo y con su similitud. Test sintético: una serie con
ACF/PACF que corte en lag 2 no debe ofrecer "solo en B²" por encima del
completo; `ar_factorization` sobre el completo estimado debe recuperar la
estructura de frecuencia si de verdad existe.

---

## Fix (aplicado, 2026-09-05)

Se toma la variante mínima del reporte —**fuera del ranking, no eliminar**—
porque son plausibles y a veces son la respuesta.

* `suggest_orders(..., incluir_dispersos=False)` **por defecto**. La API limpia
  es lo que impide que quien itere la lista se los lleve sin querer, que es como
  quien pedía «el AR(2) de la lista» acababa con un modelo restringido.
* La **presentación** los pide explícitamente y los ofrece **aparte**, bajo
  «Restricciones por confirmar — NO estimar de entrada», con el porqué.
* El aviso de «decisión ambigua» se juzga **sobre el ranking**, no sobre los
  dispersos: si uno se colaba entre los dos primeros, avisaba de una ambigüedad
  entre cosas que no compiten.

**El argumento, aportado por el analista y verificado.** Para (1 − θB²) en datos
mensuales:

    θ < 0  →  raíces imaginarias puras, ω = π/2, periodo 4  →  la frecuencia f=3
    θ > 0  →  dos raíces reales; ninguna frecuencia fija

**El significado de la restricción depende del signo del coeficiente que aún no
se ha estimado.** Imponerla de entrada es comprometerse con una lectura que
todavía no se puede hacer; después, `ar_factorization` la descubre sola — y fue
tiene operadores AR(2)/MA(2) de frecuencia fija para expresarla bien.

Eso es lo que se imprime junto a los candidatos, porque sin el porqué «no
estimar de entrada» es una prohibición arbitraria.

## Validation — resultado

El repro sale 0. `tests/test_bug_0095_sparse_fuera_del_ranking.py`, 9 pruebas,
incluidas dos que comprueban la aritmética del argumento: que (1−θB²) con θ<0 da
exactamente ω=π/2 y periodo 4, y que el periodo 4 es la frecuencia f=3 en
mensual.
