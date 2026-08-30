---
id: BUG-0024
title: La banda de cuasi-cancelacion se afirma por la DISCREPANCIA, nunca por la distancia: r en la tabla del paper ES el modulo del factor MA, y el codigo lo tiene delante
status: open
severity: medium
component: formal-tests
found_in: 0.1.11
fixed_in: 
reported: 2026-08-25
reporter: David / réplica TFM Bolivia
tags:
  - dcd
  - over-differencing
  - quasi-cancellation
references:
  - src/art/describe.py:1557-1615 (bloque «Par confirmatorio en f=0», rama else)
  - src/art/describe.py:1699-1710 (la recomendación de la banda)
  - tests/test_bug_0022_offaxis_witness.py::test_la_banda_legitima_se_sigue_informando
  - SF_MEG/Borrador/SF_MEG.tex, «The two tests compared», tabla tab:compare
  - bugs/BUG-0022-… (mismo bloque: allí se borraba el SIGNO; aquí se ignora la MAGNITUD)
  - bugs/BUG-0011-… (misma rutina, calibración del crítico)
  - bugs/BUG-0024-repro/repro.py
---

## Summary

El bloque del par confirmatorio en f=0 decide que se está en la **banda de
cuasi-cancelación** por una sola condición: que los dos contrastes **discrepen**.
Nunca mira a qué distancia de la frontera está el testigo, y el rótulo que emite
es concreto:

> *«es la **banda de cuasi-cancelación** (r≈0.90–0.95 en la tabla del paper) …
> En esa banda las representaciones son **equivalentes en previsión**»*

Esa `r` no es una magnitud abstracta. En `tab:compare` la familia es
`N = φ_f(B)⁻¹ θ_f(B;r) a`, y **`r` es el módulo del factor de medias móviles** —
en el caso regular, `|θ̂|`, que el código tiene delante en `od_res.coef_free` y no
consulta.

Medido: con `θ̂ = +0.7780` (`r̂ = 0.78`, distancia 0.222 a la frontera) el informe
afirma igualmente «banda r≈0.90–0.95» y «equivalentes en previsión». La banda que
nombra exige distancia 0.05–0.10.

Es el mismo bloque y la misma especie que `BUG-0022`, un escalón más abajo: allí
se **borraba el signo** del testigo, aquí se **ignora su magnitud**. El arreglo de
`BUG-0022` no toca esto — su rama `else` sigue poniendo `quasi_cancellation =
True` sin mirar la distancia.

## Impact

Media, y acotada por un matiz que conviene decir: en el medio ambiguo el consejo
operativo que acompaña al rótulo —*«no cambies `d` con esta evidencia»*— **sigue
siendo razonable**. Lo que no se sostiene es lo que el informe afirma alrededor:

1. **Falsa precisión.** Nombra un intervalo (`r≈0.90–0.95`) que el propio estimado
   contradice, y lo nombra citando el paper, que es lo que le da autoridad ante
   el lector.
2. **La equivalencia en previsión no está establecida fuera de la banda.** Es la
   propiedad que justifica «decide por parsimonia»; a `r̂ = 0.78` la tabla del
   paper no la respalda, y con `r̂` más bajo el proceso está más cerca de la raíz
   unitaria que de la cancelación.
3. **La discrepancia no es un indicador exclusivo de la banda**, y la tabla lo
   dice sin ambigüedad: a `r = 0.80` los dos lados discrepan el 87 % de las
   veces, y a `r = 0.50` todavía el 20 %. Leer «discrepan ⇒ estoy en 0.90–0.95»
   es el paso que falta justificar.

A quién afecta: a cualquiera que llegue a este bloque con un testigo en el eje
bueno pero lejos de la frontera, que por la fragilidad de ese óptimo (`BUG-0011`,
y el barrido de semillas de `BUG-0022`) no es una rareza.

## Reproduction

```
python3 bugs/BUG-0024-repro/repro.py
```

Sintético, determinista (semilla 7), la misma construcción de `BUG-0022`:
ARIMA(1,1,0) con φ=0.58, n=84, ajustado con un AR(2) **en niveles**. Salida:

```
Shin-Fuller: estacionario = True   (lado AR: 'd basta')
testigo:  theta_hat = +0.7780   LR = 4.791  (crit 5% = 1.94)
  => r_hat = |theta_hat| = 0.778      distancia a la frontera = 0.222
  la banda del paper es r ~ 0.90-0.95, o sea distancia 0.05-0.10.

informe:
  afirma la banda r~0.90-0.95 ...... True
  afirma equivalencia en prevision . True
  distancia impresa ................ 0.2220
```

Esa realización es exactamente la que
`tests/test_bug_0022_offaxis_witness.py::test_la_banda_legitima_se_sigue_informando`
usa como **«la banda legítima»**. Con `r̂ = 0.78` no lo es, así que ese test
consagra el caso: al arreglar esto hay que reetiquetarlo.

## Root cause

`src/art/describe.py`, rama `else` del par confirmatorio (tras el arreglo de
`BUG-0022`):

```python
dist = 1.0 - od_res.coef_free          # se calcula …
if od_res.coef_free < 0.0:
    ...                                 # (BUG-0022: guarda de signo)
else:
    quasi_cancellation = True           # … y aquí no se usa para decidir nada
    lines += [ … "es la **banda de cuasi-cancelación** (r≈0.90–0.95 …)" … ]
```

`dist` entra en el texto como número impreso, pero **no como condición**. La
bandera `quasi_cancellation` —que es la que consume `data["f0_pair"]` y la que
elige el mensaje de la recomendación— se pone por el simple hecho de que los dos
lados discrepen.

Debajo hay una confusión de qué mide qué: la discrepancia es evidencia de estar
en *el medio ambiguo*, que es un rango ancho; la banda `r≈0.90–0.95` es el
extremo de ese medio donde las dos representaciones son intercambiables. El
código las trata como la misma cosa.

## Fix

*(Propuesto, no aplicado — `describe.py` lo está tocando otra rama de trabajo.)*

Graduar por la distancia, con el estimado a la vista:

- **imprimir `r̂ = |θ̂|` explícitamente**, junto a la distancia, para que el lector
  pueda situarlo él mismo en `tab:compare`;
- `dist ≤ 0.10` (`r̂ ≳ 0.90`) → el texto actual, sin cambios: es la banda, y la
  equivalencia en previsión se puede afirmar;
- `0.10 < dist` con `θ̂ > 0` → decir lo que hay: **los dos lados discrepan, y eso
  sitúa el proceso en el medio ambiguo, pero `r̂ = …` queda fuera de la banda
  `0.90–0.95`**; retirar la afirmación de equivalencia en previsión, mantener el
  «no cambies `d` sólo con esto» y remitir a la lectura directa (signo de la
  ACF(1) de `∇^d y`) y a la comparación fuera de muestra;
- `quasi_cancellation` en `data` debería reservarse para el primer caso, que es el
  que la palabra nombra. Si se prefiere no mover la semántica de la bandera,
  añadir `r_hat` y `band` al bloque `f0_pair` y que el consumidor decida.

## Validation

Un test que fije las tres cosas: que con `r̂ ≈ 0.78` el informe **no** afirme el
intervalo `0.90–0.95` ni la equivalencia en previsión; que sí imprima `r̂` y la
distancia; y que con un testigo de verdad en la banda (`θ̂ ≳ 0.90`) el texto actual
se conserve palabra por palabra. Y reetiquetar
`test_la_banda_legitima_se_sigue_informando`, cuya realización (semilla 7) es
precisamente el contraejemplo.
