---
id: BUG-0086
title: La escalera de Ockham arbitra entre step (1a) e impulse (1b) por AIC — y recomienda un impulso transitorio para un escalón permanente de nivel
status: fixed
severity: high
component: interventions
found_in: 0.1.12
fixed_in: 0.1.12
reported: 2026-09-04
reporter: David / sesión guiada FOOD_UEM — escalera 12/2004
tags: [interventions, escalera, AIC, form, reporting]
references:
  - src/art/escalera.py:6-9 (1a y 1b «del MISMO coste … no anidadas»)
  - src/art/escalera.py:16-20 («el AIC no arbitra la subida de escalón»)
  - src/art/escalera.py:208 (mejor_simple = min(simples, key=lambda p: p.aic))
  - src/art/escalera.py:326-327 (describe_escalera: «Cuál es la buena no lo decide el ajuste»)
  - bugs/BUG-0086-repro/repro.py
  - BUG-0083 (la cola de 12/2004 bajo el umbral — por qué el impulso ajustó «mejor»)
---

## Summary

`escalera_de_ockham` documenta que las dos lecturas escalares del peldaño 1
—`1a` escalón permanente, `1b` impulso transitorio— tienen «el MISMO coste —un
parámetro cada una— y no anidadas entre sí» y que «el AIC no arbitra la subida de
escalón». Sin embargo, la selección del peldaño simple es literalmente:

```python
mejor_simple = min(simples, key=lambda p: p.aic)   # escalera.py:208
```

El AIC **sí** arbitra entre `1a` y `1b`. En FOOD_UEM 12/2004 —un pico único en la
serie diferenciada ∇ln, que ES un escalón permanente de nivel— el impulso ajustó
marginalmente mejor (AIC −2002.75 vs −2002.01) y la escalera recomendó «impulse»
(transitorio). La forma correcta es `step`.

## Impact

El carril guiado (`suggest_intervention_form(form="auto")`) recomienda la forma
equivocada para anómalos aislados de un solo período: un cambio permanente de
nivel se modela como impulso transitorio (o al revés), sesgando el modelo en
silencio y obligando al analista a corregir a mano (aquí: `form="step"`).
Socava además la afirmación central del módulo: las dos lecturas escalares no
las decide el ajuste.

## Reproduction

`bugs/BUG-0086-repro/repro.py` — sintético, determinista, sin datos ni motor.
Construye los dos peldaños con los AIC observados en 12/2004 y ejecuta la
expresión de selección:

```
1a step     AIC = -2002.01
1b impulse  AIC = -2002.75
recomendado: 1b        <-- FALLA
```

## Root cause

`src/art/escalera.py:208` elige la lectura simple por AIC:
`min(simples, key=lambda p: p.aic)`. `1a` y `1b` son **no anidadas** (una no
contiene a la otra) y de idéntico coste; el AIC no puede comparar formas no
anidadas, y el propio docstring lo prohíbe. El motivo por el que el impulso
ajustó «mejor» aquí es espurio: el suceso 12/2004 tiene una cola en 01/2005
(z≈−2.2, bajo umbral — BUG-0083), y la componente negativa compensadora del
impulso la captura parcialmente. La lectura correcta es la del residuo observado
—un pico único → escalón permanente—, no la del ajuste.

## Fix

No seleccionar entre `1a` y `1b` por AIC. Cuando el patrón observado es un
extremo aislado sin vecino compensador, el defecto es `step`; la elección entre
`step` e `impulse` debe salir de la forma del residuo y de la pregunta
extramuestral (dominio/suceso conocido), nunca de `min(..., key=p.aic)`.
Concretamente, `mejor_simple` no debe ser el mínimo por AIC: hay que presentar
ambas lecturas (con su ganancia ω(1) y su lectura de Treadway) y dejar que el
dominio/extramuestral decida — o fijar `step` como defecto del pico único.

## Validation

Con la corrección, para un pico único en ∇ln la escalera recomienda `1a` (step)
con independencia del hueco de AIC. El repro sale 0.

---

## Fix (aplicado, 2026-09-04)

**La lectura escalar sale de la FIRMA del residuo, no del ajuste.** Nueva función
`escalera.lectura_escalar(episodio, d) -> (nivel, razón)`, y `mejor_simple` pasa
a ser el peldaño que ella nombra. No recibe modelos: sólo puede mirar la firma.

El criterio es el diccionario de la FLT, sin umbral nuevo:

