---
id: BUG-0207
title: El guion del carril guiado no se escribe solo — la identificación no deja nodos, el veredicto de Q(39) aprueba lo que la Q(12) rechaza, lo que ve la diagnosis no llega a la versión, el padre de una alternativa se infiere mal y no se puede adoptar
status: fixed
severity: high
component: guion
found_in: 0.2.3.dev0 @a33b893
fixed_in: 0.2.3.dev0
reported: 2026-10-06
reporter: David / Claude — P04 de Econometría Aplicada (UCM), el IPC de España en modo guiado, preparando la clase sobre cómo se escribe un guion
tags:
  - guion
  - docencia
  - carril-guiado
  - linaje
  - diagnosis
references:
  - src/art/mcp_server.py:4982 (guided_identification — sin guion_path)
  - src/art/mcp_server.py:6154 (_record_to_guion — parent_origen «inferido» sin base_pre_path)
  - src/art/mcp_server.py:6822 (record_version — no toca status)
  - src/art/mcp_server.py:7151-7162 (guion_map — aviso de instrumento)
  - src/art/guion.py:253 (status exploring | adopted | dead-end; «adopted» no lo escribe nadie)
  - src/art/guion.py:1178 (q_pass = diag_result.white_noise)
  - bugs/BUG-0207-repro/repro.py
  - bugs/BUG-0207-repro/ES_CPI_guion_aula.json (el guion real de la clase)
  - BUG-0108, BUG-0176 (linaje, ya corregidos en estimate_and_diagnose y en la reinscripción)
---

## Summary

En docencia el guion **es el producto**: el alumno aprende el método escribiendo
cada decisión con su evidencia, lo descartado y la razón. Al recorrer en modo
guiado el IPC nacional de España (2002:01-2019:12) para enseñar cómo se escribe,
el guion que art deja solo está incompleto y, en dos puntos, dice lo contrario
de lo que pasó. Siete defectos, los siete reproducidos:

| | Defecto | Efecto |
|---|---|---|
| D1 | `guided_identification` no admite `guion_path` | λ, d, la estacionalidad y los órdenes —todo lo que se decide antes del primer modelo— no quedan en el guion. Hubo que escribir cada nodo a mano con `guion_node` |
| D2 | `criterio="dominio"` exige un nodo `dominio` previo, pero el flujo guiado nunca lo pide ni lo crea | el primer nodo que se intenta escribir con el criterio de dominio se rechaza. La regla es buena (unas expectativas declaradas después no son un criterio); falta que el flujo la ponga al principio |
| D3 | `q_pass` lo decide sólo la Q(39) | m01, (0,1,0)(0,1,1)₁₂, sale **APROBADO** y el mapa lo pinta **Q✓** con r₁ = 0,38 en los residuos y Q(12) p = 0,0003, Q(24) p = 0,006. La salida en pantalla lo advierte («salvedad»), pero la conclusión dice «el modelo se sostiene… adoptar» y el guion sólo guarda el ✓. Sigue pintado Q✓ después de abandonarlo por eso |
| D4 | Lo que ve la diagnosis no llega a `problems_found` de su versión, y no hay herramienta para anotar una versión ya registrada | los problemas de m01 sólo se pudieron escribir en la versión siguiente (`guion_problems` de m02) o en un nodo: la ficha de m01 queda sin ellos |
| D5 | En `confirm_and_estimate` modo nuevo, el padre se infiere como la última entrada y no se puede declarar (`base_pre_path` cambia a modo incremental) | dos sobreparametrizaciones seguidas de m02: m04 queda colgando de m03. Al abandonar m03, la cascada se habría llevado a m04 (hubo que usar `cascade=False`) |
| D6 | No hay forma de **adoptar** | `status="adopted"` existe en el modelo de datos y ninguna herramienta lo escribe. La vía que la propia salida propone, `record_version(decision="adoptado")`, crea una entrada duplicada con `status="exploring"`: el mapa nunca enseña un ✓ |
| D7 | `guion_map` avisa «No todo se calculó con el mismo instrumento» por los **nodos** | cuenta como «sin registrar» cada entrada sin `instrumento`, y los nodos no se calculan. En un guion bien escrito (muchos nodos) el aviso sale siempre y deja de significar nada |

