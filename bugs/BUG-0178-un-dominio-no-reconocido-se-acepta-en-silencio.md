---
id: BUG-0178
title: Un `domain` que la política no reconoce se acepta en silencio en `build_model` — decide el estadístico, un índice de precios sale en NIVELES, y la cabecera anuncia el dominio como si se hubiera aplicado
status: fixed
severity: high
component: pipeline
found_in: 0.2.1
fixed_in: 0.2.1
reported: 2026-09-12
reporter: David — run 4 automático de IPC_ES
tags:
  - dominio
  - box-cox
  - autonomo
references:
  - BUG-0015
  - BUG-0040
  - BUG-0080
  - BUG-0179
---

## Summary

`domain` no es decorativo: decide λ. La regla del índice —BUG-0015— dice que un
índice de precios va en **log SIEMPRE**, porque su base es una convención
(2016=100) y sólo los cambios relativos significan algo.

`build_model` aceptaba cualquier cadena. Un valor que `policy.DOMINIOS` no
reconoce no levanta nada: cae a `decide_domain`, decide el estadístico, y sobre
un índice de precios eso da **λ=1**. Y la cabecera lo anuncia como si el dominio
se hubiera aplicado.

## Reproduction

Medido sobre IPC_ES (n=216, 01/2002–12/2019), misma serie y mismo código:

    sin domain                       →  λ = log (λ=0)        · decide el dominio
    domain="price_index"             →  λ = log (λ=0)        · decide el dominio
    domain="índice de precios"       →  λ = identidad (λ=1)  · decide el estadístico

Y la salida del tercer caso:

    **Dominio:** índice de precios  (inferido; lo declarado gana — `domain=…`)
    **λ:** identidad (λ=1)  (gap=-0.272 · decide el estadístico)

Las dos líneas se contradicen —«inferido» y «lo declarado gana»— y ninguna dice
que el valor se descartó.

## Cómo se descubrió

Preparando el run 4 automático escribí en las instrucciones del ejercicio
`domain="índice de precios"`, en español. El modelo salió en niveles con once
armónicos de coeficientes 25 y 50, y lo reporté al analista como una
**divergencia entre el carril guiado y el autónomo**. No lo era: era el valor
que yo había pasado. La medición de arriba lo deshace.

O sea que el defecto produjo, además del modelo equivocado, un informe
equivocado — que es lo que hace un fallo silencioso.

## Impact

λ=1 sobre un índice es lo que BUG-0040 midió en PGAS: con λ=1 **ninguno de los
seis modelos alcanzó la adecuación**, porque la heterocedasticidad que el log
elimina reaparece como no-normalidad. El modelo es otro, la diagnosis es otra, y
no hay aviso.

*Publica un número incorrecto y calla.* Entra.

## Root cause

**La regla estaba en dos de las tres puertas.** `guided_identification`
(`mcp_server.py:4666`) y `confirm_and_estimate` (`:6131`) rechazaban lo no
reconocido, cada una con su copia del mismo `if`. `build_model` —la puerta del
carril **autónomo**— no tenía ninguna.

Es literalmente la lección que BUG-0015 dejó escrita en el código, tres líneas
por encima de donde faltaba:

> *La regla vive en `policy`, no aquí: tenerla sólo en esta capa es lo que
> produjo BUG-0015 —el camino autónomo partía una familia de ocho IPC entre logs
> y niveles—. **Una copia, dos caminos.***

Dos copias y tres caminos.

## Fix

`dominio_declarado(domain) -> str` en `mcp_server.py`, **una sola vez**: valida
contra `policy.DOMINIOS`, devuelve el valor limpio, y levanta `ValueError` con
la lista de los válidos para que cada puerta lo convierta en su `_err`.

Las tres puertas pasan por él; las dos copias anteriores se retiran. Añadir una
tercera copia habría sido repetir el defecto con la forma del arreglo.

## Validation

`tests/test_bugs_0178_0179_el_carril_autonomo.py`:

- `build_model(domain="índice de precios")` se rechaza, y el mensaje **nombra
  los cuatro valores válidos** — un rechazo que no dice qué vale obliga a
  adivinar;
- los cuatro `policy.DOMINIOS` pasan; `""`, `"   "` y `None` significan «no
  declarado»;
- **la regla aparece UNA vez en el fuente** — el test cuenta las copias;
- las tres puertas (`build_model`, `guided_identification`,
  `confirm_and_estimate`) pasan por `dominio_declarado`;
- con `domain="price_index"` la λ sigue saliendo log: no basta con rechazar lo
  malo, el dato bueno tiene que APLICARSE.
