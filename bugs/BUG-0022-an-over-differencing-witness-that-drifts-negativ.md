---
id: BUG-0022
title: An over-differencing witness that drifts NEGATIVE is reported as quasi-cancellation — the distance to the boundary is computed with abs(), erasing the sign that says the witness left the f=0 axis
status: fixed
severity: high
component: formal-tests
found_in: 0.1.11
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-25
reporter: David / réplica TFM Bolivia
tags:
  - dcd
  - over-differencing
  - integration-order
references:
  - src/art/describe.py:1557-1610 (bloque «Par confirmatorio en f=0»)
  - src/art/describe.py:1699-1720 (la recomendación)
  - src/art/formal_tests.py:544-600 (dcd_overdiff_regular y su docstring)
  - bugs/BUG-0011-… (misma rutina, calibración del crítico; allí θ̂ es POSITIVO)
  - bugs/BUG-0009-… (misma rutina, colisión de slot del testigo)
  - bugs/BUG-0022-repro/repro.py
---

## Summary

`dcd_overdiff_regular` documenta explícitamente su propio modo de fallo:

> *«Left free from a data-driven start, a plain regular MA can drift NEGATIVE —
> its root then points toward B=−1 and it measures the **Nyquist** (semiannual)
> frequency, not f=0. The +0.85 start keeps the witness on the f=0 axis.»*

Cuando esa salvaguarda no sujeta al testigo y θ̂ sale **negativo**, la lectura en
f=0 deja de ser válida: la raíz del testigo apunta a B=−1 y está midiendo otra
frecuencia. **Nada lo comprobaba.** Y la narrativa hacía algo peor que callar:
medía la distancia a la frontera como

```python
abs(1.0 - abs(od_res.coef_free))      # el abs() INTERIOR borra el signo
```

de modo que un θ̂ = −0.4668 se presentaba **«a 0.5332 de la frontera»** —dentro
de la banda de cuasi-cancelación r≈0.90–0.95— cuando la distancia real a θ=+1 es
**1.4668** y el testigo está en otro eje. El informe concluía entonces que las
dos representaciones son *equivalentes en previsión* y que la decisión sobre `d`
se toma «por parsimonia», que es una conclusión fabricada por el borrado del
signo.

Y la recomendación cerraba el círculo, **pero no callando**: la rama de la
discrepancia pone `quasi_cancellation = True`, así que el informe **sí** emitía
un aviso — el equivocado. Decía «banda de cuasi-cancelación en f=0 … NO cambies
d con esta evidencia — decide por parsimonia (quédate con la actual)». Sobre una
serie que es I(1) por construcción y se está ajustando en niveles, eso es una
instrucción activa a quedarse con `d = 0`. **Es peor que el silencio**: un
informe que no dice nada deja al analista mirando el número; éste le da una
razón, con cita del paper, para no mirarlo.

*(Corregido el 2026-08-25 al verificar el comportamiento previo contra el código
de `HEAD`: la primera versión de este parte decía que el informe terminaba en
«Los contrastes formales no detectan problemas». No es alcanzable por esta rama
—`quasi_cancellation` ya estaba puesta— y el daño real es el de arriba. Ver
«Validation».)*

## Impact

Alta, y de la especie mala: no rompe nada, produce un veredicto plausible y
equivocado sobre el **orden de integración**, que es la decisión de la que
cuelga todo lo demás (cointegración incluida). El mensaje «banda de
cuasi-cancelación, decide por parsimonia» invita a quedarse con la `d` actual —
justo lo contrario de lo que toca cuando el testigo no ha medido f=0.

Sólo se dispara cuando los dos lados del par **discrepan** (Shin-Fuller dice
estacionario y el DCD dice `d+1`), que es la única rama que emite el texto de la
banda. Con AR(2) de raíz casi unitaria y frecuencia baja esa discrepancia es la
situación normal, no la rara.

Encontrado en la réplica del TFM de M. Tapia (tipo de cambio real de equilibrio
en Bolivia): sobre `ln PGAS` en niveles, ART informó θ̂=−0.4668 «a 0.5332 de la
frontera» y el analista estuvo a punto de aceptar el empate como veredicto sobre
la integración de la serie. La lectura correcta —∇ln PGAS tiene ACF(1)=+0.57, o
sea que la diferencia no sobra— apunta a I(1) sin ambigüedad.

## Reproduction

```
python3 bugs/BUG-0022-repro/repro.py
```

