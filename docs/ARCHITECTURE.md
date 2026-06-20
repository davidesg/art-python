# Arquitectura de la suite ART / FUE / FUG / FUF

> Documento de visión arquitectónica. Captura la separación de capas, la
> filosofía **evidencia vs criterio**, los dos modos de operación, y el plan
> de refactor para **unificar la orquestación**.
> Redactado jun-2026 tras la revisión crítica de la suite.

---

## 1. Propósito de la suite

Construcción de modelos univariantes siguiendo la metodología
**Box-Jenkins-Treadway (BJT)**: un proceso **iterativo** que usa herramientas
gráficas y contrastes para tomar decisiones, construyendo el modelo paso a paso
mediante identificación parcial hasta obtener un modelo definitivo, listo para
usarse (estimación + previsión).

La limitación intrínseca del proceso BJT es que **requiere criterio**: las
decisiones (empíricas o teóricas) no son arbitrarias. Quien aporta ese criterio
es **Claude**, alimentado por la evidencia que produce la suite.

Esto es el núcleo de una **falsa simplicidad**: los modelos ARMA son simples,
pero el proceso iterativo de construcción funcionaba de maravilla sobre todo si
eras Box, Jenkins o uno de sus discípulos. La dificultad real es entrenar al
analista en unas decisiones muchas veces heurísticas; la IA hace aquí, con sus
limitaciones, el papel de ese analista entrenado. Nótese además que el análisis
**no es el canónico de Box y
Jenkins**, sino la versión con extensiones de **Arthur B. Treadway** (discípulo
de Gwilym Jenkins), con elementos y heurísticos procedentes de su trabajo en los
Servicios de Previsión y Seguimiento (SPS) de la economía española.

**Principio de diseño (regla de medida):** la previsión es uno de los objetivos
del modelo ARMAX —quizá imbatible en previsión—, pero el modelo univariante es
además la base de un análisis de relaciones más sofisticado. Por eso estos
modelos univariantes deben ser la **regla de medida** de modelos más complejos:
si un modelo sofisticado no mejora sus previsiones, tiene algún problema y debe
repensarse.

---

## 2. Componentes y fronteras

| Componente | Rol | Naturaleza |
|------------|-----|-----------|
| **FUE** (`atws/fue`) | Estimación ML exacta + **forecasting (FUF)** + diagnósticos de bajo nivel | Python sobre `_fue_engine.so` (C) |
| **FUG / pyfug** (`atws/fug/pyfug`) | Gráficos de alta definición para análisis de series temporales | Python + matplotlib |
| **ART** (`art-python/src/art`) | Orquestación + adaptación semántica + audit trail | Python |
| **ART MCP** (`mcp_server.py`) | Superficie de 32 herramientas hacia Claude | FastMCP |
| **Claude** | **Criterio**: identificación, interpretación, decisiones | LLM |

**FUF no es un componente par.** En la suite Python el forecasting vive *dentro*
de FUE (`load_fuf`, `forecast_fuf`, `write_fuf`, `fuf_cli.py`,
`report_forecast.py`). Es una **capacidad de FUE** aguas abajo del modelo
terminado. Los `atws/fuf/fuf-*` son el legado C/GTK.

---

## 3. Capas (sin ciclos)

```
CLAUDE — criterio (empírico/teórico)
  guiado:   sugiere → el analista decide
  autónomo: decide todo → presenta modelo final
   │  protocolo MCP + instrucciones del servidor
ART MCP  (mcp_server.py · 32 tools)
   │
ART describe.py  ── ADAPTADOR SEMÁNTICO
   │  Description{summary, figure_b64, recommendation, data}
   │  convierte números/gráficos en evidencia legible por LLM
   ├──────────────────────────────┐
ART análisis                     (describe.py y mcp_server.py
  identification                   son los únicos que importan pyfug)
  seasonal_detection
  model_detection · interventions
  formal_tests · diagnosis · guion
   │                                │
FUE (estimación + FUF)            FUG / pyfug (gráficos)
   │
_fue_engine.so (C)
```

Invariantes verificados: el grafo no tiene ciclos; solo `describe.py` y
`mcp_server.py` conocen pyfug; FUE es la base numérica transversal.

**`describe.py` es el acierto central**: el adaptador que hace que los motores
numéricos «hablen Claude». Es la abstracción correcta y debe preservarse.

---

## 4. Filosofía: evidencia ≠ criterio

La frontera que el diseño debe respetar:

- **Evidencia** (determinista, reproducible): motores + módulos de análisis.
- **Presentación de la evidencia**: `describe.py` (`summary` + `figure_b64` + `data`).
- **Criterio**: Claude, vía el protocolo MCP.
- **Registro de decisiones** (audit trail BJT): `guion.py` → `guion.json`.

