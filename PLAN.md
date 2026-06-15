# ART Python — Plan de trabajo

API de análisis de series temporales que implementa la metodología
Box-Jenkins-Treadway (5 etapas) sobre el motor de estimación `fue`.

---

## Filosofía de uso: proceso iterativo con criterio del analista

Box-Jenkins-Treadway **no es un pipeline de un solo bloque**. Es un proceso
iterativo donde el analista toma decisiones en puntos clave, observa resultados
y ajusta. Claude puede añadir valor como soporte de criterio para analistas
noveles, explicando el porqué de cada recomendación y permitiendo la discusión.

Hay dos modos de uso previstos:

### Modo guiado (interactivo)

El analista itera con Claude en cada decisión. Claude presenta la evidencia,
da una recomendación con razonamiento, y el analista confirma, modifica o pide
alternativas. Siempre que se estima un modelo, se muestran automáticamente los
residuos y los estadísticos de diagnosis.

```
Etapa 1 — Identificación (tres sub-decisiones, cada una iterativa):
  1a. λ (Box-Cox): figura + correlación media-std → recomendación + justificación
  1b. d y D (o d + armónicos): HAC F-test + ACF/PACF en niveles → recomendación
  1c. p, q [P, Q]: ACF/PACF diferenciada + sugerencias top-N → el analista elige

Etapa 2 — Estimación (no iterativa):
  → Siempre muestra inmediatamente: residuos tipificados, ACF/PACF residuos,
    Q-test, JB, tabla de parámetros con SE y t-stats.

Etapa 3 — Diagnosis (iterativa):
  → Si no pasa: Claude explica qué falla y qué opciones hay (más ARMA, MEG,
    intervenciones). El analista decide la siguiente acción.

Etapa 4 — Contrastes formales + Intervenciones:
  → DCD, MEG: Claude interpreta el resultado y recomienda si reformular.
  → Outliers: Claude detecta las fechas y sugiere la forma funcional
    (pulse/step/ramp) basándose en el contexto económico; analista confirma.

Etapa 5 — Empleo: fuera del alcance de art (lo gestiona fue).
```

### Modo autónomo

El sistema construye el modelo sin intervención humana usando heurísticas B-J:
auto-selección de λ, d, D, p, q, P, Q; estimación; detección e incorporación
automática de intervenciones; iteración hasta diagnosis limpia o límite de
rondas. Útil para análisis masivos o como punto de partida para el modo guiado.

---

## Estado jun-2026 — Síntesis y plan de prioridades

### Lo que funciona (infraestructura consolidada)

| Componente | Estado | Notas |
|-----------|--------|-------|
| **pyfug** graphics | ✅ estable | plot_combined, plot_acf_pacf, plot_histogram, plot_mean_deviation_pair |
| **fue** estimación | ✅ estable | Model, write_pre, load, Intervention; `at=` **0-based** |
| `model_equation` (Unicode) | ✅ — bug fix | Ecuación (2): ∇ ahora dentro: `(1−φB)(∇Nₜ−μ)=aₜ` |
| `describe_prelim_scan` + contrib. ACF | ✅ | Bloques E + N implementados |
| `detect_seasonality` / `plot_seasonality` | ✅ | HAC F-test, gráfico efectos mensuales |
| ADF / KPSS | ✅ | Embebidos en identify; exponer como tool dedicada (Bloque L) |
| Sistema `cases/SERIE/SERIE_mNN.pre` | ✅ | Flujo `write_pre` → `load` → modificar → estimar |
| `CHANGELOG.md` por caso | ✅ | Convención mNN documentada en cases/IPC_ES/ |

### Lecciones del análisis IPC_ES (jun-2026)

1. **Flujo BJ-T completo** (λ → d → B1/B2 → intervenciones primero → ARMA):
   documentado en TODO.md; cada bifurcación requiere confirmación del analista
   en modo guiado.

2. **Output post-estimación obligatorio**: gráfico ACF/PACF + histograma +
   `model_equation` + párrafo de diagnóstico + sugerencia de reformulación.
   Nunca mostrar solo un subconjunto.

3. **Intervenciones ANTES de ARMA** ("lo más obvio primero"): los outliers
   distorsionan ACF/PACF. El ciclo correcto es:
   ```
   mNN (solo armónicos) → scan ACF contrib → añadir steps → m(NN+1) →
   scan de nuevo → cuando residuos limpios → identificar ARMA → m(NN+2)
   ```

4. **Identificación outliers es iterativa** ("peeling the onion"): al bajar σ
   emergen outliers que estaban enmascarados. Aplicar `describe_prelim_scan`
   sobre residuos del modelo anterior en cada ronda.

5. **`at=` en fue es 0-based**: `at = (año−inicio_año)×freq + (período−1)`.
   Error común: usar 1-based produce desplazamientos silenciosos.

6. **Regla ACF/PACF** (error corregido durante análisis):
   - PACF corta en lag p → **AR(p)**
   - ACF corta en lag q → **MA(q)**

7. **Documentación por decisión**: cada paso debe registrar evidencia usada,
   decisión tomada, herramienta de soporte y alternativas consideradas.

### Flujo MCP guiado — secuencia de tools (revisada)

```
1. plot_mean_deviation_pair  → λ (razón teórica o evidencia m-dt)
2. unit_root_analysis [L]    → d=0,1,2 (ADF+KPSS por nivel)
3. detect_seasonality        → B1 (Treadway) o B2 (BJ), HAC F-test
   ↳ PREGUNTA MODO: guiado / autónomo
4. confirm_and_estimate      → m00: solo armónicos (sin ARMA, sin interv.)
   → OUTPUT: ACF/PACF + histograma + model_equation + diagnóstico
5. describe_prelim_scan      → sobre residuos de m00: outliers + contrib. ACF
   → ITERATIVO hasta residuos limpios:
     a. añadir steps/pulses para outliers > 2.5σ
     b. estimar → describe_prelim_scan sobre nuevos residuos
     c. guardar mNN.pre en cases/
6. ACF/PACF residuos limpios → identificar p, q (ARMA)
   ↳ PREGUNTA: ¿media significativa? (μ̄/SE > 2)
7. confirm_and_estimate      → mFINAL: armónicos + interv. + ARMA + (μ)
   → OUTPUT: ecuación + gráfico + diagnóstico
── SUITE REFINAMIENTO (opcional, en este orden) ──────────────────────
8. seasonal_param_analysis [G] → ¿todos los armónicos son significativos?
9. test_seasonal_simplification [H] → LR test de reducción estacional
10. formal_tests (MEG)          → ¿estacionalidad residual estocástica?
11. sobreparametrizacion [I]    → correlaciones altas entre parámetros
12. compare_versions [Q]        → LR / ΔAIC / ΔBIC entre versiones
```

### Prioridades de implementación

**Prioridad 1 — completan el flujo guiado básico**

| Bloque | Qué | Esfuerzo |
|--------|-----|---------|
| L | Unit root tool dedicado (ADF+KPSS por d=0,1,2 + figura) | medio |
| G | Visualización parámetros estacionales (barras cos/sin ± 2SE) | bajo |
| H | LR test simplificación estacional (qué armónicos eliminar) | medio |
| M | B1/B2 explícito en `guided_identification` (opción D=1) | medio |

**Prioridad 2 — refinamiento y parsimonia**

| Bloque | Qué | Esfuerzo |
|--------|-----|---------|
| I | Sobreparametrización: matriz correlación parámetros | bajo | ✅ |
| K | Shin-Fuller en `describe_formal_tests` | bajo | ✅ |
| Q | `compare_versions`: LR / diff especificación / figura dual | medio |

**Prioridad 3 — documentación integrada**

| Bloque | Qué | Esfuerzo |
|--------|-----|---------|
| P | `record_version` + `export_guion` HTML (guion.json) | alto |

**Fuera de scope por ahora**

| Bloque | Qué |
|--------|-----|
| J | Discriminación automática pulse/step/ramp (LR entre formas) |
| C2 | Batch autónomo refinado |

### Principio de diseño de cada tool MCP

Toda tool del MCP debe seguir la estructura:

