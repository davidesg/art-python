---
id: BUG-0248
title: Cinco avisos que no corresponden al modelo que se acaba de estimar (ruido blanco y ARMA(1,1))
status: open
severity: low
component: describe
found_in: 0.2.3.dev0
fixed_in: 
reported: 2026-10-14
reporter: David / Claude — rodaje de art con el ejemplo lutkepohl_poskitt de sima (Buffalo, carril guiado)
tags:
  - confirm_and_estimate
  - formal_tests
  - textos
references:
  - src/art/describe.py _overpar_note (~l. 2134)
  - src/art/describe.py contraste DCD de sobrediferenciación (~l. 2735)
  - src/art/pipeline.py aviso_se_no_fiable (~l. 280)
  - src/art/mcp_server.py escaneo de anómalos latente (~l. 5310, 5339, 5390)
  - src/art/interventions.py _lleva_arma (~l. 1270)
---

## Summary

En el carril guiado de Buffalo (ln, d = 1; m01 = (0,1,0), m02 = (1,1,1)) art
sacó cuatro textos que no se aplican al modelo (y un quinto en la intervención):

1. **m02, sobreparametrización.** Junto a corr(AR(1), MA(1)) = +0.988:
   «ℹ puede ser normal en AR(2) con raíces complejas — verificar con test RV».
   m02 no es un AR(2): es un ARMA(1,1) cuyos factores (1 − .33B) y (1 − .19B)
   casi se cancelan, el caso de manual de factor común. `_overpar_note` pone la
   nota a todo par AR–MA, sin mirar el orden del AR.
2. **m01, escaneo de anómalos latente.** Termina en «→ procede a la
   identificación ARMA» cuando la identificación ya se hizo y el analista
   eligió (0,0). `nxt` usa `has_arma`, que es falso en un ruido blanco
   ELEGIDO; el pie del mismo informe dice, bien, «contrastes formales».
3. **formal_tests sobre m01.pre.** El aviso largo «estas desviaciones típicas NO
   son fiables» (BUG-0090) sale en un modelo SIN parámetros: no hay ninguna
   desviación típica a la que afecte.
4. **formal_tests, DCD.** «Candidato: ∇^2, sin AR regular» y, dos líneas más
   abajo, «Este candidato lleva el AR del modelo, y con AR esa validación de
   fue no está hecha». m01 no tiene AR. La condición es
   `not (model.ar or [])`; probablemente `model.ar` es una lista de factores
   no vacía con factores vacíos (comprobar).
5. **guided_intervention, llamada 3, sobre un (0,1,0).** La regla de Treadway
   añade «nota: este modelo lleva ARMA, así que el p de arriba es
   CONSERVADOR…». El modelo no lleva ARMA. `_lleva_arma` cuenta como ARMA el
   AR de relleno `[[0.0]]` (fijo a cero) que fue necesita cuando no hay
   ningún operador: `any(v is not None ...)` es cierto para 0.0. Probablemente
   la misma raíz que el 4. Aquí cambia la lectura: sin ARMA el contraste del
   vecino es EXACTO, no conservador (BUG-0089), y la nota dice lo contrario.
   Visto en Buffalo, Minneapolis y Kansas City (0,1,0) + step×2 en 12/1973.

## Impact

Bajo: ningún número cambia. Pero cada uno es un texto que el analista tiene que
descartar a mano, y el 1 apunta a la explicación benigna («puede ser normal»)
justo en el caso en que la correlación sí es un fallo.

## Reproduction

`python3 bugs/BUG-0248-repro/repro.py` — con los datos del ejemplo (`flour_prices.csv`); sale con 1 mientras el bug siga abierto.

    load_data(examples/lutkepohl_poskitt/data/flour_prices.csv, column="Buffalo")   # sima
    confirm_and_estimate(lam=0, d=1, D=0, p=0, q=0, n_harmonics=0, seasonal=False)  # m01: 2
    confirm_and_estimate(lam=0, d=1, D=0, p=1, q=1, n_harmonics=0, seasonal=False)  # m02: 1
    formal_tests(m01.pre, run_meg=False)                                            # 3 y 4

## Fix

1. La nota del AR(2) sólo si el factor AR del par tiene orden ≥ 2 con raíces
   complejas; para un ARMA(1,1) con corr alta, decir lo contrario: «factor
   común probable: compara las raíces AR y MA».
2. `nxt` según el nodo `ordenes` del guion (ya decidido → contrastes
   formales), no según `has_arma`.
3. `aviso_se_no_fiable` vacío cuando el modelo no tiene parámetros libres.
4. Contar los coeficientes AR (no los factores) en la condición del DCD.
5. `_lleva_arma`: un factor cuyas banderas están todas fijas y sus valores a
   cero es el relleno, no un ARMA (mismo criterio que BUG-0241 en guion_adopt).

## Validation

Un test por texto, sobre la serie Buffalo del ejemplo (o una simulada de ruido
blanco con d = 1).
