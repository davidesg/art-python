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

`ART_NO_VIEWER=1 python bugs/BUG-0236-repro/repro.py`, bloques «0237».

## Root cause

Cada criterio de la puerta se evalúa al 5 % por separado, y la Q por el mínimo de sus p.

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
