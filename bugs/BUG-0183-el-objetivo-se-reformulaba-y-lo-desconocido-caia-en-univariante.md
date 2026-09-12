---
id: BUG-0183
title: El objetivo del análisis viajaba como texto libre — el asistente ofreció «Previsión / Estructural / Ambos», se perdió MULTIVARIANTE, y lo que art no reconocía se convertía en «univariante» en silencio
status: fixed
severity: high
component: mcp-tools
found_in: 0.2.0
fixed_in: 0.2.1
reported: 2026-09-12
reporter: David — run 6 de IPC_ES
tags:
  - objetivo
  - protocolo
  - multivariante
  - esquema
references:
  - BUG-0155
  - BUG-0178
  - BUG-0180
---

## Summary

El protocolo pregunta para qué es el modelo, con tres opciones: **univariante ·
multivariante · estructural**. En el run 6 el asistente preguntó esto:

    · Previsión — Prima la capacidad predictiva y la parsimonia.
    · Análisis estructural — Prima la interpretación…
    · Ambos / sin preferencia — Equilibrio entre previsión e interpretación.

Desapareció **multivariante**, y aparecieron dos valores que art no entiende.
Palabras del analista: *«no el modelo para análisis multivariante… ¿qué sentido
tiene poner esa lista?»*. Ninguno: la lista existe **por** la opción 2, que es la
única que VETA algo —la raíz unitaria estacional, que haría incomparables los
órdenes de integración de un sistema—.

## Root cause

Tres piezas, y ninguna lo impedía:

1. **`objetivo` era `str` en el esquema** de `guided_identification`,
   `build_model` y `batch_build`: el cliente no recibía la lista de valores, así
   que el asistente la reescribió a su gusto. Es lo que BUG-0155 arregló para
   `evento_naturaleza`.
2. **La política lo absorbía en silencio.** `policy.decide_seasonal_route`:

       obj = (objetivo or OBJETIVO_POR_DEFECTO).strip().lower()
       if obj not in OBJETIVOS:
           obj = OBJETIVO_POR_DEFECTO        # «previsión» → univariante

   Mismo patrón que el `domain` de BUG-0178: un valor que nadie reconoce cae al
   defecto y el análisis sigue como si se hubiera elegido.
3. **El protocolo daba las opciones en prosa**, sin decir que cada una es un
   valor y que no se reformulan. Y la sección autónoma que se escribió en
   BUG-0180 mandaba pasar `objetivo=` a `confirm_and_estimate`, que **no tiene
   ese parámetro**: FastMCP lo ignora sin error, así que el asistente habría
   creído declarar «multivariante» sin que llegase a ninguna parte.

## Y en el carril autónomo, el multivariante no tenía dientes

`objetivo` sólo llega a `guided_identification` (el nodo estacional) y a
`build_model`/`batch_build`. `formal_tests` y `meg_reformulate` —donde el MEG
propone y aplica la estacionalidad estocástica— no lo conocen. En el run 6 el
modelo final lleva f=3 estocástica (`ifadf[3]=1`): con objetivo multivariante,
nada lo habría impedido.

## Impact

Un usuario que necesita el modelo para un VECM no podía pedirlo, y si lo pedía
con otras palabras, art hacía otra cosa sin decirlo. *Una puerta queda cerrada a
su uso normal* y *publica… y calla*. Entra.

## Fix

- `_Objetivo = Literal["univariante", "multivariante", "estructural"]` en las
  tres herramientas: el esquema MCP publica la lista, y un valor ajeno se
  rechaza en la frontera.
- `objetivo_declarado()` —un guardián, un sitio, como `dominio_declarado`— para
  quien llame sin pasar por el esquema: rechaza lo desconocido diciendo cuáles
  valen y que prever una serie sola es «univariante».
- Protocolo: **«PRESÉNTALAS TAL CUAL: LAS TRES, CON ESOS NOMBRES»**, que no se
  añaden «previsión» ni «ambos», y por qué la lista existe. `objetivo=` se pasa
  a `guided_identification` y a `build_model`/`batch_build`, **y a ninguna otra**.
- Carril autónomo: *«CON OBJETIVO MULTIVARIANTE, LA ESTACIONALIDAD QUEDA
  DETERMINISTA — ni D=1 ni ifadf[f]=1»*, dicho como regla que lleva el LLM
  porque `formal_tests` y `meg_reformulate` no conocen el objetivo.

`decide_seasonal_route` conserva su caída al defecto para quien la llame
directamente: por las puertas de art ya no le llega nada que no reconozca.

## Pendiente para 0.3

Que `formal_tests` y `meg_reformulate` reciban el objetivo y apliquen el veto
ellos mismos. Hoy la regla del multivariante en el carril autónomo la sostiene
el protocolo, o sea que es una costumbre y no una propiedad del sistema.

## Validation

`tests/test_bugs_0182_0183_rampa_y_objetivo.py`:

- **guardián**: toda herramienta con `objetivo` en el esquema lo publica como
  enum con los tres valores de `policy.OBJETIVOS`;
- los tres valores pasan, sin distinguir mayúsculas; vacío es «univariante»;
- «previsión», «ambos», «sin preferencia», «forecast» se rechazan y el mensaje
  nombra «multivariante»;
- `build_model(objetivo="previsión")` ya no se convierte en univariante;
- el protocolo manda presentar las tres tal cual, no manda el objetivo a
  `confirm_and_estimate`, y lleva la regla del multivariante en autónomo.