## Impact

Alto para docencia, que es donde el guion importa más: el guion es lo que se
enseña a escribir y lo que se evalúa. Con estos defectos, un alumno que confía en
lo que art registra solo entrega un guion que empieza en el primer modelo (D1),
que da por bueno un modelo con la parte regular sin modelar (D3), sin la razón de
cada callejón en su sitio (D4), con un árbol falso (D5) y sin modelo adoptado
(D6). Los guiones del curso 2026-27 hechos antes de este análisis (airline, HICP
de España, Salamanca, IPC de EE. UU.) tienen exactamente esa forma: versiones con
una línea de «decisión», sin nodos, sin razones y sin adoptado.

## Reproduction

`bugs/BUG-0207-repro/repro.py` hace el recorrido de la clase llamando a las
herramientas MCP como funciones, en un directorio temporal, y comprueba cada
defecto con un `assert` que pasa mientras el defecto exista:

```
D1 ✗  guided_identification (λ, d, D, órdenes) no deja nada en el guion: no admite guion_path
D2 ✗  criterio='dominio' exige un nodo 'dominio' previo, y el flujo guiado nunca lo pide ni lo crea
D3 ✗  m01: q_pass=True (lo decide Q(39)) con Q(12) p=0.0003; el mapa lo pinta Q✓
D4 ✗  problems_found de m01 queda vacío; y no hay herramienta para anotarlo después
D5 ✗  m04 (sale de m02, v4) queda con parent=v5 (m03); en modo nuevo no se puede declarar el padre
D6 ✗  'adoptar' = una entrada nueva duplicada (status='exploring'); nunca sale ✓ en el mapa
D7 ✗  guion_map: «No todo se calculó con el mismo instrumento» por los NODOS, que no se calculan
```

`ES_CPI_guion_aula.json` es el guion real de la clase, escrito a mano donde art
no llega: 5 nodos de identificación, m01 abandonado, m02 adoptado (v11, duplicado
y en «exploring»), m03 y m04 abandonados (m04 con el padre equivocado) y un nodo
de previsión con el seguimiento del SPS en 2020-2021.

## Root cause

- D1: `guided_identification` (mcp_server.py:4982) no recibe `guion_path`; los
  nodos sólo existen vía `guion_node`.
- D2: la validación del criterio está en `guion_node`; nada en el flujo guiado
  (Call 1) ofrece el nodo `dominio`, aunque `domain=` ya se declara ahí.
- D3: `q_pass = diag_result.white_noise` (guion.py:1178), que es el veredicto en
  el retardo 3s+3. Los p-valores en 12/24/36 se guardan, pero ni el veredicto ni
  el mapa los usan.
- D4: `_record_to_guion` sólo escribe `problems_found` si se le pasa; la
  diagnosis no lo rellena con sus propios hallazgos (retardos que rechazan, media
  residual, anómalos), y no hay `guion_update`/`guion_annotate`.
- D5: `parent_origen = "declarado" if base_pre_path else "inferido"`
  (mcp_server.py:6211); en `confirm_and_estimate` `base_pre_path` significa
  «modo incremental», no «de dónde sale». Es BUG-0108 en la otra herramienta.
- D6: `status` sólo se cambia a `dead-end` (guion.py:614); nadie escribe
  `adopted`.
- D7: `sin = [e.version for e in g.entries if not e.instrumento]`
  (mcp_server.py:7158) no filtra `kind == "node"`.

## Fix

Propuesto, por orden de importancia para docencia:

1. **D1 + D2.** `guided_identification(…, guion_path=…)`: cada Call escribe su
   nodo (λ, d, estacionalidad, órdenes) con la evidencia que acaba de mostrar y
   la propuesta de la herramienta, a la espera de que el analista la confirme o
   la corrija (el campo `coincide` ya existe). La Call 1 crea el nodo `dominio`
   con las expectativas, o las pide si faltan.
