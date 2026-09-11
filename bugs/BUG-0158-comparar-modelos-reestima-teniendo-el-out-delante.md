---
id: BUG-0158
title: `compare_versions` reestima los dos modelos teniendo el `.out` delante — 9× más lento para el mismo AIC, y publica los errores típicos de la semilla
status: fixed
severity: high
component: mcp-tools
found_in: 0.2.0
fixed_in: 0.2.1
reported: 2026-09-11
reporter: David — estudio de campo del nodo de intervención
tags:
  - contrato-de-ficheros
  - covarianza
references:
  - BUG-0027
  - BUG-0090
  - BUG-0091
  - BUG-0061
---

## Summary

`compare_versions` (mcp_server.py:6813) carga los dos modelos con
`_load_fitted`, o sea que **los reestima**. El `.out` de cada uno ya trae todo
lo necesario, y `art.outfile` **ya lo parsea**:

    logelf:  10.2200683903      →  r.loglik     (precisión completa)
    Parameters  : 24            →  r.npar
    Observations: 288           →  r.nobs

    AIC = −2·logelf + 2k        BIC = −2·logelf + k·ln(n)

Medido sobre `FOOD_UEM_2025_b01_ukr_n5`:

    leyendo el .out     2,9 ms   AIC = 27,5599   BIC = 115,3874
    reestimando        25,4 ms   AIC = 27,5599

**Mismo número al cuarto decimal, nueve veces más lento.**

## Impact — y no es la velocidad

Reestimar para comparar tiene un coste que la velocidad esconde. Si lo que se
compara es un `.pre` —o un `.inp` que `_write_inp` escribió tras ajustar, que es
el caso normal en una cadena de versiones—, **los valores del fichero SON el
óptimo**: el optimizador arranca ahí, apenas itera, y la covarianza conserva la
semilla del BFGS.

Sobre el mismo modelo:

    SE del .out (34 iteraciones)   0,2315  0,2405  0,2430  0,2405  0,2304
    SE del reajuste (12 iter.)     0,0835  0,0835  0,0840  0,0852  0,0861

**Un factor de 2,8, y es el reajuste el que miente.** La herramienta cuyo
trabajo es comparar dos modelos es la que más fácilmente publica errores
típicos inválidos, justo cuando el analista los está mirando para decidir si
poda un parámetro.

Y el daño es real, no hipotético: en el estudio de campo del nodo de
intervención, esos SE invirtieron el veredicto de significación de dos ω del
episodio de Ucrania en `food` —t = −1,65 / −1,49 del `.out` frente a −4,51 /
−3,96 del reajuste— y llevaron a la conclusión contraria sobre si el modelo
adoptado cumplía la regla «no añadas un parámetro que no sea significativo».

## La regla de cuándo el reajuste miente, que este caso precisa

    sin ARMA   el modelo es lineal en los deterministas, el optimizador
               converge casi de inmediato y la covarianza se queda en la
               semilla.  ITCER m02: phi[1] = −0,0000000000, 9 iteraciones.
    con ARMA   las iteraciones que hacen falta suelen bastar para que los SE
               sean fiables.  FOOD n5: phi[1] = +0,3455, 34 iteraciones en la
               estimación real.

Pero eso vale para la estimación **real**. Un reajuste que arranca en el óptimo
no itera lo suficiente ni con ARMA: 12 frente a 34 en el mismo modelo.

## Fix

`compare_versions` lee el `.out` cuando existe —que es el registro— y sólo
reestima si no lo hay, diciéndolo. Es el mismo arreglo que BUG-0091 aplicó a
`get_out_report` y la misma regla que BUG-0061 aplicó a
`overparameterization_analysis`: **el `.out` es el registro; el `.pre`
VERIFICA que los parámetros no se mueven; para reestimar se usa el `.inp`.**

`art.outfile` ya trae `loglik`, `npar`, `nobs` e `iteraciones`, así que el AIC y
el BIC son dos líneas. Conviene exponerlos como propiedades de `OutFile` para
que no vuelva a calcularlos cada llamador por su cuenta.

## Coda: el arreglo nació muerto, y lo destapó su propia prueba

La primera versión del arreglo leía el `.out` y **no se ejecutaba nunca**:

```python
ne = len(getattr(r, "residuals", []) or []) or (o.nobs - 1)
```

`residuals` es un array de numpy. `res or []` evalúa su verdad y levanta
`ValueError: the truth value of an array … is ambiguous`, dentro de un
`try/except Exception: pass`. La rama entera del `.out` se saltaba en silencio y
la herramienta seguía recalculando.

**Y ninguna prueba lo habría visto**, porque el número recalculado es el mismo
hasta el cuarto decimal: leer y recalcular sólo se distinguen cuando el registro
dice algo que la reestimación no puede producir. Por eso la prueba altera el
`logelf` del `.out` a un centinela —`-424.242424`— y exige verlo en la salida.
El dato tiene que VIAJAR; comprobar que coincide no comprueba nada.

El `except` mudo era la otra mitad: ahora avisa. Un `.out` ilegible es una
noticia, no un detalle.

## Validation

Que `compare_versions` sobre dos modelos con `.out` dé exactamente los AIC/BIC
de esos `.out` sin llamar al motor, y que sus errores típicos sean los del
`.out`. Y que sin `.out` lo diga, como hace `get_out_report`.
