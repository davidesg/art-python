---
id: BUG-0251
title: Adoptar un modelo del empate dice «coincide con la propuesta» y guarda coincide=True junto a una propuesta que es OTRO orden
status: fixed
severity: low
component: guion
found_in: 0.2.3.dev0
fixed_in: 0.2.3.dev0
reported: 2026-10-14
reporter: David / Claude — rodaje de art con el ejemplo lutkepohl_poskitt de sima (Minneapolis y Kansas City, carril guiado)
tags:
  - guion_adopt
  - empate
references:
  - src/art/mcp_server.py guion_adopt (~l. 8772): coincide_fn acepta cualquier candidato del empate
---

## Summary

El nodo `ordenes` con empate guarda como `propuesta` el PRIMERO de la lista
(Minneapolis: «ARMA(0,1)»; Kansas City: «ARMA(0,0)»). Al adoptar otro de los
empatados (el AR(1) en los dos casos) `guion_adopt` cierra el nodo con

    ◆ guion n5: ordenes = ARMA(1,0) — coincide con la propuesta

y en el guion queda `propuesta: "ARMA(0,0)"`, `decidido: "ARMA(1,0)"`,
`coincide: true`. Es deliberado («la propuesta era el empate», BUG-0229), pero
el texto y el registro no lo dicen: quien lee el guion ve una propuesta y una
decisión distintas marcadas como iguales, y la decisión del analista —elegir
dentro del empate por dominio— desaparece como tal.

## Impact

Bajo: ningún número cambia. Pero el guion es el registro de quién decidió qué,
y aquí borra una decisión del analista.

## Reproduction

`python3 bugs/BUG-0251-repro/repro.py` — con los datos del ejemplo (`flour_prices.csv`); sale con 1 mientras el bug siga abierto.

## Root cause

El `coincide_fn` que `guion_adopt` pasa a `_confirma_nodo` devolvía True para
CUALQUIER candidato del empate (BUG-0229: «la propuesta era el empate»), y
`_confirma_nodo` sólo distinguía True / False / None.

## Fix

La segunda opción de la propuesta: la propuesta tal cual y `coincide = "empate"`
(el campo ya admitía cadenas, como "parcial" de BUG-0217).

- `src/art/mcp_server.py`, `guion_adopt`: `coincide_fn` da True si lo adoptado
  es la propuesta, "empate" si es otro de los empatados, False si no.
- `_confirma_nodo`: con "empate" el texto es «— elegido dentro del empate (la
  propuesta era ARMA(0,1))», y sin razón escrita la pide.
- `guion_map` lo marca «⇄ dentro del empate» con «el asistente propuso: …»
  debajo, y el recuento de propuestas cuenta aparte las elegidas dentro de un
  empate. El HTML del guion (`src/art/guion.py`) dice «se eligió dentro del
  empate».

Test: `tests/test_bug_0251_adoptar_dentro_del_empate.py` — Minneapolis,
propuesta ARMA(0,1), adoptado el AR(1): `coincide == "empate"`, la salida no
dice «coincide con la propuesta» y nombra la propuesta, y el mapa lo marca.
Falla sin el arreglo.

## Validation

El repro sale con 0:

    ◆ guion n5: **ordenes = ARMA(1,0)** — elegido dentro del empate (la propuesta era ARMA(0,1))

Adoptar el propio candidato propuesto sigue dando `coincide: true`
(`tests/test_bug_0207_el_guion_del_carril_guiado.py`).