```
1. EVIDENCIA    — figura pyfug (base64 ImageContent)
2. ANÁLISIS     — qué se ve, estadísticos clave
3. DECISIÓN     — qué se recomienda y con qué herramienta se fundamenta
4. ALTERNATIVAS — qué otras opciones tiene el analista (para poder volver atrás)
5. ESTADO       — qué modelo/archivo se genera; próximo paso sugerido
```

Esta estructura garantiza trazabilidad completa: el analista siempre sabe
qué decidió, por qué, y cómo deshacer si la decisión resulta incorrecta.

---

## Metodología de referencia

Las 5 etapas iterativas del proceso de construcción de modelos (tesis cap. 2.4):

1. **Especificación inicial** — identificación empírica de (λ, d, D, p, q, P, Q)
2. **Estimación eficiente** — MVENC vía `fue.Model`
3. **Diagnosis** — residuos, Q-test, estacionalidad residual, normalidad
4. **Reformulación** — volver a (2) si la diagnosis lo requiere
5. **Empleo** — previsión y seguimiento vía `fue`

`art` cubre las etapas 1 y 3 (y los contrastes formales de la etapa 4).
Las etapas 2 y 5 las gestiona `fue` directamente.

---

## Arquitectura de módulos

```
art/
  identification.py      — Etapa 1: especificación inicial
  seasonal_detection.py  — Etapa 1: detección de estacionalidad
  model_detection.py     — Etapa 1: detección automática de órdenes ARIMA  ✅
  diagnosis.py           — Etapa 3: diagnosis del modelo estimado           ✅
  formal_tests.py        — Contrastes formales DCD / RV / MEG               ✅ (SF + DCD + DCD_f)
  interventions.py       — Detección y contraste de intervenciones          ✅ (Phase 4a) / [v2] (4b, 4c)
  full_report.py         — Informe HTML integrado post-estimación            ✅ (v1)
```

---

## Estado actual

### `identification.py` ✅

| Función / clase | Estado | Descripción |
|---|---|---|
| `boxcox_transform` | ✅ | Transformación Box-Cox (λ=0 log, λ=1 identidad) |
| `boxcox_selection` | ✅ | Datos para selección λ: original vs log + m-dt |
| `plot_boxcox_selection` | ✅ | Figura 2 filas: serie tipificada + dispersión m-dt |
| `save_boxcox_selection` | ✅ | HTML autocontenido |
| `identification_listing` | ✅ | Listado: serie + ACF/PACF para cada (d, D) |
| `save_listing` | ✅ | HTML con figuras y tabla estadísticos |
| `save_identification_report` | ✅ | Informe combinado adaptativo (Decisión A / B1 / B2) |

Comportamiento del informe según detección de estacionalidad:
- **Decisión A** (sin estacionalidad): 3 paneles, d = 0, 1, 2
- **Decisión B1** (estacionalidad, D=0): 3 paneles con armónicos deterministas
- **Decisión B2** (estacionalidad, D=1): 3 paneles con diferencia estacional

### `seasonal_detection.py` ✅

| Función / clase | Estado | Descripción |
|---|---|---|
| `detect_seasonality` | ✅ | F-test HAC conjunto sobre regresión armónica con base diferenciada |
| `plot_seasonality` | ✅ | Impulsos dummy + banda ±1 SE + panel Wald por frecuencia |
| `save_seasonality` | ✅ | HTML autocontenido |
| `FreqResult` | ✅ | Wald chi² por frecuencia armónica (df=2 ó 1 para Nyquist) |
| `SeasonalDetectionResult` | ✅ | Resultado completo: F, p, dummies, SE, freq_results |

---

## Algoritmo de detección automática de modelos (ART C → Python)

Fuente: `ART_17.01/src/model_detection.c` (2143 líneas).

### Principio fundamental

**No es auto.arima.** No usa AIC/BIC ni estimación MLE durante la búsqueda.  
Es identificación B-J automatizada: compara ACF/PACF teórica de cada modelo candidato
con la ACF/PACF empírica y selecciona el modelo con mayor similitud ponderada.  
Esto replica lo que hace el analista visualmente, pero de forma sistemática y rápida.

### Flujo completo (`ejecutar_deteccion_automatica`)

```
1. PRE-PROCESADO
   ├── Detección de estacionalidad (HAC F-test) → ajustar P_max, Q_max
   ├── Tests de raíz unitaria ADF + KPSS        → sugerir d
   └── Modo desestacionalización opcional:
       restar armónicos → buscar ARMA puro (P=Q=0)

2. REDUCCIÓN DEL ESPACIO DE BÚSQUEDA
   └── determine_effective_orders(acf, pacf)
       ├── p_max_eff = último lag PACF significativo (corte: 3 lags consec. no sig.)
       ├── q_max_eff = último lag ACF  significativo (mismo criterio)
       ├── P_max_eff = último lag estacional PACF significativo (umbral ×1.2)
       └── Q_max_eff = último lag estacional ACF  significativo (umbral ×1.2)

3. BÚSQUEDA EN REJILLA ADAPTATIVA (adaptive_grid_search)
   Para cada (p, q, P, Q) en {0..p_max_eff} × ... × {0..Q_max_eff}:

   a) Filtros de patrón (evitan combinaciones incoherentes):
      ├── validate_ar_pattern: PACF[p] significativa + ≤1 lag sig. después
      └── validate_ma_pattern: ACF[q]  significativa + ≥2 lags NO sig. de los 3 siguientes

   b) FASE GRUESA — grid sobre valores de coeficientes:
      φ, θ, Φ, Θ ∈ [GRID_MIN, GRID_MAX] paso COARSE_GRID_STEP
      → para cada combinación: calcular ACF/PACF teórica → score similitud

   c) FASE FINA — refinamiento coordenada a coordenada:
      cada coeficiente explorado en [best ± 0.2] paso FINE_GRID_STEP

4. FUNCIÓN DE SIMILITUD (pattern_similarity)
   Puntuación ∈ [0, 1] con pesos:
   ├── 60% — primeros 8 lags (ACF + PACF), peso geométrico decreciente 0.8^lag
   ├── 25% — lags estacionales s, 2s (ACF → Q, PACF → P)
   └── 15% — puntos de corte (ACF cut → MA puro, PACF cut → AR puro)

5. PENALIZACIÓN POR PARSIMONIA
   Aplicada dentro de evaluate_model_similarity para preferir modelos simples.

6. OPCIONAL: DISTANCIA DE MAHALANOBIS
   Re-ranking de candidatos usando distancia Mahalanobis en espacio de features
   (acf_cutting_lag, pacf_cutting_lag, decay_rates, seasonal_strengths, ...).
```

### Features extraídas del patrón ACF/PACF (`extract_pattern_features`)

| Feature | Descripción |
|---|---|
| `acf_cutting_lag` | Primer lag donde ACF se corta (3 consec. no sig.) → indica MA puro |
| `pacf_cutting_lag` | Primer lag donde PACF se corta → indica AR puro |
| `acf_decay_rate` | Tasa de decaimiento media (ponderación geométrica, lags 2-8) |
| `pacf_decay_rate` | Idem para PACF |
| `mixed_pattern_score` | Score [0,1]: si ambos decaen + no se cortan → ARMA mixto |
| `seasonal_acf_strength` | Fuerza media de ACF en lags estacionales (s, 2s, ...) |
| `seasonal_pacf_strength` | Idem para PACF |
| `oscillation_freq` | Frecuencia de cambios de signo en primeros 10 lags ACF |

### ACF/PACF teórica (`calcular_ACF_PACF_SARIMA`, en `ARMA.c`)

Calcula la ACF y PACF exactas de un SARIMA(p,d,q)(P,D,Q)_s con coeficientes dados,
sin necesidad de simulación ni estimación. Equivalente Python: `statsmodels.tsa.arima_process.ArmaProcess`.

### Estrategia de port a Python

El port **no replica el grid search de coeficientes**. La razón: el grid busca los coeficientes 
solo para poder evaluar la ACF/PACF teórica. En Python, la ACF teórica de un ARIMA se puede 
calcular directamente con `statsmodels.tsa.arima_process` sin iterar sobre coeficientes.

