---
id: BUG-0248
title: Cinco avisos que no corresponden al modelo que se acaba de estimar (ruido blanco y ARMA(1,1))
status: fixed
severity: low
component: describe
found_in: 0.2.3.dev0
fixed_in: 0.2.3
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

## Root cause

1. `_overpar_note` (en `describe_diagnosis`) ponía la nota del AR(2) a todo
   par AR–MA, sin mirar el AR.
2. `_auto_scan_section` decidía el siguiente paso con `has_arma` (coeficientes
   ARMA libres): un ruido blanco elegido no tiene ninguno, igual que el m00 de
   la ruta B1, que sí está por identificar.
3. `aviso_se_no_fiable` miraba sólo el origen (`.pre`) y el método de las SE,
   no si había alguna SE.
4. y 5. Las dos condiciones contaban el relleno `ar=[[0.0]]`, `ar_free=[[False]]`
   que fue necesita sin operadores: `not (model.ar or [])` en el DCD y
   `any(v is not None …)` en `_lleva_arma`. Confirmado: es la misma raíz.

## Fix

1. `src/art/describe.py`, `describe_diagnosis`: `_ar_complejo` mira si el AR
   del par (regular, estacional o AR_f) tiene un factor de orden ≥ 2 con raíces
   complejas. Sólo entonces sale la nota del AR(2); si no, «⚠ factor común
   probable: compara las raíces AR y MA — si casi coinciden, se cancelan y
   sobra el par».
2. `src/art/mcp_server.py`, `_auto_scan_section`: `ordenes_decididos` sustituye
   a `has_arma` en los tres `nxt` y en el nodo de distorsión fuerte. Los órdenes
   están por decidir sólo si no hay ARMA libre, el modelo lleva deterministas
   (el m00 de B1 y sus intervenciones) y el guion no tiene nodo `ordenes`. Los
   dos llamantes (`confirm_and_estimate`, `suggest_intervention_form`) le pasan
   la ruta del guion.
3. `src/art/pipeline.py`, `aviso_se_no_fiable`: "" si `_build_param_labels`
   no da ningún parámetro libre.
4. `src/art/describe.py`, DCD: la condición usa `_p_ar` (coeficientes AR
   libres), el mismo recuento que la línea «Candidato: …» de dos líneas antes.
5. `src/art/interventions.py`, `_lleva_arma`: cuenta un coeficiente si es libre
   o, fijo, distinto de cero. El relleno no cuenta (criterio de BUG-0241).

Test: `tests/test_bug_0248_avisos_que_no_corresponden.py` — un test por texto
sobre Buffalo, y uno unitario para `_lleva_arma` (relleno, libre a cero, fijo
no nulo). Fallan los siete sin el arreglo.

## Validation

El repro sale con 0. Sobre Buffalo: m02 dice «factor común probable» junto a
corr = +0.988; el escaneo de m01 termina en «procede a contrastes formales»,
como el pie; `formal_tests` sobre m01.pre no da el aviso de SE ni la frase del
AR; la intervención sobre m01 no lleva la nota de «p CONSERVADOR». Los tests
del escaneo latente (BUG-0212), de la calibración, de BUG-0087/0088/0089 y de
BUG-0090 siguen pasando.
