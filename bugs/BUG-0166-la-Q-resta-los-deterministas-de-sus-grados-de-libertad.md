---
id: BUG-0166
title: La Q resta TODOS los parámetros de sus grados de libertad —armónicos e intervenciones incluidos— y declara no-ruido-blanco un ruido blanco; con df negativo, siempre
status: fixed
severity: critical
component: diagnosis
found_in: 0.1.0
fixed_in: 0.2.1
reported: 2026-09-11
reporter: David — run 3 de SF_MEG, «hay un bug del Q»
tags:
  - diagnosis
  - ljung-box
  - numero-incorrecto
references:
  - BUG-0025
  - BUG-0165
---

## Summary

El contraste de Ljung-Box corrige sus grados de libertad restando los parámetros
**ARMA** estimados: `df = m − (p+q+P+Q)`. Los regresores DETERMINISTAS —armónicos,
intervenciones, media— **no entran**: no se estiman a partir de la
autocorrelación de los residuos.

art resta `npar`, que es **todos**:

```python
# art/diagnosis.py:596
lb = ljung_box(r, q_check_lags, df_correction=npar)

# fue/plots.py:204 — la etiqueta de la figura
ax_acf.set_xlabel(f"Q({lags - npar}) = {lb_stat:.1f}")
```

Un modelo con 11 armónicos resta 11. Con 20 intervenciones, 20 más. **El df se
va a cero y por debajo.**

## Impact — CRÍTICO

Es el veredicto primario de adecuación del método. De él dependen
`white_noise`, el `q_pass` de la escalera, el `residuals_ok` de los contrastes
formales y la decisión de si el modelo está terminado.

**Ruido blanco PURO, declarado no-ruido-blanco.** n=292, 39 retardos, Q=39,27
(p=0,458 sin corregir, pasa holgadamente):

| npar | df usado | p | veredicto |
|---:|---:|---:|---|
| 1 | 38 | 0,413 | pasa ✓ |
| 11 | 28 | 0,077 | pasa ✓ |
| **13** | 26 | **0,046** | **RECHAZA ✗** |
| 25 | 14 | 0,00033 | RECHAZA ✗ |
| 39 | **0** | 3,7e-10 | RECHAZA ✗ |
| 45 | **−6** | 3,7e-10 | RECHAZA ✗ |

A partir de 13 parámetros el ruido blanco deja de pasar. **Y el df negativo no
da error: da un p-valor.**

**Sobre el modelo de registro de la propia serie del run**, `ES_CPI_m10`
(n=215, npar=13, ARMA reales = 1):

| retardos | Q | df art | p art | df correcto | p correcto |
|---:|---:|---:|---:|---:|---:|
| **12** | 8,61 | **−1** | **0,0033 ✗ RECHAZA** | 11 | **0,658 ✓ pasa** |
| 24 | 14,84 | 11 | 0,190 | 23 | 0,900 |
| 36 | 18,25 | 23 | 0,744 | 35 | 0,991 |

Un modelo adecuado declarado inadecuado por un df de **−1**.

**Y el daño se compone.** El analista lee «no es ruido blanco», añade una
intervención o un orden ARMA, `npar` sube, el df baja, y el rechazo se refuerza.
El defecto empuja exactamente hacia la sobreparametrización que el método existe
para evitar.

## Lo que además confunde

La etiqueta de la figura es `Q(lags − npar)`, donde el número entre paréntesis
son **grados de libertad**; el texto de art escribe `Q(24)`, `Q(36)` donde el
número son **retardos**. La misma notación para dos cosas distintas en la misma
pantalla. En el run 3 la figura decía `Q(28) = 96.1` — que es Ljung-Box sobre
**39** retardos con df=28— mientras el texto reportaba `Q(24) = 73,22`.

## Fix propuesto

`df_correction` debe recibir **sólo los parámetros ARMA**, y no `npar`:

```python
arma = (sum(len(f) for f in (model.ar or []))
        + sum(len(f) for f in (model.ma or []))
        + sum(len(f) for f in (model.ar_s or []))
        + sum(len(f) for f in (model.ma_s or [])))
lb = ljung_box(r, q_check_lags, df_correction=arma)
```

Contando los LIBRES, no los fijos. Y `fue/plots.py` igual — pero eso es un
cambio en `fue`, no en art.

**Y una guarda**: `df ≤ 0` no puede devolver un p-valor. Es «no hay contraste»,
y hay que decirlo, no publicarlo.

**Y la etiqueta**: si el paréntesis son grados de libertad, que lo diga
—`Q(m=39, df=28)`— o que sean retardos como en el texto. Las dos cosas no.

## ¿Entra en la 0.2.1 congelada?

**Sí, sin duda.** Por el criterio de `ESTADO.md`: *publica un número incorrecto
y no lo dice*. Y no es un número cualquiera: es el que decide si un modelo está
terminado.

## Validation

Ruido blanco con n=292 y 39 retardos tiene que **pasar** con 13, 25 y 45
parámetros deterministas. Sobre `ES_CPI_m10`, Q(12) tiene que dar p≈0,66 y no
0,0033. Y un df ≤ 0 tiene que decir que no hay contraste en vez de dar un
p-valor.