| en el NIVEL | en ∇ | suma en ∇ |
|---|---|---|
| escalón ω en T | UN impulso ω en T | ω |
| impulso ω en T | DOS impulsos +ω en T, −ω en T+1 | **0** |

* con `d ≥ 1` los residuos viven en ∇:
  - dos extremos contiguos de signo opuesto que **se CANCELAN** son la firma de
    un impulso de nivel → `1b`;
  - todo lo demás —un pico solo, o vecinos que no se cancelan— es la firma de un
    escalón → `1a`.
* con `d = 0` los residuos viven en el nivel y el diccionario se invierte: un
  extremo solo es un impulso (`1b`), una racha del mismo signo es un escalón
  (`1a`).

**Por qué la cancelación y no la razón de magnitudes.** La primera versión
comparaba |z₀|/|z₁| dentro de una banda, y eso ataba la lectura al umbral de
extremo: si el analista bajaba el umbral y el −2.20 de 01/2005 entraba en el
episodio, el par (+3.56, −2.20) tenía razón 1.62 y se leía como impulso — la
respuesta cambiaba por dónde se puso el umbral, no por lo que dicen los datos.
La cancelación no tiene ese defecto porque es la condición ω(1)=0 leída sobre el
residuo: (+3.56, −2.20) suma +1.36, el **38% del pico**, por encima del 35%
declarado (`TOL_CANCELA`), así que es escalón **cuente o no cuente** el vecino
como extremo. Hay un test que fija exactamente esa invariancia.

`TOL_CANCELA` es una convención declarada, no un contraste: el contraste de
ganancia nula se hace después, sobre los ω estimados.

**Dos arreglos más, del mismo defecto:**

- `describe_escalera` dice ahora **qué se leyó y por qué** (`Se lee 1a: un
  extremo aislado (+3.36) sin vecino que lo compense…`), y etiqueta la columna
  de AIC como lo que es: *«está para mirarla, no para arbitrar: entre 1a y 1b
  hay X puntos, y no significan nada»*.
- El respaldo de `suggest_intervention_form` era `esc.recomendado or "1b"` — el
  impulso, que es el lado **menos** conservador de los dos: afirma que el suceso
  revierte. Ahora cae en `esc.nivel_simple`, la lectura que dio la firma.

## Validation — resultado

**(a) El repro sale 0.** Se reescribió: la versión anterior **copiaba la línea
del defecto dentro de sí misma**, así que podía demostrar el fallo pero nunca
validar el arreglo. La nueva llama a `lectura_escalar` y recorre las seis firmas
del diccionario, más dos comprobaciones de que el AIC no entra (ni en el cuerpo
de la función —mirado por AST, porque el docstring sí lo menciona para
prohibirlo— ni en la selección).

**(b) `tests/test_bug_0086_lectura_escalar.py`**, 19 pruebas, incluida la
frontera parametrizada de la cancelación y la invariancia frente al umbral.

**(c) Sobre el caso real, FOOD_UEM 12/2004** (base `m02_ar1`, dominio
`price_index`):

```
extremos cerca de 12/2004: [(35, +3.36)]      vecino 01/2005: z = -1.98
nivel_simple : 1a
criterio     : un extremo aislado (+3.36) sin vecino que lo compense: en ∇
               un impulso solo es la firma de un ESCALÓN de nivel
recomendado  : 1a
  1a  step     AIC = -21.78   ω(1) = +0.880
  1b  impulse  AIC = -22.53   ω(1) = +0.571
  2   step     AIC = -22.22   ω(1) = +0.452
```

`1b` **sigue teniendo el mejor AIC** —0.75 puntos, el hueco que motivó el
reporte— y la escalera recomienda `1a` igualmente. Que es justo el criterio de
validación pedido: *«para un pico único en ∇ln la escalera recomienda 1a con
independencia del hueco de AIC»*.

(Los AIC aparecen aquí en la escala correcta —−21.78 y no −2002— por el arreglo
de BUG-0085, que era el mismo día y el mismo clonador.)

## Lo que este arreglo NO decide

Que la lectura escalar sea `1a` no dice que `1a` sea la forma final. Sobre
FOOD_UEM 12/2004 la forma buena está en el peldaño 2 —`12/2004×2`, dos escalones
en el nivel—, y quien manda subir sigue siendo lo de siempre: Treadway, la
inadecuación, la duración del episodio y el dominio. Lo que se ha arreglado es
que el punto de partida de esa subida ya no lo elige un hueco de AIC entre dos
formas que el AIC no puede comparar.