```
Python: suggest_orders(ts, d, D, p_max, q_max, P_max, Q_max) -> list[ModelSpec]
  ├── Para cada (p,q,P,Q) en espacio reducido:
  │   ├── Filtros de patrón (validate_ar/ma_pattern)
  │   ├── Calcular ACF/PACF teórica con coeficientes típicos (o interpolados)
  │   │   usando statsmodels ArmaProcess
  │   └── score = pattern_similarity(theoretical, empirical)
  └── Devolver lista ordenada por score (top-5 candidatos)

Notas:
  - suggest_orders NO estima, solo sugiere (p,q,P,Q)
  - El analista elige del top-5 y estima con fue MVENC
  - Coeficientes para evaluar la ACF teórica: usar valores "típicos" 
    (φ=0.5, θ=0.3, Φ=0.4, Θ=0.6) que el C también usa para modelos de alto orden
```

---

## Plan de trabajo

### Fase 1b — `model_detection.py`  ✅

Detección automática de órdenes ARIMA por similitud ACF/PACF (port del algoritmo C).

```python
@dataclass
class ModelSpec:
    p: int; d: int; q: int
    P: int; D: int; Q: int; s: int
    similarity: float           # puntuación [0, 1]
    acf_theoretical: np.ndarray
    pacf_theoretical: np.ndarray

def suggest_orders(
    ts,
    d: int, D: int,
    p_max: int = 3, q_max: int = 3,
    P_max: int = 1, Q_max: int = 1,
    top_n: int = 5,
) -> list[ModelSpec]

def plot_model_comparison(ts, specs, start) -> Figure
    # Figura: ACF/PACF empírica vs teórica de los top-N candidatos

def save_model_detection_report(ts, d, D, path) -> list[ModelSpec]
    # HTML: ACF/PACF empírica + top-5 candidatos con sus ACF/PACF teóricas
```

Tareas:
- [x] `_pattern_features(acf, pacf, s)` → dataclass con cutting lags, decay, seasonal
- [x] `_validate_ar_pattern(p, pacf, threshold)` / `_validate_ma_pattern(q, acf, threshold)`  
- [x] `_theoretical_acf_pacf(p, q, P, Q, s, lags)` via `statsmodels.tsa.arima_process`
- [x] `_pattern_similarity(theoretical_feat, empirical_feat)` — pesos 60/25/15
- [x] `_parsimony_penalty(p, q, P, Q, n)` 
- [x] `suggest_orders(...)` — búsqueda completa con filtros y ranking

Dependencia nueva: `statsmodels>=0.14` (solo para ACF/PACF teórica de ARIMA).

### Fase 2 — `diagnosis.py`  ✅

Diagnosis del modelo `fue.Model` ya estimado.

```python
diagnose(model, ts) -> DiagnosisResult
plot_diagnosis(result) -> Figure          # 4 paneles: residuos, ACF, PACF, QQ
save_diagnosis_report(model, ts, path)    # HTML sección de diagnosis
```

Contenidos:
- [x] Residuos tipificados con banda ±2σ
- [x] ACF/PACF de residuos con Q de Ljung-Box
- [x] Detección de estacionalidad en residuos (reutilizar `seasonal_detection`)
- [x] Test de Jarque-Bera (normalidad)
- [x] Tabla de residuos extremos (|z| > 3)
- [x] Gráfico QQ normal

### Fase 3 — `formal_tests.py`  ✅ (SF + DCD + DCD_f)

Contrastes formales de hipótesis (tesis sección 2.4.4).

#### 3SF. Contraste de no estacionariedad (Shin-Fuller 1998)  ✅
```python
shin_fuller(model) -> ShinFullerResult
```
- [x] H₀: φ₁ = φ_null = 1 − s/n  (polinomio AR con raíz casi unitaria)
- [x] φ_null = 1 − s/n (verificado: n=68, s=4 → φ_null = 16/17 = 0.941176)
- [x] Modelo restringido: AR fijo en φ_null, resto libre → reestimación con fue
- [x] LR = 2·(L_libre − L_restringido)  ~  χ²(df) aproximación
- [x] Tests con datos reales: PCE R.1 (LR=19.94), IPC Trim R.2 (LR=16.02)
- Referencia: Shin & Fuller (1998) JTSA 19(5), 591–599

#### 3a. Contraste DCD de no invertibilidad — MA regular  ✅
```python
dcd(model) -> list[DCDResult]
```
- [x] H₀: θ=1 (raíz unitaria en polinomio MA regular)
- [x] LR = 2·[l(θ̂) − l(θ=1)]  distribución no estándar
- [x] Valores críticos tabulados (Cuadro 2.2): 10%=1.00, 5%=1.94, 1%=4.41
- [x] Datos Colombia PO3: LR≈126.8 (tesis 122; diferencia fue-C vs fue-Python ~4%)
- [x] Error apropiado si no hay factores MA libres o modelo no estimado
#### 3a-f. Contraste DCD de no invertibilidad — MA_f  ✅
```python
dcd_f(model) -> list[DCDResult]
```
- [x] H₀: λ₂ = −1 (raíz unitaria en frecuencia f del polinomio MA_f)
- [x] LR = 2·[l(λ̂₂) − l(λ₂=−1)]  distribución no estándar
- [x] Valores críticos: 10%=1.07, 5%=2.02, 1%=4.52
- [x] Usa `model.fit()` (motor C; bug `nlatools.c:tensor()` corregido 2026-06-15)
- [x] Tests funcionales + API con datos IPC mensual (RIPC.1)
- [x] Tests con datos Chile (guion3): PC6 DCD (LR≈149.6), PC7 DCD+DCD_f (LR_MA≈152, LR_f≈4.32)
  - PC7 DCD_f: caso límite — rechaza al 5% pero NO al 1% (LR=4.32 entre 2.02 y 4.52)
  - Total: 95 tests pasando (43 previos + 12 Chile-PC6 + 17 Chile-PC7 + 23 RV)
  - PC8 DCD_f falla por convergencia: cuando ifadf ya incluye freq=1 y se restringe MA_f(freq=1)=-1,
    el likelihood se degrada (raíces comunes AR/MA); no es un bug, es un caso degenerado

**Bug corregido (2026-06-15)**: `nlatools.c:tensor()` — `calloc(nrh+1,...)` con nrl<0
asignaba 1 slot pero el loop escribía en `t[-1]`. Fix: `calloc(nrh-nrl+1,...)` + `t -= nrl`;
`free_tensor` usa `free(t+nrl)`. Ver `fue/TODO.md`.

#### 3b. Contraste RV de frecuencia fija para AR(2)  ✅
```python
rv(model, ar_factor_index=0, freq_null=None) -> list[RVResult]
```
- [x] H₀: f = k (harmónico) para un AR(2) con raíces imaginarias complejas
- [x] LR = 2[l(AR₂ libre) − l(ar_f fijado en k)] ~ χ²(1)
- [x] f̂ = arccos(φ₁/2ρ) · s/2π, ρ = √(−φ₂)
- [x] Tests con datos USA M1 (M1.5): f̂≈3.91, H₀:f=4 no rechaza (LR≈0.49), H₀:f=2 rechaza (LR≈57)
- [x] freq_null=None → prueba todos los harmónicos k=1..s//2

#### 3c. Evaluación de estacionalidad estocástica (MEG)  ✅
```python
meg(model, frequencies=None) -> list[MEGResult]
```
- [x] Para cada frecuencia f = 1,...,s//2−1:
  - Eliminar armónicos cos/sin en f de las intervenciones (cancelación teórica)
  - Activar ifadf[f]=1 (raíz unitaria en f)
  - Añadir MA_f testigo libre (coef inicial -0.9)
  - Reestimar con `model.fit()` (motor C; ~0.13s/frecuencia)
  - Aplicar DCD_f al testigo
  - MA_f invertible (DCD_f rechaza) → **estocástica**; no invertible → **determinista**
- [x] Datos Chile PC6 freq=1: coef≈-0.915, LR≈4.32, rechaza al 5% → **estocástica**
- [x] IPC_ES_m02 (AR(1), 5 frecuencias): todas deterministas; tiempo total 1.58s (C backend)
- [x] Estrategia iterativa documentada: rondas independientes por frecuencia,
      analista decide antes de proceder a ronda 2 con raíces confirmadas
