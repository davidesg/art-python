---
id: BUG-0237
title: La puerta de adecuación declara «todavía NO es adecuado» a 5 de 21 modelos VERDADEROS: varios contrastes al 5 % sin corrección por multiplicidad (Q en 12/24/36/39, JB, media, estacionalidad residual)
status: open
severity: medium
component: diagnosis
found_in: 0.2.3.dev0 @088933d (+ arreglos sin commit de BUG-0225…0231)
fixed_in:
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

`python3 bugs/BUG-0237-repro/repro.py` — los 21 modelos verdaderos de la batería; sale con 1
mientras el bug siga abierto (hoy: 5 de 21 con la puerta cerrada).

## Root cause

Cada criterio de la puerta (Q, JB, media, estacionalidad residual) bloquea por separado al 5 %.

**Corrección (2026-10-14): la Q NO decide por el p mínimo.** La puerta de `formal_tests`
(`describe.py`, `_dg_fallos`) usa `DiagnosisResult.white_noise`, que decide con el p del
retardo 3s+3 (39 en mensual), con los grados de libertad descontando los parámetros ARMA
(BUG-0075, BUG-0166). Lo que es el p mínimo es el TEXTO: «ruido blanco (Q): p mínimo = …»
cita el menor p de los cuatro retardos, no el que decidió. De ahí salió esta lectura.
El texto ya está corregido en 0.2.3: «ruido blanco (Q): Q(39) con 38 g.l., p = 0,0163»
(test `tests/test_bug_0237_puerta_cita_la_q_que_decide.py`). El bug sigue abierto por la
otra mitad: qué criterios cierran la puerta.

## Fix

A decidir con el analista (es diseño):
- un tamaño CONJUNTO (Bonferroni u Holm sobre los criterios de la puerta, o la Q por su
  retardo de decisión 3s+3 y las demás como salvedad, como ya hace la diagnosis — BUG-0166);
- o mantener la puerta estricta pero decir el tamaño conjunto («con k contrastes al 5 %, uno de
  cada cuatro modelos correctos falla alguno»), y no llamar «no fiables» a los contrastes
  formales por un p = 0,04 aislado.

Medir antes y después con la fase 2 (docs/PLAN-bateria-orden-integracion-fase2.md).

## Validation

Con muchas réplicas de modelos verdaderos, la tasa de «no adecuado» se acerca al tamaño
conjunto elegido.

## Una opción medida, no adoptada (2026-10-14)

Al arreglar los bugs para 0.2.3 se probó Bonferroni (cada criterio al 5 %/k, k = 4 en
estacional y 3 en anual) sin decidirlo con el analista, y se retiró de la 0.2.3. Lo medido,
como dato para la decisión (n = 200, f = 12, 100 réplicas por caso):

| | verdaderos declarados inadecuados | mal especificados detectados |
|---|---|---|
| hoy (cada criterio al 5 %) | 15,9 % | 69,8 % |
| Bonferroni | 6,1 % | 59,6 % |

La potencia caía en los errores sutiles (ARMA(1,1) estimado como AR(1): 20 % → 6 % con
d = 0), no en los gruesos (85–100 %). En el caso de tesis Colombia el carril autónomo pasaba
de B1 (MEG) a B2 (adecuación). En el repro, 5 → 1 de 21.

La regla del analista (2026-10-14): la Q en s·3+3 con sus grados de libertad (restando los
parámetros ARMA) es el contraste que decide la adecuación; los demás son informativos y pueden
ser contradictorios. Es la opción «la Q por su retardo de decisión y las demás como salvedad»
de arriba. Queda por decidir aparte.

