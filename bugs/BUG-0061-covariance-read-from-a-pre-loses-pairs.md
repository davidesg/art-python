---
id: BUG-0061
title: overparameterization_analysis leía la covarianza de un .pre sin avisar — y una varianza-semilla no correlaciona con nada, así que no daba un número inflado sino que PERDÍA pares enteros
status: fixed
severity: high
component: mcp-server
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-29
reporter: David — auditoría de la escalera .inp/.pre tras BUG-0060
tags:
  - covariance
  - overparameterization
  - file-convention
references:
  - src/art/mcp_server.py (overparameterization_analysis; regla 1 del convenio)
  - bugs/BUG-0027-standard-errors-come-from-the-bfgs-seed.md
  - bugs/BUG-0060-invalid-standard-errors-printed-like-valid-ones.md
  - tests/test_bug_0061_covarianza_desde_un_pre.py
---

## Summary

La regla de la escalera ya estaba escrita —*«los parámetros y sus errores típicos
se leen del `.out`, nunca de reejecutar un `.pre`»*— pero hablaba de **errores
típicos**. La covarianza tiene otro consumidor: **las correlaciones entre
parámetros**, que es lo que `overparameterization_analysis` publica.

Y ahí el daño es de otra naturaleza. Un error típico degenerado sale **pequeño y
creíble**, e infla el `t`. Una **correlación** que involucra una varianza-semilla
sale **cerca de cero**, porque la semilla es `c·I` y no correlaciona con nada. O
sea: no se ve un número raro, se ve **la ausencia de un problema**.

## La medida

`RATIO_m23` del carril DS. Su `.out` —estimación real, 61 iteraciones— publica
tres pares por encima de 0.7:

```
corr[ 8][ 6] =  0.93      AR(3) — AR(1)
corr[ 9][ 7] =  0.98      AR(4) — AR(2)
corr[11][ 1] =  0.80      MA(2) — cos(k=1)
```

Reejecutando su `.pre` (niter=5, con 3 de 11 varianzas todavía en la semilla), la
herramienta devolvía:

```
AR(1) — AR(3)   r=+0.981
AR(2) — AR(4)   r=+0.993
```

**Dos pares en vez de tres, con valores distintos, y sin una palabra de aviso.**
El que desaparece es el tercero — el acoplamiento entre el MA(2) y el armónico
coseno, el menos visible de los tres y el que más falta hacía ver.

## Fix

* `overparameterization_analysis` comprueba la covarianza antes de publicar. Si
  está degenerada dice cuántas varianzas son semilla, **nombra los parámetros
  afectados**, explica que las correlaciones que los involucran se hunden hacia
  cero y que **el listado puede estar incompleto**, y remite al `.out`.
* Si además el fichero leído es un `.pre`, lo dice explícitamente y recuerda la
  regla: **para reestimar se usa el `.inp`; el `.pre` sólo verifica**.
* La regla 1 del convenio de ficheros, en las instrucciones del servidor, se
  amplía de «errores típicos» a **toda la covarianza**, con este caso medido.

Sin degeneración no se imprime nada.

## Nota de alcance

El resto de consumidores de la covarianza ya estaban cubiertos o no la usan:
`model_equation` marca los errores típicos semilla desde BUG-0060; `formal_tests`
trabaja con razones de verosimilitud, no con la matriz; `compare_versions`
publica loglik/AIC/BIC/σ̂ₐ/npar, que son del óptimo y **sí** son válidos leídos de
un `.pre` — que es exactamente lo que el `.pre` fija.

Conviene tenerlo presente al leer cualquier análisis de esta réplica hecho
cargando `.pre`: los estadísticos de AJUSTE son buenos; los de INCERTIDUMBRE, no.