**Tensión detectada:** el criterio se filtra hacia la capa de evidencia. El
campo `Description.recommendation` lo calcula ART con heurísticas cableadas
(p. ej. «Decisión B1 por defecto»), de modo que hay **dos jueces simultáneos**
—las heurísticas de ART y Claude— que pueden contradecirse y que **anclan** a
Claude y al analista antes de que razonen.

Regla de diseño objetivo: la capa de evidencia emite **evidencia + el menú de
decisiones posibles con argumentos a favor/en contra**, no sentencias. El cierre
del criterio lo pone Claude (guiado: propone; autónomo: decide).

---

## 5. Los dos modos

| | Guiado (analista + Claude) | Autónomo (solo Claude) |
|---|---|---|
| Quién decide | El analista, con sugerencias de Claude | Claude |
| Salida | Iterativa, con confirmación en cada etapa | Un modelo final |
| Camino actual | `guided_identification` → `confirm_and_estimate` → `suggest_intervention_form` → `confirm_and_estimate(base_pre_path)` → `formal_tests` | `build_model` / `batch_build` (monolito) |

### Problema estructural: DOBLE ORQUESTACIÓN

El modo autónomo **no conduce las mismas herramientas que conduciría Claude**:
las *reimplementa* en un monolito. `build_model` (mcp_server.py:2735-2932) toma
seis decisiones inline que en guiado toma Claude leyendo los `describe_*`:

| Decisión | En `build_model` (autónomo) | En guiado |
|----------|------------------------------|-----------|
| λ | `0.0 if bc.data["gap"] >= 0 else 1.0` | Claude lee `describe_boxcox` |
| d | `urt.data["recommended_d"]` | Claude lee `describe_unit_root` |
| D, decisión | `seas.data` | Claude lee `describe_seasonality` |
| nº armónicos | `freq//2-1 if decision!="A" else 0` | Claude / `confirm_and_estimate` |
| p, q | `suggest_orders(...)[0]` | Claude lee `describe_identification` |
| Intervención | lazo `z>3.0` + step-si-consecutivo-si-no-pulse | `suggest_intervention_form` (umbral 2.5) |

**Consecuencia probada de la deriva:** `batch_build` tenía `d=1` cableado
mientras `build_model` llamaba bien a `describe_unit_root` — el clásico bug de
mantener dos implementaciones del mismo método. Además contradice la filosofía:
en el autónomo «decide Claude», pero en realidad decide un heurístico fijo en
código.

---

## 6. Plan de refactor: unificar la orquestación

**Objetivo:** una sola fuente de verdad por decisión y por paso de ejecución.
El autónomo pasa a ser «Claude/ política por defecto ejecutando la MISMA
secuencia guiada sin pausas de confirmación».

### Arquitectura objetivo: tres capas separadas

```
art/policy.py    ← REGLAS DE DECISIÓN (un único hogar). Funciones puras:
                   decide_lambda(bc_data)                  -> float
                   decide_differencing(seas_data, urt_data)-> (d, D, decision, n_harm)
                   decide_orders(specs)                    -> (p, q, P, Q)
                   decide_interventions(diag, existing)    -> list[(at, form)]
                   should_stop(diag)                       -> bool
                   THRESHOLDS = {...}   # 2.0/2.5/3.0/3.5 en un solo sitio

art/pipeline.py  ← PASOS DE EJECUCIÓN (un único hogar). Mecanismo puro:
                   build_and_fit(ts, spec)        -> (model, diag)
                       # envuelve _make_model + _write_inp + _load_fitted + diagnose
                   outlier_round(ts, spec, diag)  -> spec'
                   run_full(ts, policy)           -> PipelineResult

mcp_server.py    ← TOOLS DELGADAS sobre pipeline + policy:
                   build_model          = pipeline.run_full(ts, DefaultPolicy())
                   batch_build          = bucle de run_full
                   confirm_and_estimate = pipeline.build_and_fit(ts, spec_de_claude)
                   guided_*             = describe_* + policy.decide_* COMO SUGERENCIA
```

**Principio clave:** las funciones de `policy` son el único hogar de cada regla
de decisión. En guiado se exponen como *sugerencia* (Claude puede sobrescribir);
en autónomo se aplican. Misma regla, dos formas de consumo, **cero deriva**.

### Fases (cada una entregable y verificable por separado)

**Fase 0 — Red de seguridad.**
Tests de caracterización: capturar la salida actual de `build_model` y
`confirm_and_estimate` sobre series fixture (golden output). El refactor debe
preservar el comportamiento del modo autónomo.

**Fase 1 — Extraer `policy.py`.**
Mover las seis decisiones inline de `build_model` a funciones puras.
`build_model` las llama (sin cambio de comportamiento). Los tools guiados
empiezan a exponer `policy.decide_*` en su campo `recommendation`, sustituyendo
las recomendaciones cableadas/dispersas (p. ej. «Decisión B1 por defecto»).
→ Resuelve §4 (criterio filtrado): se centraliza Y se hace sobrescribible.

