---
id: BUG-0237
title: La puerta de adecuación declara «todavía NO es adecuado» a 5 de 21 modelos VERDADEROS: varios contrastes al 5 % sin corrección por multiplicidad (Q en 12/24/36/39, JB, media, estacionalidad residual)
status: fixed
severity: medium
component: diagnosis
found_in: 0.2.3.dev0 @088933d (+ arreglos sin commit de BUG-0225…0231)
fixed_in: 0.2.3.dev0
reported: 2026-10-08
reporter: David / Claude — batería de contrastes del orden de integración (research/bateria_contrastes_d.py)
tags:
  - diagnosis
  - adecuacion
  - contrastes-multiples
  - formal-tests
references:
  - src/art/diagnosis.py (white_noise, normal, centred, seasonal_residual)
  - src/art/describe.py (aviso «Este modelo todavía NO es adecuado» en formal_tests)
  - bugs/BUG-0236-repro/repro.py
---

## Summary

En la batería, con la especificación VERDADERA y n = 200, `formal_tests` abre con «⚠ Este
modelo todavía NO es adecuado… sus p-valores y sus veredictos no son fiables aquí» en 5 de 21:

| modelo | falla en |
|---|---|
| AR(2) reales, d=0 | ruido blanco (Q): p mínimo = 0,041 |
| AR(2) complejo, d=1 | estacionalidad en los residuos (p = 0,015), en una serie sin estacionalidad |
| MA(1) 0,5, d=1 | ruido blanco (Q): p mínimo = 0,008 |
| AR(2) complejo, d=2 | ruido blanco (Q): p mínimo = 0,004 |
| ARMA(1,1), d=2 | media residual distinta de cero: t = −2,18 |

Es lo esperable de cinco o seis contrastes cada uno al 5 %: el tamaño conjunto se acerca al
25 %. La Q se juzga por el «p mínimo» de sus cuatro retardos, que es aún más liberal.

## Impact

La puerta bloquea la lectura de los contrastes formales («informativos, no concluyentes») en
uno de cada cuatro modelos correctos, y empuja al analista a reformular un modelo que no tiene
nada que reformular (en el carril autónomo, a añadir órdenes).

## Reproduction

`python3 bugs/BUG-0237-repro/repro.py` — las 21 series de la batería (las de
BUG-0236-repro), la especificación verdadera y `describe_formal_tests`; sale con 1
mientras más de 2 de 21 abran con la puerta cerrada.

`ART_NO_VIEWER=1 python bugs/BUG-0236-repro/repro.py`, bloques «0237».

## Root cause

Cada criterio de la puerta se evalúa al 5 % por separado, y la Q por el mínimo de sus p.

## Fix

**Elección: Bonferroni sobre los criterios de la adecuación**, cada uno al
5 %/k, con k = 4 (Q en 3f+3, JB, media residual, estacionalidad residual) si
f > 1 y k = 3 en anuales. Por qué ésta:

- La adecuación es UNA afirmación —el modelo vale— y la puerta la niega si
  rechaza ALGUNO. Para esa decisión Holm y Bonferroni coinciden (el primer paso
  de Holm es α/k), así que Holm no añade nada; Simes/Hochberg exigirían
  dependencia positiva y en la batería no ganan nada (misma tasa al 1 %).
- Bonferroni no supone nada sobre la dependencia entre contrastes, y aquí la
  hay (la Q y la media salen de los mismos residuos).
- No se tocó la opción «Q por su retardo de decisión»: ya era así (BUG-0166,
  el cancerbero 3f+3). Lo que decía «p mínimo» era el TEXTO de la puerta, que
  publicaba el mínimo de los cuatro retardos y no el p que decidía.

