---
id: BUG-0023
title: The one-step cap on d is absolute where it should be RELATIVE — the guided node jumps d=0→2 before testing seasonality, and neither lane can ever take the legitimate second step to d=2
status: fixed
severity: high
component: identification
found_in: 0.1.11
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-25
reporter: David / réplica TFM Bolivia
tags:
  - integration-order
  - seasonality
  - guided
  - box-jenkins
references:
  - src/art/mcp_server.py:1862-1888 (guided_identification, Call 2)
  - src/art/describe.py:298-303 (el aviso «Considera d=2» del nodo de estacionalidad)
  - src/art/identification.py:345 (recommended_d — capa de EVIDENCIA, no se toca)
  - src/art/policy.py:141 (decide_d — el tope del carril autónomo)
  - bugs/BUG-0016-… (el MISMO defecto, arreglado sólo en el carril autónomo)
  - bugs/BUG-0002-… (fija recommended_d(res)==2 como contrato de la evidencia)
  - src/art/pipeline.py:780 (el carril autónomo llamaba a decide_d UNA sola vez)
  - bugs/BUG-0023-repro/repro.py
---

## Summary

El paso 2 del flujo guiado pide la tabla ADF/KPSS con `max_d=2` fijo y publica
`recommended_d` sin tope. Cuando el ADF no rechaza ni en d=0 ni en d=1 —que es
**exactamente** lo que hace una serie con estacionalidad fuerte— la recomendación
sale **d=2**, saltando dos decisiones de una vez.

Dos cosas están mal a la vez:

1. **Metodológicamente.** En la escuela de Box y Jenkins no se saltan dos
   decisiones sin pasar por los instrumentos de especificación y diagnosis:
   desde d=0 sólo se puede ir a d=1 o quedarse en d=0. ART pretende ser el
   equivalente a un analista formado en la escuela, y aquí no lo es.

2. **Técnicamente.** La regresión del ADF no lleva términos estacionales, así
   que el patrón cae en su varianza residual, infla el error típico del
   coeficiente y sesga el contraste hacia NO rechazar la raíz unitaria — que se
   lee como «vuelve a diferenciar». Y en el flujo guiado la estacionalidad **ni
   siquiera se ha contrastado todavía**: ese nodo es el paso 3. El orden no es
   caprichoso — la estacionalidad sólo empieza a ser visible a partir de d=1,
   porque en la escuela se evalúa sobre una serie más o menos centrada.

El docstring de `recommended_d` presentaba la condición como si fuera una
salvaguarda: *«only reaches d=2 when ADF fails to reject at both d=0 and d=1»*.
No lo es. Es la firma de un contraste sin potencia.

**Y el nodo se contradice a sí mismo:** su texto ofrece exactamente dos
continuaciones —`d=1` o `d=0, D=0`— así que recomienda un valor que él mismo no
admite.

## Impact

Alta. El orden de integración es la decisión de la que cuelga todo lo demás, la
cointegración incluida; y `d=2` sobre una serie de gasto público sobre PIB
significa deriva cuadrática en el nivel, que no es defendible. El analista que
siga la recomendación sobrediferencia e inyecta una raíz unitaria MA espuria
—que es justo lo que BUG-0002 vino a evitar por el otro lado.

Es además **una reaparición**. BUG-0016 es este mismo defecto y está marcado
`fixed` en 0.1.11 — pero el arreglo se aplicó sólo al **carril autónomo**:

| | tope de un paso | tope por estacionalidad |
|---|---|---|
| `policy.decide_d` (autónomo) | `max_step=1` ✔ | parámetro `seasonal` ✔ |
| nodo guiado (`mcp_server.py:1868`) | ✖ | ✖ (imposible: el nodo va antes) |

El carril guiado es el que un analista conduce de verdad, y se quedó fuera.

Encontrado en la réplica del TFM de M. Tapia: sobre `ln RATIO` (gasto público /
PIB de Bolivia, 84 obs trimestrales), con una ACF de **0,86 en el retardo 4**
delante, ART recomendó `d=2`.

## Reproduction

```
python3 bugs/BUG-0023-repro/repro.py
```

Sintético y determinista (semilla 5): paseo aleatorio + patrón trimestral fijo,
n=84. El orden regular es **1 por construcción**; no hay ninguna segunda raíz
unitaria que encontrar.

```
  d=0  ADF p=0.6206 NO rechaza   KPSS p=0.0100 rechaza      -> unit_root
  d=1  ADF p=0.4155 NO rechaza   KPSS p=0.1000 no rechaza   -> ambiguous
  d=2  ADF p=0.0000 rechaza      KPSS p=0.1000 no rechaza   -> stationary

  recomendacion con la tabla hasta d=2 : d = 2   <- el defecto
  recomendacion con la tabla hasta d=1 : d = 1   <- la correcta
  verdad del DGP                       : d = 1
```

Sobre la serie real: `describe_unit_root(RATIO, lam=0.0, max_d=2)` daba `d=2`;
con `max_d=1` da `d=1`.

## La regla, enunciada bien: el tope es RELATIVO

Lo que la escuela prohíbe **no es llegar a d=2**: es saltarse la decisión
intermedia. La secuencia correcta tiene tres tiempos y ninguno se puede omitir:

```
   evaluar d=0 vs d=1   →   estudiar la estacionalidad   →   evaluar d=1 vs d=2
```

A partir del segundo momento la pregunta por `d>1` es **completamente
legítima**, y en ausencia de estacionalidad no queda nada que contamine el ADF.
Formalmente el tope es `max_d = current_d + 1`, no `max_d = 1`.

Esto parte el defecto en dos mitades **de signo opuesto**, y la segunda es la
que faltaba:

