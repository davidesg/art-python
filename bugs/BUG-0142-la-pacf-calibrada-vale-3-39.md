---
id: BUG-0142
title: La PACF calibrada dibujaba +3,39 — Durbin-Levinson sobre una ACF que ya no es admisible
status: fixed
severity: high
component: calibracion
found_in: 0.2.2
fixed_in: 0.2.2
reported: 2026-09-10
reporter: David
tags:
  - calibracion
  - figuras
references:
  - BUG-0131
  - BUG-0132
  - BUG-0133
---

## Summary

En el gráfico de calibración de distorsiones —el que el analista declaró
canónico para calibrar distorsiones y para el análisis de intervención— la barra
roja de la PACF llega a **−3,56** en el retardo 14. Una contribución de esa
magnitud es imposible: la PACF observada y la calibrada están las dos acotadas
en [−1, 1], así que su diferencia no puede pasar de 2.

El número malo no es la contribución: es **la PACF calibrada**, que vale
**+3,394** en el retardo 14 y **+1,134** en el 15. Un coeficiente de
autocorrelación parcial fuera de [−1, 1] no existe.

## Diagnóstico

`_acf_pacf(x, K, omitir=...)` calcula la ACF **por pares retenidos** —cada r(k)
promedia sólo las parejas en las que ninguno de los dos miembros está omitido— y
se la pasa a `_durbin_levinson`. Y ahí está el problema:

> **Una ACF calculada por pares retenidos NO es una función de autocovarianza
> admisible.** La matriz de Toeplitz que forma no tiene por qué ser definida
> positiva, porque cada r(k) se ha estimado sobre un subconjunto DISTINTO de
> observaciones. La ACF muestral completa sí lo es siempre —es una forma
> cuadrática de la propia muestra— y por eso `fue.pacf` nunca da |φ| > 1.

Durbin-Levinson sobre una ACF inadmisible diverge, y la recursión sólo se guarda
de la división por cero (`abs(den) > 1e-12`). Medido sobre `RATIO_m10.pre`
(∇100·ln, n=83, umbral 2,0σ, omitidas las obs. 64, 71 y 75), llevando la
varianza de innovación v_k = v_{k−1}(1 − φ_k²):

| k | φ_k | v_k | den |
|---|---|---|---|
| 12 | +0,3704 | +0,07131 | +0,08265 |
| 13 | **−0,8567** | **+0,01898** | +0,07131 |
| 14 | **+3,3937** | **−0,19957** | **+0,01898** |
| 15 | +1,1340 | +0,05706 | −0,19957 |

La varianza de innovación se derrumba en el 13 y **se hace negativa** en el 14.
El `den` de 0,019 pasa el guardián de 1e-12 sin despeinarse y produce un φ de
3,39. A partir de ahí todo lo que sigue es basura, incluida la v que vuelve a
salir positiva en el 15 por haber multiplicado por (1 − φ²) < 0 dos veces.

La ACF observada NO tiene el problema: los quince retardos de la PACF sin
calibrar caen dentro de [−1, 1]. **El defecto sólo aparece al omitir**, que es
justo lo que esta figura existe para hacer.

## Repro

```python
import numpy as np
from art.mcp_server import _load_fitted
from art.calibracion import _acf_pacf

ts, m = _load_fitted("RATIO_m10.pre")
y = np.asarray(ts.data, float)
w = np.diff(100 * np.log(y)); w = (w - w.mean()) / w.std(ddof=0)
om = {i for i in range(len(w)) if abs(w[i]) > 2.0}
_, pacf_cal = _acf_pacf(w, 15, omitir=om)
print(pacf_cal[13], pacf_cal[14])     # 3.3937…  1.1340…  ← imposibles
```

Sintético y determinista, sin el fichero. **Hace falta estructura
estacional fuerte**: sobre ruido blanco no se reproduce —el máximo |φ| se queda
en 0,29— porque la varianza de innovación no llega a derrumbarse. Es una serie
con la ACF cerca del círculo unidad, que es lo que tiene el ∇ln del RATIO:

```python
import numpy as np
from art.calibracion import _acf_pacf

rng = np.random.default_rng(0)
n, t = 83, np.arange(83)
y = 3.0*np.sin(2*np.pi*t/4) + 0.6*((-1.0)**t) + rng.standard_normal(n)*0.4
y = (y - y.mean()) / y.std(ddof=0)
y[64] += 6.0
om = {i for i in range(n) if abs(y[i]) > 2.0}       # {64}
_, p = _acf_pacf(y, 15, omitir=om)
print(np.abs(p).max())        # 15.32  ← primer |φ|>1 en el retardo 11
```

