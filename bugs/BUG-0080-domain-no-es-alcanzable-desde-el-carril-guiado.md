---
id: BUG-0080
title: `domain` no es alcanzable desde el carril guiado — la política declara que «lo declarado gana siempre» y la salida de escape sólo existe en `build_model`, exactamente el defecto que ya se arregló para `objetivo` en la misma función
status: fixed
severity: medium
component: mcp-tools
found_in: 0.1.12
fixed_in: 0.1.12
reported: 2026-09-04
reporter: David / sesión guiada FOOD_UEM (HICP alimentos UEM)
tags: [policy, domain, guided-lane, wiring]
references:
  - src/art/mcp_server.py (guided_identification, confirm_and_estimate, build_model)
  - src/art/policy.py:120 (decide_domain), :197 (decide_lambda)
  - bugs/BUG-0080-repro/repro.py
  - BUG-0015, BUG-0040 (la regla índice y la taxonomía de dominios)
---

## Summary

`policy.decide_domain` es explícito en que su inferencia es una **sugerencia**:

> *«Sigue siendo una SUGERENCIA: se registra en `PipelineResult.domain`, se
> anuncia, y **lo declarado gana siempre** (`ClaudePolicy(domain=…)`,
> `build_model(domain=…)`).»*

Y con razón: el propio docstring argumenta que un índice *«no tiene firma en el
dato que lo distinga de cualquier otra magnitud positiva —lo que lo define es que
su nivel es una convención, y eso no se ve en la serie»*. El dominio lo pone el
analista, no el dato.

Pero `domain=` sólo existe en `build_model`. `guided_identification` no lo tiene,
y `confirm_and_estimate` tampoco. **Recorriendo los nodos uno a uno no hay forma
de declararlo.**

## Impact

La consecuencia es la que BUG-0015 y BUG-0040 vinieron a evitar, por una puerta
distinta. En la sesión: HICP alimentos de la UEM, 2002:01-2019:12. `decide_domain`
devuelve `generic` (el nombre no cruza `_INDEX_PREFIXES` y el recorrido de nivel
de un índice nunca llega al ×3 de `RANGO_MULTIPLICATIVO`), así que λ la decide el
signo de `gap` — y `gap = −0.179` sobre 18 bloques, con IC de la correlación
[−0.502, +0.430] en λ=1 y [−0.626, +0.271] en λ=0: el estadístico se abstiene.
art publicó **«Recomendación: identidad (λ=1)»** sobre un índice de precios.

Que la inferencia falle ahí NO es el defecto —está documentado que puede fallar y
por qué—. El defecto es que **el carril guiado no ofrece la corrección**. Con
`domain="price_index"` declarado, `decide_lambda` devuelve 0.0 sin mirar el
estadístico, que es la respuesta correcta.

Precedente exacto, en la misma función y para el parámetro de al lado — del
docstring de `objetivo` en `guided_identification`:

> *«It was reachable only from `build_model`, so an analyst walking the nodes one
> at a time could not state the purpose at all — and the route is precisely where
> the purpose matters.»*

Se arregló para `objetivo`. `domain` tiene el mismo problema y se quedó fuera.

## Reproduction

`bugs/BUG-0080-repro/repro.py` — determinista, sin datos, sólo firmas:

```
DOMINIOS reconocidos por la politica: ('price_index','multiplicative','ratio','generic')

  build_model              domain= : SI
  guided_identification    domain= : NO
  confirm_and_estimate     domain= : NO

INALCANZABLE desde: guided_identification, confirm_and_estimate
```

## Fix (propuesto)

`domain: str = ""` en `guided_identification`, propagado al nodo Box-Cox igual
que hoy se propaga `objetivo` al nodo estacional: si viene declarado, gana sobre
`decide_domain`, y la salida lo dice («dominio declarado por el analista:
price_index → λ=0 por regla índice»). Mismo parámetro en `confirm_and_estimate`
para que el modelo estimado lo registre.

---

## Fix (aplicado, 2026-09-04)

**1. `guided_identification(domain="")`**, propagado al nodo Box-Cox igual que
`objetivo` al nodo estacional. Un dominio no reconocido se rechaza con la lista.

**2. Y se enruta por `policy.decide_lambda`, no por una copia.** Esto es más de
lo que pedía el reporte, y hacía falta: la copia que vivía en la capa guiada
implementaba **sólo la rama del índice**, así que las dos categorías que BUG-0040
añadió —`multiplicative` y `ratio`, que van en log salvo que el dato lo
desmienta— no llegaban al carril guiado **ni declarándolas**. El comentario del
propio bloque ya advertía por qué: *«Una copia, dos caminos»*, que es lo que
produjo BUG-0015. Ahora la regla vive entera en `policy` y el carril guiado la
consume.

**3. La salida dice de dónde sale el dominio** —«declarado por el analista» o
«inferido por `decide_domain`»— y **por qué** impone lo que impone. Cuando el
dominio no se declaró y la inferencia no es `generic`, recuerda que lo declarado
gana y que se puede volver a llamar.

**4. La recomendación anulada deja de contradecir.** La evidencia del estadístico
sigue verbatim —las correlaciones media-std, que es lo que el analista tiene que
ver— pero su *recomendación* («Confirma λ=1.0»…) se sustituye por una nota que
dice que queda anulada. Dos instrucciones contrarias en la misma pantalla, y la
de arriba se lee primero.

**5. `confirm_and_estimate(domain="")`** hace dos cosas distintas:

- **registra** el dominio en el guion (`spec["dominio"]`). No se puede recuperar
  releyendo el `.inp` —es un dato del analista, no del modelo— así que sin esto
  la razón por la que λ vale lo que vale se pierde;
- y **contrasta** el dominio con la λ que se le pasa. `price_index` con λ=1 no es
  una preferencia: es una contradicción, y es literalmente el caso que abrió el
  bug. No bloquea —el analista manda— pero lo dice.

## Validation — resultado

**(a) El repro sale 0.**

**(b) `tests/test_bug_0080_domain_en_el_carril_guiado.py`**, 15 pruebas.

Una nota sobre la fixture, porque costó dos intentos y el segundo enseña algo:
la serie no puede llamarse «IDX…». `decide_domain` mira `_INDEX_PREFIXES`, así
que ese nombre habría devuelto `price_index` él solo y la prueba no habría
probado nada. Hay que construir una serie que el estadístico mande dejar en
niveles Y cuyo nombre no delate el dominio — que es **exactamente** la situación
de FOOD_UEM: el nombre no cruzaba la lista, el recorrido de nivel no llegaba al
×3, y por eso hacía falta poder declararlo a mano.

**(c) Sobre el caso real que abrió el bug** (`FOOD_UEM_m00.inp`):

```
domain=''             → Recomendación: identidad (λ=1) → lam=1.0
domain='price_index'  → ⚠ REGLA DE DOMINIO APLICADA (declarado por el analista)
                        Se impone λ=0 sobre el λ=1 del estadístico → lam=0.0
```

Y por `confirm_and_estimate` con `lam=1.0` y `domain="price_index"`:

> ⚠ **Dominio `price_index` con λ=1.** … La regla índice dice **λ=0 siempre**.
> Se estima lo que has pedido, pero mira esto antes de seguir.

con `dominio: price_index` guardado en el `spec` del guion.

## Lo que queda del patrón

El §3 del documento de arquitectura llamaba a esto *«la capacidad está en la capa
de abajo; la superficie no tiene puerta»*, con tres instancias: la FLT (0079), el
dominio (0080) y los nodos que el carril guiado no registra salvo llamada aparte.
Las dos primeras están cerradas. La tercera sigue abierta.