2. **D6.** `guion_adopt(guion_path, version, why)` —simétrico de
   `guion_abandon`—, que marca `status="adopted"` sin duplicar, y deja al resto
   de hermanos «explorando» o pide abandonarlos.
3. **D3.** El veredicto de ruido blanco no puede ser sólo Q(3s+3): basta con que
   rechace la Q en s o en 2s para que `q_pass` sea False (o un tercer estado,
   «pasa con salvedad»), y el mapa lo pinte así.
4. **D4.** La diagnosis escribe sus hallazgos en `problems_found` de su versión;
   y `guion_annotate(guion_path, version, campo, texto)` para lo que el analista
   añada después.
5. **D5.** Un `parent=` explícito en `confirm_and_estimate` (y en
   `record_version`), separado de `base_pre_path`.
6. **D7.** Excluir los nodos del recuento del aviso de instrumento.

## Validation

`repro.py` invertido: cada `assert` debe fallar —con su mensaje «resuelto»— una
vez corregido el defecto correspondiente; y el guion del recorrido debe salir con
nodos desde λ, m01 con Q en salvedad y sus problemas, m04 colgando de m02 y m02
marcado ✓ sin duplicar.

## Resolution (2026-10-06)

**Fix.** Los siete defectos:

- **D1/D2.** `guided_identification(…, guion_path=…)`: cada llamada deja el nodo que
  enseña (λ, d, estacionalidad, órdenes) PENDIENTE, con la propuesta de la
  herramienta y su evidencia (gap y correlaciones; ADF/KPSS; F-HAC; los tres
  primeros candidatos). La llamada siguiente —que trae el valor elegido, con
  `razon=`— lo cierra y fija `coincide` comparando VALORES. `confirm_and_estimate`
  cierra los nodos pendientes (los órdenes sobre todo) antes de escribir el modelo,
  que cuelga del nodo de órdenes. La llamada 1 escribe el nodo `dominio` con
  `domain` + `expectativas`, o las pide; después `criterio="dominio"` se admite.
- **D3.** Tercer estado «pasa con salvedad» (`guion.q_estado`/`q_marca`, derivado de
  los p-valores guardados, así que vale también para guiones ya escritos): el mapa
  pinta `Q⚠(12,24)`, el HTML `✓⚠`, y la conclusión dice «se sostiene con
  SALVEDAD… no lo adoptes sin haberlo mirado»; la alternativa ya no es «adoptar».
  `q_pass` sigue siendo el veredicto del cancerbero 3s+3 (decisión del
  11-sep-2026).
- **D4.** La diagnosis escribe sus hallazgos en `problems_found` de su versión
  (`[diagnosis] …`: rechazo o salvedad de la Q con retardos y p, JB, media residual,
  estacionalidad residual, anómalos por encima del umbral calibrado), detrás de lo
  que escriba el analista. `guion_annotate(guion_path, version, campo, texto)`
  AÑADE en una línea fechada, sin pisar.
- **D5.** `parent=` en `confirm_and_estimate` y `record_version`, separado de
  `base_pre_path`; un padre inferido se dice como tal en la salida.
- **D6.** `guion_adopt(guion_path, version, why)` marca `status="adopted"` con
  `why_adopted`, sin crear entrada, y lista los modelos que siguen en exploración.
  `record_version(decision="adoptado")` sobre un `.pre` ya registrado adopta esa
  entrada en vez de duplicarla.
- **D7.** El aviso de instrumento de `guion_map` no cuenta los nodos.

Sobre ES_CPI el recorrido sale con nodos desde λ, m01 en `Q⚠(12,24)` y con sus
problemas, m04 colgando de m02 (`parent=`) y m02 marcado ✓ sin duplicar.

**Validation:** `tests/test_bug_0207_el_guion_del_carril_guiado.py` (12 pruebas, una
o más por defecto, sobre un índice sintético y guiones construidos a mano).