**Fase 2 — Extraer `pipeline.py`.**
Mover `_make_model`+`_write_inp`+`_load_fitted`+`diagnose` a `build_and_fit`, y
el lazo de outliers a `run_full`. `build_model` queda en ~15 líneas:
`result = run_full(ts, DefaultPolicy()); return render(result)`.
`confirm_and_estimate` reutiliza `build_and_fit`. `batch_build` itera `run_full`.
→ Elimina la duplicación `_make_model`-loop vs tools guiados.

**Fase 3 — Unificar la lógica de intervención.**
La heurística step/pulse existe en `build_model` (inline) y en
`suggest_intervention_form` (umbral 2.5). Mover a `policy.decide_interventions`.
Guiado y autónomo pasan a usar la regla idéntica.

**Fase 4 — Policy como objeto intercambiable.**
`DefaultPolicy` (heurísticas) vs `ClaudePolicy` (delega en Claude). Autónomo =
`DefaultPolicy`. Hace explícita la filosofía en código: el autónomo es «la
política heurística por defecto», y queda la puerta abierta a que las elecciones
de Claude realimenten como política.

**Fase 5 — Limpieza.**
Borrar duplicación muerta, alinear umbrales a `policy.THRESHOLDS`, retirar los
caminos divergentes.

### Estado de implementación (jun-2026)

| Fase | Estado | Resultado |
|------|--------|-----------|
| 0 | ✅ | `tests/test_golden_pipeline.py` + fixture congelada; red de seguridad |
| 1 | ✅ | `art/policy.py` — funciones puras de decisión + `THRESHOLDS` |
| 2 | ✅ | `art/pipeline.py` — primitivos de ejecución + `build_and_fit` + `run_full`; `build_model`/`batch_build` comparten el lazo |
| 3 | ✅ | `policy.decide_form` único; umbrales de intervención desde `THRESHOLDS` |
| 4 | ✅ | `Policy`/`DefaultPolicy`/`ClaudePolicy`; `run_full(decision_policy=…)` |
| 5 | ✅ | umbrales user-facing → `THRESHOLDS["outlier_user"]`; eliminados `_param_table`/`_param_names` muertos |

Comportamiento preservado en todas las fases (golden verde). Cero regresiones
netas frente al baseline `af2ba9b` (los fallos restantes del suite son
pre-existentes: nlags en series cortas, tolerancias Chile, npar trimestral).

**Cierre de la unificación (hecho):** `build_model` es ahora el único motor en
ambos modos. Sin spec → `DefaultPolicy` (autónomo). Con spec confirmada
(`lam/d/D/p/q/n_harmonics/decision`) → `ClaudePolicy`, que honra lo que el
analista fijó y deja el resto a la heurística, conduciendo el mismo
`run_full`. «Autónomo» y «guiado» son literalmente el mismo camino con distinto
«quién confirma». Para confirmación outlier-a-outlier sigue disponible el flujo
`confirm_and_estimate` + `suggest_intervention_form`.

### Riesgo y verificación

- **Riesgo principal:** la salida de `build_model` puede cambiar si una decisión
  inline no era exactamente equivalente a la nueva función de `policy`. Mitigado
  por los golden tests de la Fase 0.
- **Verificación por fase:** los golden tests deben pasar tras cada fase
  (comportamiento preservado) salvo cambios deliberados documentados.
- **Secuencia:** cada fase es independiente y desplegable; no hay big-bang.

### Estado del contrato `data` (relacionado)

`Description.data` es un `dict` no tipado con defaults mágicos
(`data.get("recommended_d", 1)`). Ahí se escondió el bug del `d=1` cableado.
Recomendación complementaria al refactor: tipar `data` por etapa
(`SeasonalityData`, `UnitRootData`, …) o eliminar los defaults mágicos para que
una clave ausente sea error explícito.

---

## 7. Deuda arquitectónica residual (fuera del refactor de orquestación)

| Tema | Severidad | Nota |
|------|-----------|------|
| Frontera FUF con atributos privados (`_fuf_*`) | Baja-media | Falta un `ForecastSpec` explícito |
| Estado partido: `.inp`/`.pre` vs `guion.json` | Media | `guion.json` debería ser la fuente de verdad |
| `_write_inp` duplica el conocimiento de formato de FUE | Media | Sin sello de versión en el header `.inp` |
| Gráficos partidos: pyfug vs `fue.plots` | Baja | pyfug debería ser dueño de toda la gráfica |

---

## 8. Qué preservar

- `describe.py` como **adaptador semántico** (motores → evidencia conversable).
- El **grafo de dependencias sin ciclos** y la separación FUE(números) /
  pyfug(gráficos).
- `guion` como **audit trail** del proceso iterativo BJT.
- La distinción guiado/autónomo — pero implementada como **un solo camino de
  orquestación** con distinto «quién confirma».