Sintético, autocontenido y determinista (semilla 9). DGP: ARIMA(1,1,0) con
φ=0.58, n=84 — **I(1) por construcción**. Se le ajusta un AR(2) en niveles, que
es lo que hace quien cree la serie estacionaria; eso reproduce la configuración
de `ln PGAS`:

```
ACF(1) de la primera diferencia = +0.438  (positiva => la dif NO sobra)

testigo:  theta_hat = -0.5702   LR = 10.135   (crit 5% = 1.94)
  distancia a la frontera theta=+1
    formula ANTIGUA  abs(1-abs(th)) = 0.4298   <- lo que se informaba
    distancia REAL         1 - th   = 1.5702
```

Un dato lateral que el barrido de semillas dejó y conviene no perder: sobre el
**mismo** DGP el testigo aterriza en cualquier punto entre −0.57 y +1.00 según la
realización. La fragilidad de ese óptimo es materia de BUG-0011, no de éste,
pero es la que hace que el caso negativo no sea una rareza.

## Root cause

`src/art/describe.py:1573` (antes del arreglo):

```python
f"{abs(1.0 - abs(od_res.coef_free)):.4f} de la frontera: es la "
```

El `abs()` exterior es inofensivo; el **interior** es el defecto. La frontera de
sobrediferenciación en f=0 está en θ=+1 y sólo en θ=+1 — es el factor (1−B). La
distancia es `1 − θ̂`, con signo. Al aplicar `abs()` al coeficiente, un testigo
en el eje de Nyquist (θ̂<0, raíz hacia B=−1) se refleja sobre el eje de f=0 y
aparece a la distancia que le correspondería a |θ̂|.

Detrás hay una segunda ausencia, que es la sustantiva: en ninguna parte se
comprueba `coef_free < 0`, pese a que la rutina que produce el número declara
ese caso como su modo de fallo conocido.

## Fix

`src/art/describe.py`, rama del par confirmatorio en f=0:

- distancia con signo, `1.0 - od_res.coef_free`;
- **guarda de signo**: si `coef_free < 0` no se emite el texto de la banda de
  cuasi-cancelación (ni se marca `quasi_cancellation`). En su lugar el informe
  dice que el testigo se salió del eje f=0, da la distancia real, advierte de
  que el lado MA no es interpretable como veredicto sobre `d` en esa corrida,
  remite a repetirlo sobre la línea base determinista —que es donde el docstring
  pide correrlo— y ofrece la lectura directa que sí vale: el signo de la ACF(1)
  de ∇^d y;
- la recomendación gana la rama correspondiente: donde antes salía el aviso de la
  banda —que respalda la `d` actual— ahora sale el de eje, que dice que el lado
  MA no da veredicto y ofrece la lectura que sí vale. La rama nueva va detrás de
  `quasi_cancellation`, así que cubre además el caso en que los dos lados
  **coinciden** con el testigo fugado, donde antes no lo miraba nadie.

## Validation

`tests/test_bug_0022_offaxis_witness.py` fija las dos mitades: que con θ̂<0 el
informe **no** contiene «cuasi-cancelación», sí contiene el aviso de eje, y que
la distancia impresa es `1−θ̂` y no `|1−|θ̂||`. Se conserva un caso con θ̂>0 y
discrepancia para comprobar que la banda legítima se sigue informando como antes.

**Cuál de esos asertos muerde y cuál no.** El que discrimina es el par «no está
el texto de la banda / sí está el del eje», más la distancia. El aserto
`"no detectan problemas" not in recommendation` **no distingue nada**: antes del
arreglo la recomendación tampoco cerraba ahí — cerraba en el aviso de la banda.
Se conserva porque es la propiedad que se quiere garantizar hacia adelante, no
porque falle sin el arreglo.

**El comportamiento previo, medido y no descrito** (2026-08-25): se extrajo
`HEAD` a un árbol aparte y se corrió `bugs/BUG-0022-repro/repro.py` contra él.
Salida: θ̂=−0.5702 «a 0.4298 de la frontera … es la **banda de
cuasi-cancelación**», y recomendación «NO cambies d con esta evidencia — decide
por parsimonia (quédate con la actual)». Sobre la serie real (`ln PGAS`, AR(2) en
niveles) las cifras del parte se reproducen exactamente: θ̂=−0.4668, distancia
informada 0.5332, real 1.4668, y ACF(1) de ∇ln PGAS = +0.577.