- [x] Frecuencia biannual (f=s//2, alter) excluida por defecto (requiere MA_f orden 1)
- [x] 112 tests pasando (95 + 17 MEG)

#### 3d. MEG_AR — contraste complementario AR_f  ⛔ NO IMPLEMENTADO

**Motivación**: análogo al contraste de Shin-Fuller (1998) para raíces unitarias
regulares, pero aplicado a frecuencias estacionales.  El test de Shin-Fuller usa el
ratio de verosimilitudes incondicional (RV) para contrastar φ₁ ≈ 1 en un ARMA(p,q).
Un MEG_AR aplicaría la misma lógica al AR_f(freq=f): H₀: coef ≈ −1 (raíz unitaria
estacional) vs H₁: coef bien interior (estacionalidad determinista o dinámica
estacionaria).  RV grande → rechaza H₀ → **determinista**; pequeño → no rechaza →
**estocástica**.  La decisión sería la inversa de MEG.

**Razón del abandono (investigación empírica 2026-06-05)**:

En modelos fue con d≥2, una raíz unitaria estacional en freq=f se manifiesta como
MA_f no invertible (MA_f→−1) en la representación ARMA de ∇ᵈy_t, **no** como
AR_f en el polinomio AR.  La demostración:

```
Si y_t tiene raíz unitaria estacional en f, con el modelo ya diferenciado:
  ∇ᵈy_t = (1 − 2cos(2πf/s)·B + B²)⁻¹ · MA(θ) · εt
```

La raíz estacional aparece como factor MA_f en la representación de ∇ᵈy_t.
Añadir un AR_f libre con coef≈−1 al polinomio AR de ∇ᵈy_t crea un filtro doble
en f, con pérdida de verosimilitud catastrófica (Δℓ≈−130 nats, Chile IPC n=192).
El modelo libre siempre converge a AR_f≈0 desde cualquier valor inicial; el
paisaje de verosimilitud es monótonamente creciente desde coef=−1 hasta coef=0.
El RV resultante es siempre ≈258 para **todas** las frecuencias, independientemente
de si la estacionalidad es estocástica o determinista → potencia nula, tamaño ≈ 1.

**Sobre los armónicos**: cuando AR_f es libre, no hay colinealidad matemática con
los cos/sin armónicos (la cancelación sólo ocurre en la frontera coef=−1).  Sin
embargo, ni mantener ni eliminar los armónicos resuelve la degeneración anterior.

**Contexto válido**: el test sería correcto para modelos con d=0 ó d=1 donde la
raíz unitaria estacional aún no se ha extraído al diferenciado.  Equivale al
territorio de los tests OCSB (Osborn, Chui, Smith, Birchenhall) y Canova-Hansen,
que no son parte de la tradición Treadway.

**Conclusión**: para el flujo estándar fue (d≥2), MEG (MA_f testigo + DCD_f) es
el contraste teóricamente correcto y empíricamente válido.  MEG_AR no se implementa.

**TODO críticos previos** (aplicables a MEG también):
- [ ] Verificación Monte Carlo de los valores críticos de DCD y DCD_f (Treadway,
      tesis Cuadro 2.2 y análogo para frecuencia fija).  Los valores actuales son
      los de la tesis, tratados como exactos; no se han producido contrapartes
      simuladas o bootstrap.
- [ ] Si en el futuro se desea implementar MEG_AR, hacerlo para modelos d=0/d=1
      con hipótesis H₀: AR_f → raíz unitaria, usando valores críticos propios
      obtenidos por Monte Carlo (los valores DCD_f **no** son válidos como
      aproximación para el polinomio AR).

### Fase 4 — `interventions.py`

Detección y contraste de intervenciones (tesis sección 2.4.4.4).

#### Phase 4a — Avisos de anomalías  ✅

`diagnose_interventions(model, threshold=3.5, acf_contrib_threshold=0.05) → InterventionDiagnosis`

- [x] Detectar residuos con |z| > umbral (re-estandarizados con media/std muestrales)
- [x] Calcular `variance_fraction` = z²/Σz² (indicador de compresión global ACF/PACF)
- [x] Identificar lags de ACF afectados por contribución par superior a `acf_contrib_threshold`
- [x] Señalar Jarque-Bera y Ljung-Box como poco fiables si hay extremos
- [x] Formatear fechas correctamente (mensual "MM/YYYY", trimestral "QN/YYYY", anual "YYYY")
- [x] `InterventionDiagnosis.summary()` con informe de texto legible
- [x] Tests: 24 tests (Colombia PO2 —z≈−3.38 en 2/1999—, Chile PC6 limpio, API)

#### Phase 4b — Contraste de hipótesis sobre intervenciones  [✅ HECHO]

```python
test_intervention(model, itv_idx, alpha=0.05) -> InterventionTestResult
simplify_interventions(model, alpha=0.05, skip_types=("cos","sin","alter")) -> list[InterventionTestResult]
simplify_summary(results, alpha=0.05) -> str
```

- [x] t-Student H₀: ω=0 por parámetro libre; SE de cov_matrix diagonal; df=n_obs−npar
- [x] Wald H₀: g=0 para FLTs (delta≠0): g=α·ω, V(g)=α·COV(ω)·αᵀ, α=(1,−δ₁,…)
- [x] Ordenación de parámetros correcta (itv_i.omega_free, itv_i.delta_free, …, AR, MA, mu)
- [x] `_intervention_param_start(model, itv_idx)` → índice global de inicio en params
- [x] MCP tool `test_interventions(inp_path, alpha)` → texto con tabla y sugerencia
- [x] `InterventionTestResult.significant` → True si ≥1 omega libre es significativa
- [x] `simplify_summary` muestra significativas vs prescindibles con sugerencia de eliminación
- [x] 11 tests nuevos en `test_interventions.py` + 1 en `test_mcp_server.py`

#### Phase 4c — Detección automática de forma funcional  [FUTURO]

- [ ] Discriminar pulse / step / ramp por comparación de re-estimaciones y test LR

### Fase 5 — Informe integrado  ✅ (v1)

Informe HTML autocontenido, página única con secciones colapsables (`<details>`).

```python
save_full_report(model, path, *, run_meg=True,
                 intervention_threshold=3.5, z_threshold=3.0) -> FullReport
```

`FullReport` dataclass: path + diagnosis + dcd_results + dcd_f_results +
rv_results + meg_results + interventions.

Secciones:
- [x] 1. Modelo estimado — spec ARIMA(p,d,q)(P,D,Q)ₛ, λ, loglik, AIC, BIC,
         tabla de parámetros con SE y t-stats; nombres desde estructura del modelo
- [x] 2. Diagnosis — figura (residuos, ACF/PACF, QQ) + Q-test + JB + estacionalidad residual
- [x] 3. Contrastes formales — DCD, DCD_f, RV (si AR(2)), MEG (si D=0 + armónicos)
- [x] 4. Intervenciones — tabla de extremos con z, var%, lags ACF; avisos JB/Q;
         sección se abre automáticamente si hay extremos

Notas de diseño:
- MEG solo corre cuando `model.D == 0` y hay cos/sin/alter (modelo adecuado en
  el proceso iterativo)
- Contrastes que no aplican (sin MA libre, sin AR(2), etc.) se omiten en silencio
- Secciones 1, 2 y 3 abiertas por defecto; sección 4 abierta solo si hay extremos
- Las secciones de identificación (box-cox, detección estacional, listado) quedan
  fuera de alcance: el analista las ha completado antes de llegar al modelo estimado

Pendiente v2:
- [ ] Sección de identificación opcional (box-cox + seasonal + listing)

---

## Decisiones de diseño fijadas

- Series tipificadas (z-score) en todos los gráficos de nivel → tradición y homogeneidad visual
- Transformación log siempre recomendada a priori para números índice o unidad arbitraria
- Estacionalidad provisional determinista (armónicos) como punto de partida (tesis 2.4.1)
- MEG evalúa posibilidades estocásticas frecuencia a frecuencia, sobre modelo ya estimado
- HAC Newey-West: max_lags = 1 (n≤100), 2 (n≤200), 3 (n>200)
- Lags ACF/PACF: fórmula fug (`_default_lags_fug`)
- Todos los informes son HTML autocontenidos (PNG en base64, sin dependencias externas)

---

## Dependencias

```toml
fue >= 0.1.2          # motor ARIMA: estimación, previsión, lectura .pre/.inp
numpy >= 1.24
matplotlib >= 3.7
scipy >= 1.10         # F, chi², t para contrastes
statsmodels >= 0.14   # ACF/PACF teórica de ARIMA (model_detection.py)
```

---

## Estado de implementación — MCP tools

### Gráficos por herramienta (regla de oro: toda decisión va acompañada de su figura)

| Tool | Bloque | Estado | Gráfico |
|------|--------|--------|---------|
| `series_info` | — | ✅ | — (solo metadatos) |
| `boxcox_analysis` | — | ✅ | ✅ serie original vs log + dispersión m-dt |
| `seasonality_analysis` | — | ✅ | ✅ impulsos dummy + Wald por frecuencia |
| `preliminary_outlier_scan` | E | ✅ | ✅ ∇ᵈ∇ᴰ tipificada ±2σ + outliers marcados |
| `identification_analysis` | — | ✅ | ✅ ACF/PACF en todos los niveles de d hasta d elegido |
| `guided_identification` | B1 | ✅ | ✅ boxcox+seasonal (etapa 1a/1b); ACF/PACF (etapa 1c) |
| `confirm_and_estimate` | B2 | ✅ | ✅ residuos+ACF/PACF+QQ inmediatos |
| `estimate_and_diagnose` | — | ✅ | ✅ residuos+ACF/PACF+QQ |
| `suggest_intervention_form` | B3 | ✅ | ✅ residuos+ACF/PACF+QQ post-intervención |
| `intervention_analysis` | 4a | ✅ | ✅ residuos tipificados (outliers visibles en ±2σ) |
| `formal_tests` | — | ✅ | — (numérico; perfil verosimilitud pendiente) |
| `test_interventions` | 4b | ✅ | — (tabla; pendiente figura de residuos) |
| `save_identification_report` | — | ✅ | HTML con figuras (no inline) |
| `full_report` | — | ✅ | HTML (no inline) |
| `build_model` | C1 | ✅ | ✅ una figura por ronda de estimación |
| `batch_build` | C2 | ✅ | ✅ figura de diagnosis por serie |

### Flujo interactivo completo (modo guiado) — versión actualizada

```
1.  series_info                  → metadatos
2.  boxcox_analysis              → [figura] λ decision
3.  unit_root_analysis [BL-L]    → [tabla] ADF+KPSS en d=0,1,2 → d sugerida
    seasonality_analysis         → [figura] F-test HAC + decision:
                                     • Por defecto: D=0 + armonicos (determinista)
                                     • Opcional:    D=1 multiplicativo (B-J original)
4.  preliminary_outlier_scan     → [figura] serie diferenciada ±2σ + outliers
                                     "lo mas obvio primero" — tratar ANTES de p,q
                                     [BL-N] contribuciones ACF por lag (outlier → lag)
5.  guided_identification        → [figura ACF/PACF] top-5 candidatos p,q
                                     Si D=1: sugerir tambien P, Q [BL-M]
6.  confirm_and_estimate         → [ecuacion BL-O] + [figura 4 paneles diagnosis]
                                     nabla^d[ln y_t] = D_t + phi^{-1}(B) theta(B) a_t
                                     con parametros + SE debajo de cada uno
7.  CICLO DE REFORMULACION (repetir hasta diagnosis OK):
    a. intervention_analysis     → [figura residuos] outliers post-estimacion
                                     [BL-N] + barras contribucion ACF por lag
    b. suggest_intervention_form → [figura] pulse/step/ramp + re-estimar
       (= paso 4 cada vez que hay modelo estimado)
    c. formal_tests              → Shin-Fuller [BL-K] + DCD + DCD_f + RV + MEG
    d. seasonal_param_analysis   → [figura BL-G] coef. estacionales ±2SE
       test_seasonal_simpl.      → [BL-H] RV conjunto para eliminar armonicos
    e. test_interventions        → intervenciones prescindibles (t-test)
    f. sobreparametrizacion      → [BL-I] correlacion params > 0.7 → eliminar
    g. volver a 6 si necesario
8.  full_report                  → informe HTML completo con todas las secciones
```

---

### Bloque C — Flujo autónomo  [✅ HECHO]

#### C1. `build_model(inp_path, output_path, max_rounds=5, run_meg=False)` → list  ✅
Pipeline autónomo completo B-J-T (MCP tool):
```
1. Box-Cox auto (λ=0 si gap≥0, λ=1 si gap<0)
2. Seasonality auto → decision A/B1/B2; d, D, n_harmonics
3. suggest_orders(top_n=5) → tomar top-1 (p, q)
4. Estimar con _make_model + _write_inp + _load_fitted
5. Diagnosis → si extremos: añadir pulse/step y volver a 4 (hasta max_rounds)
6. DCD y MEG opcionales (reportar, no reformular automáticamente)
7. Devolver TextContent (log+tabla+diagnosis) + ImageContent (figura)
```

Helper `_make_model(ts, lam, d, D, p, q, n_harmonics, extra_itvs)` reutilizable
por B2 y C. `extra_itvs` es lista de `(at_0based, "pulse"|"step"|"ramp")`.

#### C2. `batch_build(inp_paths, output_dir, max_rounds=5, run_meg=False)` → list  ✅
Pipeline para múltiples series. Devuelve tabla Markdown de resumen + imagen
por serie + HTML de diagnosis en output_dir. Tolera ficheros faltantes.

---

### Bloque D — Visualización inmediata post-estimación  [✅ HECHO]

**Regla**: cada vez que se estima un modelo (en cualquier flujo), se deben
mostrar siempre y de forma inmediata: residuos tipificados, ACF/PACF de
residuos, Q-test resumen, JB y tabla de parámetros. Nunca dejar al analista
sin feedback visual tras una estimación.

- [x] `estimate_and_diagnose` siempre devuelve `ImageContent` — verificado con test
- [x] `confirm_and_estimate` (B2): siempre devuelve figura + tabla de parámetros juntas
- [x] `build_model` (C1): una figura por ronda de estimación (Block D). Log de rondas
      enriquecido con Q-test (lags fallidos), JB y extremos con z-scores.
      `build_model` con 3 rondas → devuelve 3 imágenes.

---

### Bloque E — Pre-escaneo de outliers antes de identificación ARMA  [✅ HECHO]

**Principio "lo más obvio primero" (tesis cap. 4, Chile/Colombia):**
Un outlier gigante en la serie diferenciada distorsiona la ACF/PACF:
- Infla σ̂ → subestima todos los coeficientes de autocorrelación
- Las ACF/PACF aparecen "muertas" (todo cerca de cero)
- La identificación p, q se hace sobre información distorsionada

**Solución**: escanear ∇ᵈ∇ᴰy_t tipificada ANTES de identificar (p, q).
Si hay |z| > umbral → tratar esa observación con intervención primero.

```python
# describe.py
describe_prelim_scan(ts, d, D, lam, threshold=3.5) -> Description
# - Calcula ∇ᵈ∇ᴰ boxcox(y), tipifica con media/std muestral
# - Detecta |z| > threshold, calcula variance_fraction del mayor outlier
# - Figura: serie tipificada ±2σ (gris) ±threshold (rojo), outliers marcados con fecha
# - Texto: cuánto % de varianza explica el mayor outlier, qué forma tentativa
# - Recomendación: si hay outliers, "tratar antes de identificar ARMA"

# mcp_server.py
preliminary_outlier_scan(inp_path, d, D, lam, threshold=3.5) -> list
```

- [x] `describe_prelim_scan` en `describe.py` (incluye figura inline)
- [x] MCP tool `preliminary_outlier_scan` en `mcp_server.py`
- [ ] Test unitario en `test_mcp_server.py`

---

### Bloque F — Correcciones de gráficos en herramientas existentes  [✅ HECHO]

Corregidos los gaps de visualización encontrados en el análisis de la tesis:

- [x] `describe_identification`: ahora devuelve figura ACF/PACF de todos los
      niveles de diferenciación hasta (d, D) elegido — antes devolvía `None`
- [x] `guided_identification` etapa 2: ahora incluye `ImageContent` con la
      figura ACF/PACF — antes ignoraba `ident.figure_b64`
- [x] `describe_interventions`: ahora devuelve figura de residuos tipificados
      con bandas ±2σ — antes devolvía `None`

---

### Bloque G — Visualización de parámetros estacionales  [✅ COMPLETADO]

**Motivación (tesis cap. 4, figura 4.1 Chile):**
Después de estimar, mostrar un gráfico de los coeficientes cos/sin por
frecuencia con barras ±2SE permite:
- Visualizar qué frecuencias tienen estacionalidad significativa
- Guiar la simplificación (qué armónicos eliminar)
- Comparar patrones estacionales entre submuestras

```python
# describe.py (nueva función)
describe_seasonal_params(model) -> Description
# - Extrae coeficientes cos_k, sin_k para k=1..s//2
# - Calcula amplitud A_k = sqrt(cos_k² + sin_k²) y fase φ_k
# - Figura: barras por frecuencia con ±2SE; dos paneles (cos, sin) o amplitud/fase
# - Texto: qué frecuencias son significativas (|t| > 2)
# - Recomendación: cuáles podrían eliminarse

# mcp_server.py (nuevo tool)
seasonal_param_analysis(inp_path) -> list
```

- [x] Implementar `describe_seasonal_params` en `describe.py`
- [x] Añadir MCP tool `seasonal_param_analysis`
- [x] Tests: 14 tests en `test_seasonal_params.py`

---

### Bloque H — Test conjunto de simplificación estacional  [PENDIENTE]

**Motivación (tesis Chile, PC10 → PC11):**
Test RV H₀: todos los armónicos de frecuencias f₁..fₖ son simultáneamente = 0.
RV = 2[l(libre) - l(restringido)] ~ χ²(2k). Permite reducir de 11 a 1 parámetro
estacional si los datos no discriminan (como Chile PC11 con RV=1.6 << 16.0).

```python
# formal_tests.py (nueva función)
seasonal_simplification_test(model, freq_list=None) -> SeasonalSimplificationResult
# - H₀: cos_f = sin_f = 0 para todas las f en freq_list
# - Reestima con esas restricciones y calcula LR
# - Devuelve: LR, df, p-value, recomendación (mantener/eliminar)

# mcp_server.py (nuevo tool)
test_seasonal_simplification(inp_path, freq_list=None) -> list
```

- [ ] Implementar `seasonal_simplification_test` en `formal_tests.py`
- [ ] Añadir MCP tool `test_seasonal_simplification`
- [ ] Test unitario con Chile PC10 (esperar RV ≈ 1.6 para restricción de 10 params)

---

### Bloque I — Detección de sobreparametrización  [PENDIENTE]

**Motivación (tesis, criterio de correlación de parámetros):**
Cuando |corr(θ̂_i, θ̂_j)| > 0.7, el modelo puede estar sobreparametrizado
(ejemplo: Chile PC4 con AR(1) y MA(1) correlados → eliminar AR(1)).
Este diagnóstico debe mostrarse automáticamente tras cada estimación.

```python
# Ampliar DiagnosisResult en diagnosis.py
# - param_corr: np.ndarray (matriz correlación de parámetros, si disponible)
# - high_corr_pairs: list[(i,j,r)] con |r| > 0.7

# Ampliar describe_diagnosis para incluir advertencias de sobreparametrización
# Ampliar plot_diagnosis con tabla adicional o heatmap de correlaciones
```

- [ ] Extraer matriz de correlación de parámetros de `fue.Model._result`
- [ ] Añadir `param_corr` y `high_corr_pairs` a `DiagnosisResult`
- [ ] Mostrar en `describe_diagnosis` como advertencia
- [ ] Test unitario

---

### Bloque P — Sistema de documentación: guion de análisis  [PENDIENTE]

**Motivación (guion.tex de la tesis):**
La tesis documenta cada modelo como una página: ecuación del modelo, figura de diagnosis
y tabla de residuos extremos con notas del analista. Los modelos se nombran secuencialmente
(PC1, PC2, ..., PC11). El guion es la traza completa del proceso de construcción.

**Diseño:**

```
Estructura de archivos por análisis (ej. Chile IPC 1994-2001):
  chile_ipc/
    guion.json          ← traza completa de todas las versiones
    v01_PC1.inp         ← modelo estimado versión 1
    v02_PC2.inp         ← modelo estimado versión 2
    ...
    guion.html          ← informe navegable generado desde guion.json
```

**Formato guion.json** (inspirado en el guion.tex de la tesis):

```json
{
  "series": "IPC Chile mensual 1/94-12/01",
  "analyst": "D. Guerrero",
  "created": "2026-06-12",
  "entries": [
    {
      "version": 1,
      "name": "PC1",
      "inp_path": "chile_ipc/v01_PC1.inp",
      "timestamp": "2026-06-12T10:30:00",
      "spec": {
        "lam": 0.0, "d": 2, "D": 0, "p": 0, "q": 0,
        "n_harmonics": 6, "interventions": []
      },
      "stats": {
        "loglik": -180.3, "aic": 384.6, "bic": 408.2,
        "sigma_a": 0.0063, "q_pass": false, "jb_pass": false,
        "n_extreme": 4, "extreme": [
          {"obs": 55, "date": "9/1990", "z": 3.96},
          {"obs": 57, "date": "11/1990", "z": -3.38}
        ]
      },
      "figure_b64": "...",
      "equation": "nabla^2[ln PC_t] = D_t + N_t  (solo armonicos, sin ARMA)",
      "decision": "Modelo inicial: solo estacionalidad determinista",
      "rationale": "Box-Cox: lambda=0 (log); d=2 (ACF decae lentamente en d=1); D=0 (armonicos); sin ARMA inicial",
      "problems_found": "ACF/PACF residuos: espiga en lag 1 → añadir MA(1); outliers 9/90 y 11/90 (z≈±4)",
      "next_version": "PC2: añadir MA(1) para capturar lag 1"
    },
    {
      "version": 2,
      "name": "PC2",
      "change_from_prev": "Añadido MA(1)",
      ...
    }
  ]
}
```

**MCP tools nuevas:**

```python
# mcp_server.py
record_version(inp_path: str, guion_path: str,
               name: str = "",
               decision: str = "",
               rationale: str = "",
               next_step: str = "") -> str
# - Estima el modelo del inp_path
# - Añade entrada al guion.json (crea si no existe)
# - Calcula automáticamente: stats, equation (BL-O), diff con version anterior
# - Devuelve: nombre de versión asignado + resumen de cambios

export_guion(guion_path: str, output_html: str) -> str
# - Lee guion.json
# - Genera HTML navegable con una sección colapsable por versión
# - Cada sección: ecuación + figura diagnosis + tabla residuos + notas decision
# - Resumen cronológico: tabla de versiones con AIC/BIC/Q/JB
# - Estilo: similar al guion.tex de la tesis pero interactivo
```

**Auto-documentación en herramientas existentes:**
- `confirm_and_estimate` y `suggest_intervention_form`: parámetro opcional `guion_path`
  → si se proporciona, añaden automáticamente la versión al guion sin llamar record_version
- `build_model`: genera guion.json automáticamente si se especifica `guion_path`

- [ ] Definir `GuionEntry` dataclass en nuevo módulo `art/guion.py`
- [ ] Implementar `record_version` MCP tool
- [ ] Implementar `export_guion` MCP tool → HTML con una sección por versión
- [ ] Integrar parámetro `guion_path` opcional en `confirm_and_estimate` y `suggest_intervention_form`
- [ ] Integrar en `build_model` (C1): generación automática de guion.json
- [ ] Tests: crear guion de Chile PC1→PC6 y verificar HTML exportado

---

### Bloque Q — Control de versiones y comparación de modelos  [SIGUIENTE PRIORIDAD]

**Motivación**: el flujo iterativo B-J-T produce una secuencia de versiones del modelo
(PC1 → PC2 → … → PC11 en la tesis). El analista necesita comparar versiones adyacentes
para justificar cada cambio con evidencia estadística: LR test si están anidadas, ΔAIC/ΔBIC
si no lo están. `compare_versions` cierra este ciclo en el flujo guiado (paso 12 del flujo MCP).

**Convención de nombrado:**

```
# Prefijo vNN garantiza orden cronológico; sufijo libre (como en la tesis)
cases/IPC_ES/IPC_ES_m01.pre  →  "m01" (inicial: solo armónicos)
cases/IPC_ES/IPC_ES_m02.pre  →  "m02" (+ AR(1))
cases/IPC_ES/IPC_ES_m03.pre  →  "m03" (reformulación)
```

**MCP tool de comparación:**

```python
compare_versions(inp_path_a: str, inp_path_b: str,
                 guion_path: str = "") -> list
# Salida: TextContent + ImageContent
#
# TextContent:
#   1. Diff de especificación:
#      - ARIMA(p,d,q): A=(1,1,0) → B=(1,1,1) [añadido MA(1)]
#      - Intervenciones: +step 3/2022, −pulse 5/2021
#      - Armónicos: sin cambio
#   2. Tabla estadísticos lado a lado:
#      | Estadístico | Modelo A | Modelo B | Δ (B−A) |
#      | loglik      | −145.3   | −138.7   | +6.6    |
#      | AIC         |  304.7   |  291.4   | −13.3   |
#      | BIC         |  312.1   |  302.7   | −9.4    |
#      | σ̂_a         | 0.00314  | 0.00289  | −8%     |
#      | Q-test      | ✗        | ✓        |         |
#      | JB          | ✓        | ✓        |         |
#   3. Test LR si anidados: LR = 2·(l_B − l_A) ~ χ²(k), p-valor
#      Detección de anidamiento: B anida A si spec(A) ⊆ spec(B)
#      (misma serie, mismo d, D; B tiene todo lo de A + algo más)
#   4. Veredicto: "B mejora significativamente" / "B no justificado (ΔAIC>0)"
#
# ImageContent: figura 2×3 paneles
#   Col izq: residuos tipificados, ACF, PACF de A
#   Col der: residuos tipificados, ACF, PACF de B
```

**Detección de anidamiento** (para decidir si aplicar LR o solo ΔAIC/ΔBIC):

```python
def _are_nested(m_a, m_b) -> tuple[bool, int]:
    # B anida A si: misma serie (n, freq, lam, d, D iguales)
    # Y la spec de A es subconjunto de la de B:
    #   - p_a <= p_b, q_a <= q_b (ARMA regular)
    #   - intervenciones de A ⊆ intervenciones de B (mismas fechas y tipos)
    #   - armónicos de A ⊆ armónicos de B
    # k = número de parámetros adicionales en B vs A
    # Devuelve (True, k) si B anida A, (False, 0) si no
```

**Integración con guion** (independiente de Bloque P — no depende de guion.json):
- `compare_versions` funciona solo con dos ficheros `.pre`/`.inp`, sin guion
- Si `guion_path` se proporciona, anota el resultado de la comparación en la entrada
  correspondiente del guion.json (campo `"comparison_with_prev"`)

**Casos de prueba:**

| Par A → B | Cambio | LR esperado | Veredicto esperado |
|-----------|--------|------------|-------------------|
| IPC_ES_m01 → IPC_ES_m02 | +AR(1) | ~10–20 | B mejora (χ²(1), p<0.01) |
| Chile PC5 → PC6 (de la tesis) | −AR(1) | ~4–6 | A mejor (ΔAIC > 0 al eliminar AR) |

- [ ] Implementar `_are_nested(m_a, m_b) -> (bool, int)` en `formal_tests.py` o módulo aux
- [ ] Implementar `compare_versions` en `mcp_server.py`
- [ ] Figura comparativa: `plot_comparison(diag_a, diag_b) -> Figure` (2 cols × 3 filas:
      residuos tipificados, ACF residuos, PACF residuos — sin QQ)
      en `diagnosis.py`; devolver como único `ImageContent`
- [ ] LR test automático si `_are_nested` → `True`; ΔAIC/ΔBIC siempre
- [ ] Tests con IPC_ES_m01 vs IPC_ES_m02 (verificar Δloglik, LR, ΔAIC)

---

### Bloque J — Phase 4c: discriminación de forma de intervención  [FUTURO]

```python
discriminate_intervention_form(model, at_0based) -> InterventionFormResult
# - Estima tres versiones: pulse, step, ramp en at_0based
# - LR test entre ellas (pulse vs step, pulse vs ramp)
# - Recomienda la forma más parsimoniosa con soporte estadístico
```

- [ ] Implementar en `interventions.py`
- [ ] MCP tool `discriminate_intervention` (Phase 4c)

---

### Bloque K — Shin-Fuller en MCP/describe  [✅ COMPLETADO]

**Estado**: `shin_fuller(model)` implementado en `formal_tests.py`. Integrado en
`describe_formal_tests` con formato completo (φ̂, Φ̂₁ᵤ, valores críticos 10/5/1%).
Bug corregido: condición "Ningún contraste" ahora incluye `sf_res is None`.
Tests en `test_mcp_server.py`: `test_formal_tests_shin_fuller_ipc_es` y
`test_formal_tests_shin_fuller_data_field`.

**Acción**: añadir Shin-Fuller a `describe_formal_tests` junto con DCD, RV, MEG.

```python
# En describe.py → describe_formal_tests():
# Añadir:
sf_res = _try(lambda: shin_fuller(model), None)
if sf_res:
    lines.append(f"\n**Shin-Fuller (no estacionariedad AR)** (H₀: φ₁≈1−s/n)")
    lines.append(f"- φ_null={sf_res.phi_null:.4f}, φ̂₁={sf_res.phi_free[0]:.4f}")
    lines.append(f"- LR={sf_res.lr:.3f}, p={sf_res.pvalue:.5f}")
    verdict = "Rechaza H₀ ✓ (modelo estacionario)" if sf_res.rejects_5pct else "No rechaza H₀ ✗ (posible raíz unitaria)"
    lines.append(f"- {verdict}")
```

**Nota crítica**: los valores críticos de Shin-Fuller (Cuadro 2.x tesis o tabla del artículo
original Shin & Fuller 1998 JTSA 19(5)) deben verificarse antes de usar en producción.
Al añadir este contraste, **pedir el artículo** Shin & Fuller (1998) para confirmar los
valores críticos exactos a 1%, 5%, 10% por tamaño muestral.

- [ ] Añadir SF a `describe_formal_tests` (3 líneas de código)
- [ ] Verificar valores críticos con artículo Shin & Fuller (1998)
- [ ] Test en `test_mcp_server.py` para verificar que `formal_tests` incluye SF

---

### Bloque L — Tests de raíz unitaria dedicados (ADF + KPSS por nivel)  [✅ COMPLETADO]

**Estado actual**: ADF + KPSS están embebidos en `describe_seasonality` solo para d=1 fijo.
El ART C (`ART_18/src/unit_root_tests.c`) los aplica en cada nivel d=0,1,2.

**Necesidad**: función dedicada que teste en cada nivel y decida d automáticamente,
tanto para el flujo interactivo (informativa) como para el autónomo (decisión automática).

```python
# identification.py o formal_tests.py (nueva función)
@dataclass
class UnitRootResult:
    d: int                   # nivel diferenciación testado
    adf_stat: float
    adf_pvalue: float
    adf_rejects: bool        # H₀: raíz unitaria
    kpss_stat: float
    kpss_pvalue: float
    kpss_rejects: bool       # H₀: estacionariedad
    verdict: str             # "estacionaria" | "raiz_unitaria" | "ambiguo"

def unit_root_tests(ts, lam=0.0, max_d=2) -> list[UnitRootResult]
# - Para cada d en 0..max_d: calcula ∇ᵈboxcox(y) y aplica ADF + KPSS
# - ADF: H₀ raíz unitaria, rechazar = estacionaria
# - KPSS: H₀ estacionaria, rechazar = no estacionaria
# - Consenso ADF+KPSS → d óptimo
# - Figura: tabla de resultados por nivel + recomendación de d

# mcp_server.py (nuevo tool)
unit_root_analysis(inp_path, lam=0.0, max_d=2) -> list
# Devuelve tabla + figura de la serie en cada nivel
```

**Integración con flujo guiado**: insertar entre Box-Cox y el listado de identificación.
Proporciona evidencia formal para elegir d (complementa la inspección visual de ACF).

- [x] Implementar `unit_root_tests` en `identification.py`
- [x] Figura: tabla coloreada por nivel d + recomendación visual
- [x] MCP tool `unit_root_analysis`
- [x] Integrar en `guided_identification` (Call 2): ADF+KPSS tabla + figura automáticos
- [x] Tests unitarios: 25 tests en `test_unit_root.py` (PCE n=68, verdicts, describe)

---

### Bloque M — Estacionalidad: determinista por defecto + opción D=1  [PENDIENTE]

**Situación actual**: `describe_seasonality` siempre recomienda B1 (determinista).
No hay forma de elegir D=1 (modelo multiplicativo ARIMA(p,d,q)(P,D,Q)_s) desde
el flujo guiado. Esta era la tradición Box-Jenkins original.

**Cambio de diseño**:
- **Por defecto**: D=0 + armónicos (determinista, tradición Treadway) → decisión B1
- **Opción D=1**: estacionalidad multiplicativa (tradición B-J original) → decisión B2
  - Solo ofrecida si HAC F-test detecta estacionalidad
  - Si se elige D=1: el modelo pasa a ARIMA(p,d,q)(P,D,Q)_s
  - P, Q a determinar en paso de identificación ARMA (seasonal AR/MA)
  - No se añaden armónicos cos/sin (los sustituye la diferencia estacional)

```python
# En describe_seasonality y guided_identification:
# Añadir parámetro: seasonality_form="deterministic" | "multiplicative"
# Si "multiplicative": D=1, n_harmonics=0, modelo SARIMA

# En _build_inp / _make_model: soporte para D=1 + MA_s/AR_s
# (ya hay soporte en fue para ma_s, ar_s — solo hay que usarlo)

# MCP: guided_identification(inp_path, lam, d, D, seasonality_form="deterministic")
# Si seasonality_form="multiplicative": sugerir también P, Q además de p, q
```

**Notas de implementación**:
- La opción multiplicativa usa `ma_s` / `ar_s` en fue (seasonal MA/AR), no `ma_f`
- `_make_model` ya construye `ar_s=[], ma_s=[]` — ampliar para P,Q > 0
- La identificación de P, Q sigue el mismo patrón que p, q pero en lags estacionales

- [ ] Añadir parámetro `seasonality_form` a `describe_seasonality` y `guided_identification`
- [ ] Ampliar `_make_model` para soportar P > 0 y Q > 0 (ma_s, ar_s)
- [ ] Ampliar `suggest_orders` en `model_detection.py` para sugerir también P, Q (ya tiene lógica)
- [ ] Ampliar `_build_inp` para generar sección anual MA/AR con fue
- [ ] Tests con serie de ejemplo mensual usando SARIMA(0,1,1)(0,1,1)_12

---

### Bloque N — Visualización de contribuciones ACF en pre-escaneo  [✅ HECHO jun-2026]

Implementado en `describe_prelim_scan`: figura bipartita con residuos tipificados
(panel superior) y barras de contribución de outliers a la ACF (panel inferior,
rojo = parte del coeficiente ACF debida al outlier, azul = ACF total).

Función auxiliar `_acf_outlier_contributions` calcula:
`C_k(p) = [ẑ_p · ẑ_{p+k} + ẑ_{p-k} · ẑ_p] / Σ_j ẑ_j²`

**Uso**: llamar `describe_prelim_scan` sobre residuos de un modelo estimado
(creando `TimeSeries` con `d=0, lam=1.0`) para ver qué outliers distorsionan
la ACF y en qué lags, antes de identificar la parte ARMA.

---

### Bloque O — Ecuación del modelo estimado  [✅ HECHO — bug fix jun-2026]

**Bug fix jun-2026**: la ecuación de ruido mostraba `∇(1−φB)(Nₜ−μ)` (∇ fuera del
polinomio AR). Corregido a `(1−φB)(∇Nₜ−μ)=aₜ` — μ es la media del proceso
diferenciado ∇Nₜ, no del nivel. Fix en `describe.py` líneas ~888–905:
incorporar `diff_s` dentro del `nt_label` en lugar de prependerlo a `lhs_items`.

**Motivación**: fue C escribe el modelo como operadores polinomiales en LaTeX.
En Claude, sin renderizar LaTeX, usar Unicode para la misma estructura.

**Formato objetivo** (igual que fue LaTeX pero en Unicode):

```
∇²[ln PCₜ]  =  D_t  +  N_t

  D_t  =  +0.231·cos(π/6·t)     +0.118·sin(π/6·t)     ...  −0.015·ξₜ^{step,08/95}
             (0.045)                (0.038)                       (0.005)

  φ(B)·N_t  =  θ(B)·aₜ
  φ(B) = (1 − 0.42B)            [AR(1)]
              (0.08)
  θ(B) = (1 − 0.89B)            [MA(1)]
              (0.05)

  σ̂_a = 0.00314  |  loglik = −145.3  |  AIC = 304.7  |  BIC = 312.1
```

**Frecuencias de armónicos (mensual, freq=12)**:
```
f=1: cos(π/6·t),  sin(π/6·t)
f=2: cos(π/3·t),  sin(π/3·t)
f=3: cos(π/2·t),  sin(π/2·t)
f=4: cos(2π/3·t), sin(2π/3·t)
f=5: cos(5π/6·t), sin(5π/6·t)
f=6: (-1)ᵗ  (alternancia, Nyquist)
```
(igual que en fue.c líneas 2109–2138)

```python
# En describe.py (nueva función)
def model_equation(model) -> str
# - Construye la representación textual del modelo estimado
# - Operadores φ(B), θ(B) con coeficientes y SE
# - Componentes deterministas D_t con coeficientes y SE
# - Diferenciación: ∇, ∇², ∇_12, etc.
# - σ̂_a, loglik, AIC, BIC al final

# Integrar en:
# - describe_diagnosis (añadir la ecuación antes de la figura)
# - confirm_and_estimate (mostrar ecuación + figura)
# - build_model (mostrar ecuación del modelo final)
```

- [x] Implementar `model_equation(ts, model) -> str` en `describe.py`
      — dos ecuaciones: (1) nivel con Dₜ+Nₜ, (2) ruido con φ(B)∇ᵈNₜ=θ(B)aₜ
      — _TwoLine builder: SE alineado bajo cada coeficiente (≡ \\est{}{} LaTeX)
      — firma: `(v, se) = pi.pop()` sigue orden EXACTO de m.params
      — convención ARMA: valor positivo → restar (signo −)
      — factores MA_f con two_cos exacto (√3, 1, 0, negativo → + B)
      — σ̂ₐ con refactor: si refactor≥10 → display en %; si lam=0 y pequeño → pct
- [x] Mapear frecuencias de armónicos (freq=4, 12) con fracciones de π correctas
- [x] Integrar en `describe_diagnosis`: ecuación precede a la sección de diagnosis
- [x] Nuevo MCP tool `model_equation_display(inp_path)` → TextContent con la ecuación
- [ ] Integrar en `build_model` log final (pendiente)
- [ ] Tests: verificar output con Chile PC6 y Colombia PO3 (pendiente)

---

## Archivos de prueba

Series reales usadas para desarrollo:
- `tests/real_cases/PRICES/IPC/Mensual/sample_1.2002_12.2007/RIPC.1.pre`
  — IPC mensual (n=72, freq=12), estacionalidad claramente detectada, log a priori

Casos de estudio IPC 4 países Europa+USA (2002-2023, n=263): `../Data/IPC.xlsx`
— Francia, Alemania, España, USA  
— Anomalías detectadas: ES/DE/FR en 2022-2023 (inflación Ucrania), USA en 2008 (Lehman)

Casos de estudio IPC 8 países (2002-2019, n=216): ver `CASE_STUDIES.md`  
— España, Canadá, EMU, Alemania, USA, Francia, UK, Japón  
— Todos: λ=0, d=1, D=0, 10 armónicos, ≥1 alter  
— Patrón dominante: AR solo en lag 2 (4/8 países)