Dónde (`src/art/diagnosis.py`): `ALFA_ADECUACION = 0.05` y
`alfa_por_criterio(freq)`; `DiagnosisResult.alfa` (5 %/k, lo pone `diagnose`;
5 % por defecto en un resultado construido a mano). `white_noise`, `normal`,
`centred` (|t| contra el cuantil de la t al nivel α/k; el 2 de Brajín al 5 %) y
la estacionalidad residual (`detect_seasonality(..., significance=α/k)`) usan
ese nivel. Como `clean` y `residuals_ok` se componen de esas piezas, el
veredicto APROBADO/REVISAR, la puerta de `formal_tests` y la parada del bucle de
anómalos siguen siendo UN predicado (BUG-0036, BUG-0211). Lo que rechaza al 5 %
aislado y pasa al nivel de la puerta se publica como SALVEDAD
(`DiagnosisResult.rechazos_aislados`): en la diagnosis y en `formal_tests`,
como ya se hacía con los retardos no cancerberos de la Q. En
`describe_formal_tests` (`src/art/describe.py`) la puerta cita el p del
cancerbero y el nivel por criterio.

Test: `tests/test_bug_0237_puerta_tamano_conjunto.py` — el nivel 5 %/k; un
p = 0,03 en la Q es salvedad y no bloqueo (con el 5 % de antes bloqueaba); la
media con t = −2,18 pasa y se nombra; los 21 modelos verdaderos del repro dejan
como mucho 2 con la puerta cerrada. Falla sin el arreglo.

## Validation

**Los 21 del repro:** antes 5 de 21 «todavía NO adecuados»; ahora **1 de 21**
(d = 2, AR(2) complejo: Q(39) p = 0,0044, un rechazo que también lo es al nivel
corregido). Los otros cuatro (Q p = 0,043 y 0,016, estacionalidad residual
p = 0,015, media t = −2,18) pasan con su salvedad dicha. Como los 21 son
verdaderos, ninguno de ellos es un inadecuado que ahora pase.

**Monte Carlo** (n = 200, f = 12, 100 réplicas por caso, d = 0 y 1):

| | antes (5 % cada uno) | Bonferroni (1,25 % cada uno) |
|---|---|---|
| 14 modelos verdaderos (1400 ajustes): «no adecuado» | 15,9 % | **6,1 %** |
| 16 mal especificados (1600 ajustes): «no adecuado» | 69,8 % | 59,6 % |

El tamaño queda cerca del 5 % (los propios contrastes son algo liberales: Q
2,8 % y JB 2,6 % al 1,25 %). **Sí hay modelos inadecuados que ahora pasan:** la
potencia baja en los errores SUTILES —ARMA(1,1) 0,6/0,3 ajustado como AR(1):
20 % → 6 % (d = 0), 27 % → 12 % (d = 1); como MA(1): 26 % → 15 %, 47 % → 23 %;
MA(1) 0,5 como AR(1): 37 % → 17 %, 39 % → 23 %; AR(2) 0,5/0,3 como AR(1):
61 % → 38 %, 69 % → 48 %—, y no en los gruesos (AR(1) 0,6 o 0,95 como ruido,
AR(2) complejo como AR(1): 99-100 % antes y después; MA(1) como ruido: 98/93 %
→ 87/85 %). Parte de la «potencia» perdida era el propio exceso de tamaño, y
esos casos son los que después recogen la sobreparametrización y los
contrastes de significación. Es el precio de que «adecuado» signifique un
tamaño del 5 %; la salvedad le enseña al analista qué habría rechazado la
puerta de antes, para que lo mire.

**Un cambio de comportamiento en el carril autónomo**, que es consecuencia
directa y se dejó a la vista: en el IPC de Colombia de la tesis
(`tests/test_thesis_i2_chile_colombia.py`) la rama B2 pasa ahora la diagnosis
(su JB p = 0,029 ya no rechaza al 1,25 %) y la B1 no (JB p ≈ 0), así que
`decide_seasonal_route` adopta B2 por adecuación —su paso 0— en vez de dejar
decidir al MEG, que con las dos ramas fallando elegía B1 (f=4 estocástica). El
test se actualizó: Colombia sale B2 con esa razón, y el barrido del MEG y la
f=4 estocástica se comprueban sobre el modelo de la rama B1, que es donde vive
el MEG. Si el analista prefiere que en un caso así siga mandando el MEG, la
regla a revisar es la del paso 0 de `decide_seasonal_route`, no el tamaño de la
puerta.

Suite completa: 2366 passed, 124 skipped, 4 xfailed (con este cambio de test).