| mitad | carril | qué hace | efecto |
|---|---|---|---|
| A | guiado | tabula hasta d=2 desde d=0, antes de contrastar la estacionalidad | **sobre**diferencia |
| B | ambos | nunca da el segundo paso, ni cuando es legítimo | **sub**diferencia |

**La mitad B, medida.** Serie I(2) genuina, n=84, sin estacionalidad:

```
  la EVIDENCIA dice          : recommended_d = 2
  estacionalidad detectada   : False  -> decisión A
  carril autónomo (pipeline.py:780, una sola llamada, current_d=0)
      decide_d(...)                =  1     <- se queda corto
  con el segundo paso
      decide_d(..., current_d=1)   =  2     <- lo correcto
```

`decide_d` **ya** aceptaba `current_d` y `max_step` desde el arreglo de
BUG-0016, y su docstring ya describe el razonamiento con precisión
(*«from d=0 the question of whether a SECOND difference is warranted has never
been put»*). Lo que faltaba era el llamador: **nadie invocaba el segundo paso**,
así que el carril autónomo no podía alcanzar `d=2` NUNCA, ni sobre una I(2)
limpia. El carril guiado tampoco lo ofrecía con un instrumento delante — sólo
una línea de prosa («¿Tendencia residual? → considera d=2»).

Comportamiento tras el arreglo, en los tres casos que delimitan la regla:

| caso | evidencia | estacional | paso 1 | paso 2 |
|---|---|---|---|---|
| I(2) sin estacionalidad | 2 | no | 1 | **2** ✔ |
| I(1) sin estacionalidad | 1 | no | 1 | 1 ✔ |
| I(1) **con** estacionalidad | 2 | sí | 1 | **1** ✔ topado |

La tercera fila es la que muestra que el tope sigue vivo donde debe: con
estacionalidad sin tratar el ADF continúa sesgado, y lo que toca primero es
tratarla — no diferenciar otra vez.

## Root cause

`src/art/mcp_server.py:1868` llamaba

```python
urt = describe_unit_root(ts, lam=lam, max_d=2)
```

con el `2` fijo, y publicaba `urt.data["recommended_d"]` tal cual.
`recommended_d` (identification.py:345) recorre la tabla entera y devuelve el
primer `d` con rechazo del ADF; con la tabla llegando a 2, un doble no-rechazo
por falta de potencia se convierte en la recomendación `d=2`.

Segundo sitio, y el peor de los dos: `describe.py:298` emitía
*«⚠ … Considera d=2»* **dentro del bloque de estacionalidad**, tres líneas
después de haberla detectado. Ahí la contaminación estaba diagnosticada en la
misma salida y se ignoraba.

## Fix

**Dónde NO va el tope.** `recommended_d` es la capa de EVIDENCIA y debe seguir
reportando lo que los contrastes dicen; `tests/test_bug_0015_0016_policy_domain_and_d_cap`
fija ese límite a propósito (*«El tope es de POLÍTICA»*) y `test_bug_0002` fija
`recommended_d(res) == 2` como contrato. El tope va ENCIMA, y el carril guiado ya
tenía dónde ponerlo.

1. `mcp_server.py` — el nodo evalúa desde d=0, así que pide la tabla capada:
   `describe_unit_root(ts, lam=lam, max_d=1)`. Por construcción no puede
   recomendar un d que el propio nodo no ofrezca.
2. `describe.py` — el aviso «Considera d=2» queda condicionado a que **no** se
   haya detectado estacionalidad. Cuando sí la hay, el texto explica que el
   no-rechazo del ADF es contaminación esperada, que primero se trata la
   estacionalidad y que el contraste que vale sobre el modelo estimado es
   Shin-Fuller.
3. `identification.py` — docstring de `recommended_d`: la frase de los dos
   no-rechazos deja de venderse como salvaguarda y se nombra dónde vive el tope
   en cada carril.

**Mitad B — el segundo paso, que faltaba en los dos carriles:**

4. `mcp_server.py`, nodo 3 del guiado — cuando la estacionalidad **no** se
   detecta, el nodo tabula ADF/KPSS hasta `d+1` bajo el epígrafe «¿Hace falta
   una diferencia más? (d → d+1)» y dice si la evidencia sostiene la `d` actual
   o pide otra, con la reentrada preparada. Con estacionalidad detectada no se
   ofrece: ahí el contraste sigue sesgado y lo primero es tratarla.
5. `pipeline.py:780`, carril autónomo — tras resolver la estacionalidad, si la
   decisión es "A" (no hay) se toma el segundo paso con
   `decide_d(..., seasonal=False, current_d=d)`. Ni `decide_d` ni
   `recommended_d` cambian: sólo se les llama como ya admitían.

## Validation

`tests/test_bug_0023_guided_d_single_step.py`, 10 casos.

*Mitad A* — sobre el DGP del repro: que la tabla sin capar recomienda 2 y la
capada 1 (o sea, que el caso sigue siendo el que muerde); que el nodo guiado no
tabula d=2 desde d=0; y que con estacionalidad detectada la salida no contiene
«Considera d=2». Control I(2) sin estacionalidad donde ese aviso **sí** debe
seguir apareciendo.

*Mitad B* — la secuencia de los tres tiempos, `d → estacionalidad → ¿d+1?`, en
los tres casos de la tabla de arriba: I(2) limpia alcanza d=2 **en el segundo
paso y no antes**; I(1) limpia se queda en 1 (el segundo paso no es automático,
sólo se da si la evidencia lo pide); e I(1) estacional se topa en 1 aunque la
evidencia cruda diga 2. Y sobre el nodo guiado: que el epígrafe «¿Hace falta una
diferencia más?» aparece sin estacionalidad y **no** aparece con ella.
