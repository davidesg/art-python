---
id: BUG-0032
title: the autonomous lane records the DESTINATION, not the PATH — build_model writes one guion entry per RUN while the round loop estimates and diagnoses one model per ROUND, so guion_map draws a one-node map for a multi-step search
status: fixed
severity: high
component: mcp-tools
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-27
reporter: David / réplica TFM Bolivia
tags:
  - guion
  - autonomous
  - documentation
references:
  - src/art/mcp_server.py (build_model, bloque del guion)
  - src/art/mcp_server.py (_round_decision_text, _round_problems_text)
  - src/art/pipeline.py (RoundResult — el camino ya estaba en memoria)
  - docs/ARCHITECTURE_REVIEW.md §5.1 (el guion como mapa)
  - bugs/BUG-0032-repro/repro.py
  - tests/test_bug_0032_autonomous_guion_records_the_path.py
---

## Summary

`build_model` corre un bucle de rondas. Cada vuelta **estima** un modelo, lo
**diagnostica**, y decide **desde esa diagnosis** qué intervención añadir antes
de volver a estimar. Los modelos y sus diagnosis quedan en `result.rounds`.

Al terminar, escribía **una** entrada en el guion: la del modelo final.

```python
guion_note = ""
if m_fit is not None:
    try:
        guion_note = _record_to_guion(
            model=m_fit, inp_path=output_path, lam=lam, ...)   # UNA. La última.
```

`guion_map` dibujaba entonces **un nodo para una búsqueda de tres pasos**:

```
## Mapa del análisis — RATIO
└─ · v1 auto  logL=-244.71  Q✗ JB✓  ← Corrida autonoma …
```

cuando la corrida había sido:

```
Ronda 1:  JB ✗ JB=30.4   extremos: 1  → Añadidas: PULSE obs 66
Ronda 2:  Q ✗ lags 8,12  extremos: 1  → Añadidas: PULSE obs 20
Ronda 3:  Q ✗ lags 4,8,12               (para: sin nuevos)
```

## Por qué importa, y no es contabilidad

El comentario que había justo encima del código decía ya lo correcto —*«El
carril autónomo documenta TAMBIÉN, y con más motivo: aquí no hay analista que
note el callejón»*— y el código documentaba la corrida, no el camino.

**Lo que se pierde no es el modelo intermedio.** Ese se descarta a propósito: un
callejón sin salida es el método funcionando, no fallando. Lo que se pierde es
la **razón** de haber pasado al siguiente, que es lo único que impide volver a
probar la misma rama. Un mapa con nodos y sin aristas no dice por dónde se fue.

Y es exactamente la pregunta que el guion existe para contestar. Comparando los
dos carriles sobre RATIO —el guiado llega a `AR(1)₄ + escalón@2008:4`, el
autónomo a `AR(1)₄ + impulso@2008:4` y dos MA irrelevantes— la pregunta natural
es *en qué ronda se torció*. El guion del autónomo no podía contestarla.

## El corolario de ficheros

`output_path` se **reescribe en cada vuelta**. Una entrada intermedia que
apuntase ahí describiría un modelo que ese fichero ya no contiene: un registro
**falso**, no meramente incompleto. Es el mismo fallo que obligó a borrar dos
guiones de la réplica cuando el servidor MCP servía código obsoleto.

Por eso cada ronda escribe **su propio `.pre`** (`…_r1.pre`, `…_r2.pre`), que es
el convenio ya existente: un `.pre` es el óptimo en forma reejecutable, y el
invariante es comprobable — el test carga cada fichero, lo reestima y exige que
la verosimilitud coincida con la que la entrada afirma.

## Repro

`bugs/BUG-0032-repro/repro.py` — serie trimestral I(1) de 100 observaciones con
dos impulsos grandes y separados (semilla fija), que obliga al bucle a dar más
de una vuelta:

```
rondas que dio el bucle: 2
  ronda 1: extremos=2  añade=[PULSE obs 31, PULSE obs 71]  motivo_parada=—
  ronda 2: extremos=1  añade=[—]                           motivo_parada=no_new

modelos que el bucle estimó y diagnosticó: 2
entradas que el guion recibía (antes del arreglo): 1
```

## Fix

Una entrada por ronda, encadenadas, cada una apuntando a su propio fichero:

```python
for rd in result.rounds:
    es_ultima = (rd.round_num == ultima_ronda)
    if es_ultima:
        ruta, nombre = output_path, guion_name
        decision_txt = guion_decision or _round_decision_text(rd)
    else:
        ruta = f"{stem}_r{rd.round_num}.pre"
        rd.model.write_pre(ruta)
        nombre = f"{guion_name}-r{rd.round_num}" if guion_name else f"r{rd.round_num}"
        decision_txt = _round_decision_text(rd)
    guion_note = _record_to_guion(
        model=rd.model, inp_path=ruta, lam=lam, guion_path=gpath,
        name=nombre, decision=decision_txt,
        problems_found=_round_problems_text(rd), ...)
```

El encadenamiento sale gratis: `infer_parent` ya toma la última versión
registrada como padre cuando no se encadena desde un `.pre` explícito.

Dos ayudantes nuevos ponen la arista en palabras:

- `_round_decision_text(rd)` — *«Ronda 2: la diagnosis marca 1 extremo(s) → se
  añade PULSE obs 20.»*, o el motivo de parada (`clean` / `no_new`).
- `_round_problems_text(rd)` — *«Q rechaza en los retardos 8, 12 (p-mín=0.0040)
  · extremos: obs 19 (z=+3.54)»*.

RATIO, después:

```
v1 auto-r1  padre=None  RATIO_auto_r1.pre
   decision : Ronda 1: la diagnosis marca 1 extremo(s) → se añade PULSE obs 66.
   problemas: JB=30.4 (p=0.0000) · extremos: obs 65 (z=+3.99)
v2 auto-r2  padre=1     RATIO_auto_r2.pre
   decision : Ronda 2: la diagnosis marca 1 extremo(s) → se añade PULSE obs 20.
   problemas: Q rechaza en los retardos 8, 12 (p-mín=0.0040) · extremos: obs 19 (z=+3.54)
v3 auto     padre=2     RATIO_auto.inp
   problemas: Q rechaza en los retardos 4, 8, 12 (p-mín=0.0026)
```

## Lo que NO arregla — y es la otra mitad, medida

El carril **guiado** tiene el mismo agujero por otra vía: hay herramientas que
estiman y no añaden línea al guion. Medido sobre la réplica:

| serie | modelos en disco | entradas en el guion |
|---|---|---|
| ITCER | m00, m10, m20 | m00, m20 — **falta m10** |
| PGAS | m10, m20 | m10, m20 — completo |
| RATIO | m00, m10, m20, m30, m31 | m00, m10 — **faltan m20, m30, m31** |

En RATIO faltan justo los modelos donde se deciden las intervenciones, que es
donde diverge del autónomo. Sólo `confirm_and_estimate` y `build_model` escriben
guion (`_record_to_guion` tiene 4 llamadas en todo el servidor); el resto de
caminos que producen un modelo estimado no.

Va aparte porque el arreglo es distinto: aquí bastaba recorrer una lista que ya
existía; allí hay que decidir qué herramientas son «producir un modelo» y cuáles
son mirar, y cablearlas todas. Anotado en TODO.md.
