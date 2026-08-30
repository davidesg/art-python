---
id: BUG-0040
title: the domain taxonomy was binary (price_index | generic), so a multiplicative magnitude had nowhere to fall and its λ was decided by the sign of a noise statistic — two independent lanes made the same error on the same series
status: fixed
severity: high
component: policy
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-28
reporter: David / réplica TFM Bolivia — hallado por el experimento del chat limpio
tags:
  - box-cox
  - domain
  - autonomous
  - incomplete-fix
references:
  - src/art/policy.py (decide_domain, decide_lambda, DOMINIOS, RANGO_MULTIPLICATIVO)
  - src/art/mcp_server.py (build_model — el anuncio del dominio)
  - bugs/BUG-0015-index-rule-missing-from-the-autonomous-policy.md (el arreglo que se quedó corto)
  - bugs/BUG-0040-repro/repro.py
  - tests/test_bug_0040_domain_taxonomy.py
---

## Summary

```python
def decide_domain(ts) -> str:
    return "price_index" if name.startswith(_INDEX_PREFIXES) else "generic"

def decide_lambda(boxcox_data, domain=None):
    if domain == "price_index":
        return 0.0
    gap = boxcox_data.get("gap", 0.0)
    return 0.0 if gap >= 0 else 1.0
```

Dos categorías. Un **precio** —magnitud multiplicativa con cero natural, donde el
log es práctica estándar— cae en `"generic"`, y ahí su λ la decide el **signo**
de `gap`, un estadístico que sobre series cortas es ruido.

Es **el arreglo de BUG-0015 quedándose corto**. Aquél añadió el dominio a la capa
de política, con razón, pero con las dos únicas categorías que su caso
necesitaba. Y el texto que art imprime al analista dice *«λ=0 es preferible si la
serie es un índice de precios **o magnitud multiplicativa**»* — el código no
tenía la segunda.

## Cómo se encontró: dos carriles, el mismo error

PGAS, precio de exportación del gas boliviano, 95→500 USD/t, `gap = −0.023`.

1. **La heurística por lotes** tomó λ=1 y el modelo salió con `JB = 73.8`.
2. **Un analista LLM sin ningún contexto previo** (experimento del chat limpio,
   modelo distinto de Claude) tomó λ=1 y lo razonó así:

   > *«Es un precio con cero natural, **no un índice**, así que la
   > transformación la decide el estadístico.»*

**No fue un descuido: es la taxonomía leída correctamente.** El segundo carril
articuló exactamente la regla que el código implementa.

Consecuencia medida en ese carril: **ninguno de sus seis modelos de PGAS alcanzó
la adecuación.** El JB fue de 46.7 a 8.9 y nunca pasó, porque la
heterocedasticidad que el log elimina reaparece como no-normalidad. Cerró
aceptando `JB=12.12 (p=0.0023)` con el argumento de que los contrastes formales
suponen ruido blanco y no normalidad — defendible como lectura, pero la
no-normalidad persistente **sin anómalos** es la firma de la λ equivocada.

## Fix

**Cuatro categorías**, y la inferencia mira el DATO en vez del nombre:

| categoría | qué es | regla de λ |
|---|---|---|
| `price_index` | base convencional, sin cero natural | **λ=0 siempre** |
| `multiplicative` | magnitud positiva que se mueve en proporción | λ=0 **por defecto**, revocable por el dato |
| `ratio` | participación acotada | λ=0 por defecto; la logit sería la correcta y no está |
| `generic` | lo demás | decide el estadístico |

```python
if domain == "price_index":
    return 0.0
if domain in ("multiplicative", "ratio") and abs(gap) < BANDA_AMBIGUA_BOXCOX:
    return 0.0
return 0.0 if gap >= 0 else 1.0
```

**El interruptor es la banda en que el estadístico no discrimina**, y es la misma
que art ya imprime al analista (*«Δcorr=0.024 < 0.10 → decisión ambigua»*).
Dentro de ella manda el dominio; fuera, manda el dato. Eso da la propiedad que
hace el arreglo seguro: **el dominio sólo decide donde el estadístico no dice
nada**, así que una clasificación equivocada cuesta poco.

Y hay una asimetría deliberada entre `price_index` y las otras dos: el índice es
regla **absoluta** porque su nivel es una convención y un modelo en niveles no
tiene escala interpretable; un precio sí tiene escala, así que su log es un
**punto de partida** que el dato puede desmentir.

### La inferencia deja de depender del nombre

El docstring anterior se quejaba de su propia implementación: *«un modelo no debe
salir distinto porque el fichero se llamara IPC_ES en vez de serie3»*. Ahora:

* valores no positivos ⇒ `generic` (el log no está definido);
* todo dentro de (0,1) ⇒ `ratio`;
* recorrido máx/mín ≥ **3.0** ⇒ `multiplicative`. El umbral es una convención y
  ésta es su razón: sobre un recorrido de factor R, un modelo de varianza aditiva
  afirma que la innovación tiene la misma magnitud absoluta en los dos extremos.
  Con R ≥ 3 eso es implausible para una magnitud económica positiva — en PGAS
  serían los mismos USD/t de sorpresa a 95 que a 500.

El nombre se conserva **sólo para los índices**, y no por pereza: un índice no
tiene firma en el dato que lo distinga de cualquier otra magnitud positiva, ya
que lo que lo define es que su nivel es convencional, y eso no se ve en la serie.
Se añadieron los prefijos de tipo de cambio efectivo (`itcer`, `tcer`, `reer`,
`neer`), que son índices y no estaban.

### Y se ANUNCIA

El docstring prometía *«recorded and announced, never applied in silence»* y no
se imprimía. `build_model` saca ahora la línea, con quién decidió:

```
**Dominio:** magnitud multiplicativa  (inferido; lo declarado gana — `domain=…`)
**λ:** log (λ=0)  (gap=-0.024 · decide el dominio)
```

## Lo que el arreglo NO resuelve, y conviene saberlo

Corregida la λ de PGAS, **el carril por lotes falla ahora en el nodo siguiente**:
toma `d=0`, que es lo que recomienda la tabla ADF/KPSS y contra lo que fueron los
tres analistas humanos/LLM que miraron la serie. El instrumento que dictamina esa
cuestión —el DCD de sobrediferenciación sobre el modelo estimado— existe, pero el
bucle de rondas no lo consulta: sólo sabe añadir intervenciones.

Es el mismo patrón de fondo, por sexta vez: **una decisión que el motor sabe
contrastar y el bucle no tiene por dónde revisar.** Queda anotado en TODO.md.