Un solo anómalo omitido, y la PACF calibrada llega a **15,3**.

## Fix — el estimador, no el dibujo

Decisión del analista: **relleno con ceros (Bartlett)**.

    μ̂ sobre lo RETENIDO
    z̃ₜ = (xₜ − μ̂)  si t retenida,   0  si omitida
    r(k) = Σₜ z̃ₜ z̃ₜ₊ₖ / Σₜ z̃ₜ²

r(k) vuelve a ser la autocorrelación de una sucesión REAL, cuya transformada es
|Z(ω)|² ≥ 0: definida positiva **por construcción**, luego |φ(k)| ≤ 1 siempre.
No hay que detectar nada ni reparar nada.

Se descartaron las otras dos, y por qué:

| | resultado sobre `RATIO_m10`, umbral 2σ |
|---|---|
| eliminación por pares (lo que había) | máx\|φ\| = **3,394** |
| proyección PSD de Higham | máx\|φ\| = **1,000 exacto** — admisible y **singular**: φ(15) = −1,000 dice «determinista», tan inservible como el 3,39 |
| detectar y declarar NaN | pierde los retardos 13-15, que en trimestral son el entorno de 3s donde se lee el orden AR estacional |
| **relleno con ceros** | máx\|φ\| = **0,679** |

Y arregla de paso dos cosas más que no eran el objetivo:

1. **Sin omisión coincide EXACTAMENTE con `fue.acf` y `fue.pacf`** —0,0 de
   diferencia en las dos—. El paquete tenía dos correlogramas observados: la
   eliminación por pares daba r(1)=+0,5819 sobre ∇ln PGAS donde la diagnosis
   daba +0,5749. La tabla de BUG-0048 llegó a publicar `ACF(1)=+0,5749` y
   `PACF(1)=+0,5819` **en la misma tabla**, cuando son idénticos por definición.
2. La recursión lleva ahora la varianza de innovación y devuelve NaN si le
   entra una ACF inadmisible. Es la **red**, no el arreglo: con el estimador
   nuevo no salta —comprobado sobre 400 series de estrés—.

### La objeción doctrinal, que hay que mirar de frente

La cabecera del módulo argumentaba contra sustituir por la media —*«equivale a
un impulso con ω libre… es circular»*— y el estimador adoptado es
**aritméticamente idéntico a sustituir por la media** (verificado: 3,3e-16).

La objeción no sobrevive al requisito de admisibilidad. Cualquier estimador que
(a) quite la contribución de una observación a **todos** los retardos y (b) siga
siendo definido positivo tiene que poner su desviación a cero: c(k)=Σz̃ₜz̃ₜ₊ₖ es
la única forma que garantiza PSD, y «no contribuye» significa z̃=0 ahí. La
disyuntiva real no era «omitir contra sustituir» sino **«omitir de forma
admisible» contra «omitir de forma inadmisible»**. Y la propia medición de la
cabecera ya daba ganadora a la media: error medio 0,0162 contra 0,0212.

El coste es un encogimiento de |r(k)| de aproximadamente n_I/n, y va en la
dirección **conservadora**: puede dejar de detectar estructura, no puede
fabricarla. Para lo que decide esta figura, es el único error que no hace daño.

La cabecera del módulo está reescrita entera con esto.

## Test

`tests/test_bug_0142_pacf_admisible.py` — 45 pruebas, de las que **17 fallan
con el estimador anterior**, incluidas **15 de las 40 series de estrés**: no era
un caso límite, saltaba en el 37% de series realistas con estacionalidad.

Se comprueba la propiedad donde vive —los autovalores de la Toeplitz—, no sólo
su consecuencia; que la red no salte con el estimador bueno; y que sí salte con
una ACF inadmisible hecha a mano.

Y `tests/test_calibracion_correlograma.py` cambia la prueba que fijaba la
doctrina anterior —`test_calibrar_es_OMITIR_y_no_sustituir`— por la que fija
ésta, con la historia dentro, más una nueva que exige la coincidencia exacta
con `fue` y la identidad PACF(1) ≡ ACF(1), que **antes no se cumplía**.
