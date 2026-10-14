---
id: BUG-0251
title: Adoptar un modelo del empate dice «coincide con la propuesta» y guarda coincide=True junto a una propuesta que es OTRO orden
status: open
severity: low
component: guion
found_in: 0.2.3.dev0
fixed_in: 
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

## Fix

O guardar como `propuesta` el empate entero («empate: ARMA(0,1), ARMA(1,0),
ARMA(1,1)») o, con la propuesta tal cual, `coincide = "empate"` y el texto
«— elegido dentro del empate (la propuesta era ARMA(0,1))».

## Validation

El repro: con la propuesta ARMA(0,1) y el AR(1) adoptado, la salida no dice
«coincide con la propuesta» a secas.
