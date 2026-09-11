---
id: BUG-0170
title: `easter` se ignora en silencio al encadenar con `base_pre_path`, y entonces NO queda ninguna vía para añadirlo a un modelo existente
status: open
severity: high
component: mcp-tools
found_in: 0.1.0
fixed_in:
reported: 2026-09-11
reporter: David — run 3 de SF_MEG, incidencia C-6
tags:
  - easter
  - contrato-de-ficheros
  - hueco
references:
  - BUG-0097
  - BUG-0103
  - BUG-0116
  - BUG-0162
---

## Summary

`confirm_and_estimate(..., easter=True, base_pre_path=<el .pre>)` devuelve un
modelo **sin** el regresor de Semana Santa, sin decir nada. Medido:

    encadenado con base_pre_path  →  regresores easter en el `.pre`:  0
    vía fresca desde el `.inp`    →  regresores easter en el `.pre`:  1

En el run 3, `A_m04` salió con 11 deterministas y **ℓ y AIC idénticos a `A_m03`**
— la señal de que no se añadió nada—, y era la llamada del §3 de las
instrucciones, la que el run venía a ejecutar.

## Y está DOCUMENTADO, que es lo que lo empeora

```
easter : … Like n_harmonics, it is ignored when base_pre_path is given — the
         deterministics come from the .pre, and if the .pre already carries it,
         it is inherited.
```

No es un accidente: es una limitación conocida, escrita en el docstring **y que
la herramienta no menciona en ejecución**. Otra vez lo mismo — una regla que vive
en la prosa y nada la enuncia donde se usa. El analista pasó el argumento, la
herramienta lo aceptó, y devolvió un modelo como si lo hubiera puesto.

## El hueco, que es el daño de segundo orden

Si `easter` se ignora al encadenar, **no queda ninguna vía para añadirlo a un
modelo existente**. Volver al `.inp` fresco pierde todas las intervenciones y
todas las decisiones tomadas desde entonces, que es justo lo que el convenio de
ficheros existe para conservar.

Es la misma forma que BUG-0162 —sólo se puede añadir, no modificar— aplicada a
los deterministas en vez de a las intervenciones. Y con una diferencia: allí el
`.pre` anterior era una salida real; aquí no hay ninguna.

Contexto que lo agrava: **de los 84 `.inp` del corpus de SF_MEG, ninguno lleva
easter** (BUG-0161 midió lo mismo con δ). El regresor existe desde BUG-0097 y la
ruta desde BUG-0103, y sigue sin usarse nunca. Este defecto es una de las razones.

## Fix propuesto

Dos partes, y la primera es obligatoria aunque no se haga la segunda:

1. **Que lo diga.** Si `easter=True` llega con `base_pre_path` y el `.pre` no lo
   trae, avisar: «`easter` se ignora al encadenar; el `.pre` no lo lleva, así que
   este modelo NO lo tiene». Aceptar un argumento y descartarlo en silencio es
   el peor de los tres comportamientos posibles.
2. **Que se pueda.** Añadir el regresor sobre los deterministas heredados —no
   sustituirlos— es lo que el analista pide cuando lo pasa. Lo mismo vale para
   `n_harmonics`, que está en la misma frase del docstring.

## Validation

`confirm_and_estimate(easter=True, base_pre_path=X)` sobre un `.pre` sin easter
tiene que producir un modelo CON easter, o avisar de que no lo hará. Nunca
devolver silenciosamente el mismo modelo.
