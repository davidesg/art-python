---
id: BUG-0115
title: Las etiquetas AR_f/MA_f usan el índice de la lista en vez de la frecuencia del factor — el testigo de f=3 se anuncia como f=0, que es la frecuencia cero y significa otra cosa
status: fixed
severity: medium
component: diagnosis
found_in: 0.2.0
fixed_in: 0.2.1
reported: 2026-09-08
reporter: David
tags:
  - meg
  - etiquetas
references:
  - BUG-0034
---

## Summary

`diagnosis.py:397-404` construye las etiquetas de los factores de frecuencia
fija con el **índice de enumeración de la lista**, no con la frecuencia del
factor:

    for f_idx, ff in enumerate(model.ar_f or []):
        if ff.free:
            labels.append(f"AR_f(f={f_idx})")

    for f_idx, ff in enumerate(model.ma_f or []):
        if ff.free:
            labels.append(f"MA_f(f={f_idx})")

Con un solo factor —el caso normal tras `meg_reformulate`— el índice es 0, así
que el testigo MA_f de **f=3** se etiqueta **`MA_f(f=0)`**.

## Impact

No altera ninguna estimación: es una etiqueta. Lo que la hace algo más que
cosmética es que **`f=0` no es un nombre libre en este paquete**: es la
frecuencia cero, donde operan el Shin-Fuller y los dos DCD de sobre y
sub-diferenciación, que aparecen en la misma salida y a pocas líneas de
distancia. La etiqueta nombra un objeto que existe y que es otro.

Observado en el aviso de sobreparametrización de un modelo reformulado en f=3:

    ⚠ Posible sobreparametrización (|corr| > 0.7):
      - corr(sin(k=2), MA_f(f=0)) = -0.780

Ahí el analista lee que el armónico de f=2 está correlacionado con algo de la
frecuencia cero, cuando lo que ocurre es que está correlacionado con el testigo
de f=3 — que es exactamente el parámetro que la reformulación acaba de
introducir, y por tanto la lectura que importa.

Con **dos o más frecuencias reformuladas** —el uso iterativo que la propia
documentación de `meg_reformulate` describe— los índices serían 0 y 1, y
ninguno coincidiría con su frecuencia. El error no se corrige solo al crecer el
modelo: empeora.

## Reproduction

    meg_reformulate(inp_path=<baseline>, base_pre_path=<baseline .pre>,
                    freq=3, output_path=<m05.inp>, with_witness=True)

En la diagnosis del modelo resultante, el bloque de sobreparametrización
etiqueta el testigo como `MA_f(f=0)`. La ecuación del mismo modelo, en cambio,
lo imprime bien:

    (1 − 0.4305·B) ((1 + B²)_f=3 ∇Nₜ − 0.3106) = (1 + 0.9507·B²)_f=3 aₜ

Las dos salidas del mismo modelo se contradicen sobre la frecuencia del mismo
parámetro.

## Root cause

El objeto ya lleva su frecuencia. `fue.model.FixedFreqFactor` la expone como
atributo:

    class FixedFreqFactor:
        """Second-order AR or MA factor with fixed spectral frequency."""
        freq : float
            Fixed frequency in cycles per seasonal period (pfre1 en fue.c).

El código de las etiquetas no la mira y usa el contador del `enumerate`.

## Fix

Una línea en cada uno de los dos bucles:

    labels.append(f"AR_f(f={ff.freq:g})")
    labels.append(f"MA_f(f={ff.freq:g})")

Conviene revisar de paso si hay otras etiquetas construidas con el índice en
vez del atributo, en `diagnosis.py` y en `overparameterization_analysis`, que
es quien consume esta lista.

## Validation

* Reformular en `freq=3` y comprobar que la etiqueta dice `f=3` y no `f=0`.
* Reformular en dos frecuencias (p. ej. 3 y 5) y comprobar que las dos
  etiquetas son `f=3` y `f=5`, no `f=0` y `f=1`.
* Afirmación cruzada: la frecuencia que aparece en la etiqueta debe coincidir
  con la que imprime la ecuación del modelo para el mismo factor. Hoy no
  coinciden, y es la comprobación que habría cazado esto.


---

## Cierre (2026-09-08)

La etiqueta se construye con `int(round(float(ff.freq)))` — la frecuencia del
factor, que es lo único que lo identifica.

Comprobado que no basta con acertar por casualidad: con un solo factor en f=3
sale `MA_f(f=3)` donde antes salía `MA_f(f=0)`, y con tres factores en f=4, f=2 y
f=5 salen los tres con la suya, que el índice habría numerado 0, 1 y 0.

**`describe.py` NO tenía este defecto aunque el patrón se parece.** Allí el
índice de `enumerate` se usa para INDEXAR el vector de valores —`vals[6][i]`—,
que es su uso correcto. Se revisó porque la misma forma en dos sitios es motivo
de sospecha, y esta vez la sospecha no se confirmó.

Cierra la clase una prueba que exige que la etiqueta no vuelva a construirse con
`enumerate`.
