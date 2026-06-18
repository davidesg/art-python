# art-python — TODO

## Bugs conocidos

- [ ] **MEG no evalúa la frecuencia de Nyquist (bienal, f=s/2)**: `meg`
      (`art/formal_tests.py`) por defecto contrasta solo `f=1…s/2−1` (5 en
      mensual), pero la tesis (chap2.4) y Abraham & Box (1978, Tabla A1)
      especifican `f=1…s/2` (6 en mensual), incluyendo el Nyquist.
      **NO es limitación del motor** — la nota del docstring de `meg`
      ("requires first-order MA handling not yet implemented") es incorrecta:
      el factor de Nyquist es de primer orden `(1+B)` (raíz −1), un MA con
      parámetro negativo que fue estima sin problema, y el AR_f en f=6 ya está
      implementado. Para evaluar f=6 basta extender `meg`:
        • eliminar el término determinista `alter` (=(−1)ᵗ) en f=s/2 (no cos/sin),
        • añadir la diferencia con raíz unitaria en Nyquist (AR_f homogéneamente
          no estacionario / `ifadf[s/2]=1` → `(1+B)`),
        • añadir el MA_f testigo con preestimación −0.8/−0.9,
        • aplicar DCD_f como en el resto de frecuencias.
      Actualizar `frequencies = range(1, s//2+1)`, el removal de `alter`, y el
      test `test_meg_returns_five_results` (5→6). Ref: Abraham-Box Tabla A1
      (`literature/Abraham-DeterministicForecastAdaptiveTimeDependent-1978.pdf`).
      Corregir también la nota errónea del docstring de `meg`.

- [x] **nlags en series cortas** (RESUELTO): pyfug `plot_combined` pedía
      `nlags = 3·(f+1)` (convención J-T) y solo capaba a `n−1`, pero statsmodels
      `pacf` exige `nlags < n/2` → ValueError con muestras cortas (n=72 mensual).
      Fix en pyfug: `plot_combined` capa `nlags = min(…, n//2−1)` (ambos paneles
      consistentes, convención preservada cuando n>6·(f+1)) y `statistics.pacf`
      capa defensivamente a `len//2−1`. Test de regresión:
      `tests/test_golden_pipeline.py::test_diagnosis_short_series_no_crash`.

## Filosofía: ART simple + Claude como analista BJ

### Modelo de colaboración (documentado en sesión jun-2026)

La experiencia con IPC_DE, IPC_FR, IPC_ES y WTI mostró que Claude funciona bien
como analista Box-Jenkins independiente, usando directamente `pyfug` y `fue` como
instrumentos. ART no necesita ser un agente complejo que automatice el flujo entero:
provee instrumentos, Claude aporta criterio.

**División de responsabilidades**:

| Capa | Qué hace | Herramienta |
|------|----------|-------------|
| **pyfug** | Gráficos Jenkins-Treadway (serie, ACF/PACF, histograma, media-σ) | Python + matplotlib |
| **fue** | Estimación ML exacta ARIMA + intervenciones | Python (+ C opcional) |
| **ART** | Pruebas formales, selección de modelo, criterios de parada | Python |
| **Claude** | Identificación BJ, interpretación, refinamiento iterativo | LLM |

---

## Flujo BJ completo documentado (jun-2026)

### Paso 1 — Transformación Box-Cox (λ)

**Gráfico**: `plot_mean_deviation_pair(ser, name="X")` — nivel y log uno al lado del otro.

**Criterio empírico** (m-dt):
- Nivel: si los puntos forman pendiente positiva (σ ∝ μ) → log indicado
- Log: si los puntos se dispersan sin pendiente (σ ≈ cte) → λ=0 confirmado

**Criterio teórico** (prevalece aunque el gráfico no sea concluyente):
- **Números índice** (IPC, IPCA, IPP, deflactores...): base arbitraria (p.e. 2015=100),
  las diferencias absolutas carecen de sentido; las tasas de variación (∇ ln) sí lo tienen.
- **Series con base arbitraria** (precios en unidades nominales, producciones indexadas):
  mismo argumento — el nivel no es comparable entre períodos.
- **Series de precios de commodities** (WTI, Brent, gas...): la volatilidad crece con el
  nivel, σ ∝ μ es la norma; el log estabiliza la varianza.
- Regla práctica: si hay razón teórica para λ=0, usarlo aunque el m-dt no lo exija.

**Comentario inicial al analista** (antes de ver el gráfico):

> El analista puede imponer λ a priori sin necesidad de ver el m-dt:
> - Para **números índice** (IPC, IPCA, IPP, deflactores) con base arbitraria,
>   λ=0 es la elección natural — las diferencias logarítmicas son tasas de variación.
> - Para **precios de commodities** (WTI, Brent, gas natural) y series multiplicativas,
>   el log estabiliza la varianza por construcción.
> - El m-dt sirve para **confirmar o cuestionar** esa elección, no para sustituirla.
>   Si el m-dt contradice la elección teórica, es señal de que algo inusual ocurre
>   (cambio estructural, truncamiento, error de datos).

**Análisis de casos (jun-2026)**:

| Serie | Evidencia m-dt nivel | Evidencia m-dt log | Decisión | Razón principal |
|-------|---------------------|-------------------|----------|----------------|
| IPC_DE | nube horizontal, outlier 2022 sup-der | similar | **λ=0** | índice base arbitraria (2015=100) |
| IPC_ES | nube dispersa, sin pendiente clara | similar | **λ=0** | índice base arbitraria (2016=100) |
| IPC_FR | nube horizontal, outlier 2022 sup-der | similar | **λ=0** | índice base arbitraria (2015=100) |
| WTI    | pendiente positiva visible | nube sin pendiente | **λ=0** | commodity + evidencia empírica |

Para los tres IPC el criterio teórico es determinante: el m-dt no muestra
heteroscedasticidad fuerte porque la inflación fue estable y baja en 2002-2021;
el outlier de 2022 (crisis energética) es un episodio excepcional, no estructura.
Para WTI el m-dt confirma empíricamente lo que la teoría ya indica.

---

### Paso 2 — Diferenciación (d, D)

Sobre la serie transformada (`ln x` si λ=0):

**2a. Diferencia regular (d)**

`plot_combined(ln x)` + ADF/KPSS sobre ln x → ACF decae → d=1

Comentario tipo:
> La ACF decae lentamente desde valores cercanos a 1 — no estacionariedad clara.
> ADF no rechaza raíz unitaria; KPSS rechaza estacionariedad. Los contrastes son
> herramienta de apoyo: la estacionalidad marcada reduce la potencia del ADF
> (residuos del AR auxiliar no son ruido blanco). La decisión d=1 descansa
> principalmente en el patrón ACF/PACF.

**2b. Estacionalidad — bifurcación B1/B2**

`plot_combined(∇ ln x)` + **contraste HAC de estacionalidad** (ART):

```python
from art.seasonal_detection import detect_seasonality, plot_seasonality
result = detect_seasonality(ts, d=1, lam=0.0)
# result.f_stat, result.p_value, result.seasonal_detected
fig = plot_seasonality(result)   # opcional — efectos mensuales + Wald por frecuencia
```

Comentario tipo cuando la estacionalidad es evidente:
> La ACF de ∇ ln x muestra picos en lags s, 2s, 3s — estacionalidad clara.
> HAC F(s-1, n-s) >> 0, p=0.000. Cuando no es obvia visualmente, el test HAC
> es especialmente valioso; el gráfico aporta además los efectos mensuales estimados.

**Bifurcación B1 / B2** — el analista elige la tradición metodológica:

| Opción | Tradición | Especificación | Contrastación posterior |
|--------|-----------|---------------|------------------------|
| **B1** | **Treadway** | d=1, D=0 + armónicos cos/sin en D_t | MEG frecuencia por frecuencia |
| **B2** | **Box-Jenkins** | d=1, D=1 (SARIMA multiplicativo) | MEG sobre D=1 vs D=0 |

**B1 (Treadway)**: la estacionalidad se modela como determinista (efectos fijos mensuales
via armónicos). Más general: permite que cada frecuencia estacional sea significativa
o no de forma independiente. Los residuos quedan más limpios para identificar el ARMA.
Tras estimar, el test MEG de ART contrasta si alguna frecuencia requiere tratamiento
estocástico. Es el camino propio del enfoque BJ-Treadway de ART.

**B2 (Box-Jenkins)**: la estacionalidad se modela como estocástica imponiendo D=1.
Conduce directamente a los modelos multiplicativos ARIMA(p,1,q)(P,1,Q)₁₂ de BJ.
Más parsimonioso cuando la estacionalidad es claramente estocástica, pero impone
una restricción que puede no ser necesaria en todas las frecuencias.

El analista elige explícitamente entre las dos tradiciones. ART implementa B1 como
flujo principal; B2 es también soportado como hipótesis de trabajo alternativa.

**Casos documentados (jun-2026)**:
- **IPC_ES** (mensual): d=1 (ADF t=−2.42 p=0.37; KPSS p<0.01); HAC F(11,250)=6351.7 p=0.0000 → **B1**
- **IPC_DE** (mensual): d=1, D=1 → ARIMA(0,1,0)(0,1,1)₁₂ (B2)
- **WTI**   (mensual): d=1, D=0, sin estacionalidad → AR(2) + escalones

---

### Paso 2c — Modo de análisis (pregunta obligatoria al analista)

**Antes de continuar con la identificación ARMA**, Claude debe preguntar:

> ¿El análisis está en **modo guiado** (un paso a la vez, con comentario y confirmación)
> o en **modo autónomo** (flujo completo hasta diagnóstico final)?

Esto determina el ritmo de la sesión y si Claude espera respuesta en cada bifurcación.

---

### Paso 3 — Intervenciones primero ("lo más obvio primero")

**Principio BJ-T**: los outliers extremos distorsionan las ACF/PACF ("las matan"),
haciendo que los coeficientes ARMA identificados sean artefactos de las interacciones
entre valores extremos, no estructura genuina de la serie. La secuencia correcta es:

1. **Identificar y tratar intervenciones** antes de identificar el ARMA
2. **Luego** identificar ARMA en los residuos limpios

**Error a evitar** (documentado en IPC_ES, jun-2026): tras el primer modelo con armónicos,
ACF(1)=+0.31* llevó a proponer MA(1). Pero había 16 outliers en 2021-2023 (máx +6.1σ)
que distorsionaban toda la ACF. El MA(1) era probablemente un artefacto. La decisión
correcta es tratar primero los outliers, luego reidentificar el ARMA.

**Herramienta ART**: `preliminary_outlier_scan` — identifica residuos > 2σ y muestra
sus contribuciones a la ACF, permitiendo calibrar cuánto distorsionan los correlogramas.

```python
from art.interventions import preliminary_outlier_scan
result = preliminary_outlier_scan(model_residuals, sigma, ...)
```

**Secuencia correcta para B1 (Treadway)**:
1. Estimar armónicos (sin ARMA)
2. **Identificar outliers** → añadir escalones/impulsos para los más extremos
3. Reestimar con intervenciones → ACF/PACF limpias
4. **Ahora** identificar ARMA en residuos limpios
5. Estimar modelo completo (armónicos + intervenciones + ARMA)

### Paso 4 — Identificación ARMA (sobre residuos limpios)

ACF/PACF de residuos tras tratar outliers:
- PACF(1..p) corta, ACF decae → **AR(p)**   ← regla clave
- ACF(1..q) corta, PACF decae → **MA(q)**
- ACF(s) significativo, PACF(s) decae → SMA(1)
- Ambas decaen → ARMA(p,q)

**Regla mnemotécnica**: PACF corta → AR; ACF corta → MA.

**Media**: si $\bar{w}/\sigma_{\bar{w}} > 2$, la media es significativa → incluir `estimate_mu=True`.
La media en $\nabla \ln x_t$ implica una tendencia (drift) en $\ln x_t$.

**Caso IPC_ES (jun-2026)**:
- PACF(1)=+0.35*, corte → AR(1)
- μ=+0.14%/mes, t=7 → media significativa (inflación promedio 2002-2024)
- Modelo: ARI(1,1) con media

---

### Paso 5 — Estimación y presentación

**Ciclo `mNN.pre` → `m(NN+1)`**:

```python
from fue.report import write_pre

# 1. Guardar modelo estimado como .pre
write_pre(m_fitted, "cases/SERIE/SERIE_mNN.pre")

# 2. Cargar .pre del modelo anterior como punto de partida
ts, m_init = fue.load("cases/SERIE/SERIE_mNN.pre")

# 3. Construir modelo siguiente añadiendo la modificación
m_next = fue.Model(ts, ..., ar=[[-0.35]], ar_free=[[True]],
                   mu=0.0014, estimate_mu=True,
                   interventions=m_init.interventions)
m_next.fit()
write_pre(m_next, "cases/SERIE/SERIE_m(NN+1).pre")
```

**Presentación del modelo**: siempre incluir:
1. Gráfico residuos + ACF/PACF (`plot_combined`)
2. Histograma (`plot_histogram`)
3. **Ecuación del modelo en Unicode** — usar `art.describe.model_equation`:

```python
from art.describe import model_equation
print(model_equation(ts, m_fitted))
```

Produce la forma BJ-T completa con coeficientes, errores estándar y estadísticos:
```
(1)  ln Xₜ = Dₜ + Nₜ          ← parte determinista (intervenciones + armónicos)
(2)  ∇(1 − φ₁B)(Nₜ − μ) = aₜ  ← ecuación de ruido (ARMA + media)
σ̂ₐ = ...   ℓ = ...   AIC = ...   BIC = ...
```
Visible directamente en Claude Code (terminal Unicode).

**Indexación `at=` en fue**: **0-based** (at=0 = primera obs).
Para (año y, mes m) con serie iniciando en (2002,1):
```python
at = (y - 2002)*12 + (m - 1)   # 0-based
```

---

### Paso 6 — Diagnóstico de residuos

- `plot_combined(residuos)` — serie + ACF/PACF: buscar Q(k) no significativo
- `plot_histogram(residuos)` — normalidad: JB+p-valor
- Outliers > 2σ → nueva intervención → ciclo `mNN.pre` → `m(NN+1)`

**Lección WTI** (jun-2026): escalones consecutivos (at=218,219,220 para crash COVID
mar-abr-may 2020) tienen multicolinealidad alta. Un t bajo no implica que el escalón
sea prescindible — revisar los residuos antes de eliminar.

---

### Sistema de control de cambios por caso (jun-2026)

Cada caso de análisis BJ tiene su directorio en `art-python/cases/SERIE/`:

```
cases/
  IPC_ES/
    IPC_ES_m00.pre   — armónicos base (sin ARMA, sin intervenciones)
    IPC_ES_m01.pre   — + intervenciones outliers
    IPC_ES_m02.pre   — + AR(1) + media
    CHANGELOG.md     — control de cambios modelo a modelo
```

**`CHANGELOG.md`** documenta por cada `mNN`:
- Especificación (qué se añadió/eliminó respecto al anterior)
- Parámetros estimados clave
- Diagnóstico (σ̂, Q, JB)
- Outliers restantes
- Próximos pasos

**Principio**: cada `.pre` es el punto de partida del siguiente modelo.
Los parámetros estimados en `mNN` se convierten en valores iniciales de `m(NN+1)`,
garantizando convergencia rápida y trazabilidad completa del proceso de refinamiento.

---

## Arquitectura de servidores de datos, gráficos y modelos (jun-2026)

### Motor de datos — fue

```
Entrada         Tipo                    Función
──────────────────────────────────────────────────────────────────
array/CSV/xlsx  → fue.TimeSeries        .from_array / .from_csv / .from_pandas
.inp / .pre     → (TimeSeries, Model)   fue.inp.load(path)   ← _InpParser.parse()
                                        at= en .inp/pre es 1-based → at_0 = at_1-1
                                        Model no estimado; .fit() para estimar

Propiedades clave de fue.TimeSeries:
  .data  : np.array   (valores en niveles tal cual se cargan)
  .freq  : int        (1=anual, 4=trim., 12=mensual)
  .start : (year, period)   1-based
  .name  : str

Nota: .residuals devuelve TimeSeries sin .start correcto → usar _resid_start(model)
```

### Motor de modelos — fue.Model

```
Construcción        Helpers ART              Parámetros clave
─────────────────────────────────────────────────────────────────
fue.Model(ts, ...)  _build_inp(...)          d, D, boxlam, ar, ma, ar_s, ma_s
                    _build_arma_on_model(m)  interventions (cos/sin/step/pulse)
                                             estimate_mu, ifadf

Estimación:   m.fit()  →  C engine MVENC  →  m._result: FitResult
Resultados:   m.residuals / .params / .std_errors / .aic / .bic / .sigma2

Serialización:
  write_pre(m, path)   →  .pre  (parámetros estimados como valores iniciales)
  fue.load(path)       ←  .pre / .inp  (Model sin estimar)

Workaround obligatorio (bug C backend):
  Si p=0 y q=0: añadir AR(1) φ=0 fijo para evitar crash del estimador C.
  _build_inp y _build_arma_on_model lo aplican automáticamente.

Bug conocido (fue/TODO.md):
  ar_s (P≥1) + ma_s (Q≥1) simultáneos → crash C. Solo P>0 ó Q>0, no ambos.
```

### Motor de gráficos — pyfug

```
Tipo entrada    Preparación ART             Función pyfug              Output
────────────────────────────────────────────────────────────────────────────────
fue.TimeSeries  _pyfug_from_fue(ts)         plot_mean_deviation_pair   PNG b64 (λ)
numpy + meta    _pyfug_ts(w, freq, start)   plot_combined(pf)          PNG b64 (serie+ACF+PACF)
residuos        _pyfug_ts(r, f, _resid_start(m))  plot_combined(pf)  PNG b64 (diagnosis)
residuos        idem                        plot_histogram(pf)         PNG b64 (histograma)

Regla crítica: pyfug opera sobre .data tal cual — NO diferencia internamente.
  plot_combined(d=, ds=) acepta esos params pero los ignora.
  ART aplica boxcox_transform + apply_differences ANTES de crear pyfug.Tseries.

Figuras internas ART (sin equivalente en pyfug, quedan en matplotlib):
  describe_unit_root        →  tabla coloreada ADF/KPSS
  describe_prelim_scan      →  serie tipificada + barras contrib. ACF outliers
  describe_seasonal_params  →  barras cos/sin ± 2SE por armónico
  _plot_series_at_d         →  [PENDIENTE migrar a pyfug — ver §Optimizaciones]
```

### Bridge fue ↔ pyfug (describe.py:53–78)

```python
# Array numpy → pyfug.Tseries
def _pyfug_ts(data, freq, start, name) -> Tseries

# fue.TimeSeries → pyfug.Tseries (datos en niveles)
def _pyfug_from_fue(ts) -> Tseries

# Start correcto para residuos (fue.TimeSeries.residuals no propaga start)
def _resid_start(model) -> tuple:
    n_skip = model.d + model.D * freq
    off    = (start[1] - 1) + n_skip
    return (start[0] + off // freq, off % freq + 1)
```

### Retorno al MCP — Description

```python
@dataclass
class Description:
    summary    : str        # markdown análisis para el LLM
    figure_b64 : str|None   # ACF/PACF o figura principal (PNG base64)
    recommendation: str     # próxima decisión sugerida
    data: dict              # {
                            #   "hist_b64": str|None,     ← histograma pyfug
                            #   "d", "D", "lam": ...,
                            #   "suggestions": [...],     ← candidatos ARMA
                            #   "outliers": [...],        ← prelim scan
                            # }

# Cada MCP tool devuelve:
[TextContent(summary + recommendation),
 ImageContent(figure_b64),        ← ACF/PACF
 ImageContent(data["hist_b64"])]  ← histograma (cuando disponible)
```

---

## Gráficos pyfug en el flujo

| Paso | Preparación | Función pyfug |
|------|------------|--------------|
| 1. λ | `_pyfug_from_fue(ts)` | `plot_mean_deviation_pair(pf, name)` |
| 2–3. Serie diferenciada | `boxcox_transform + apply_differences + new_start` | `plot_combined(pf)` |
| 4. ARMA sobre residuos | `_pyfug_ts(resid, freq, _resid_start(m))` | `plot_combined(pf, d=0)` |
| Histograma residuos | idem | `plot_histogram(pf, d=0)` |

```python
# Retardos por defecto (pyfug)
nlags = max(10, 3 * (freq + 1))   # 39 mensual, 15 trimestral, 10 anual
```

---

## Optimización de flujos — tokens y tiempo (pendiente)

### Ineficiencias actuales

**1. `_plot_series_at_d` — duplicación + matplotlib interno**

`guided_identification` calls 2 y 3 usan `_plot_series_at_d`, que reimplementa
manualmente lo que pyfug ya hace en `plot_combined`. ~110 líneas duplicadas.

```
_plot_series_at_d(ts, lam, d)
  → boxcox manual (lam=0 → log, else → (x^lam-1)/lam)
  → np.diff(y) d veces
  → fue.diagnostics.acf / pacf
  → fue.plots._draw_acf_panel  (privado de fue)
  → matplotlib figura propia
```

**Solución**: reemplazar con `_pyfug_ts(w, freq, start) + plot_combined(pf)`.
Mismo output, cero código duplicado, coherencia visual con el resto del flujo.

**2. Re-estimación en cada llamada MCP**

`_load_fitted(path)` = `fue.load(path)` + `m.fit()`. Cada tool que necesita
el modelo estimado lo re-estima desde cero aunque el `.pre` tenga parámetros.

Impacto: estimación MVENC ≈ 0.1-2s por modelo (C backend); en el ciclo de
outliers (5-20 rondas) esto suma. Sin cache entre llamadas MCP.

**Solución mínima**: leer parámetros del `.pre` como valores fijos cuando todos
los `free=False` (forecast mode). Para el caso guiado no aplica directamente,
pero documentar como limitación.

**3. Dos imágenes por llamada de diagnosis**

`estimate_and_diagnose`, `confirm_and_estimate`, `suggest_intervention_form`
devuelven ahora `[Text, ImageContent(ACF), ImageContent(hist)]`.
Cada imagen PNG base64 ≈ 15-40 KB = 20.000-55.000 tokens.
En el ciclo de outliers (10+ rondas) esto supone 200.000-550.000 tokens solo en imágenes.

**Solución**: añadir parámetro `include_histogram: bool = False` a estas tools.
El histograma solo es necesario en el diagnóstico FINAL, no en cada ronda del ciclo.

**4. `describe_diagnosis` llama al estimador dos veces vía model_equation**

`describe_diagnosis` llama `model_equation(model.series, model)` que puede
redundar con accesos a `model._result` ya disponibles.
Impacto menor pero documentar.

**5. Coste total tokens por análisis completo (estimación)**

| Fase | Tools | Imágenes | Tokens imagen aprox. |
|------|-------|----------|---------------------|
| Identificación (calls 1-4) | 4 | 1×call ≈ 1-2 imgs | 40-80 K |
| m00 estimación | 1 | 2 imgs (ACF+hist) | 40-80 K |
| Ciclo outliers × N rondas | N×2 | 2 imgs/ronda | 40-80 K × N |
| Modelo final | 1 | 2 imgs | 40-80 K |
| Refinamiento (G, H, MEG) | 3 | 1-2 imgs/tool | 40-120 K |
| **Total (N=10 rondas)** | ~20 | ~28 imgs | **~800 K tokens** |

### Acciones recomendadas (por impacto)

- [ ] **Alta**: reemplazar `_plot_series_at_d` con pyfug `plot_combined`
      (elimina ~110 líneas de código interno de fue, coherencia visual)
- [ ] **Alta**: añadir `include_histogram: bool = False` a `confirm_and_estimate`
      y `suggest_intervention_form` — histograma solo en diagnosis final
- [ ] **Media**: en `guided_identification` call 3 (HAC seasonality), no mostrar
      imagen de seasonality si el analista ya confirmó d — se puede omitir
- [ ] **Media**: documentar el bug P+Q simultáneos en fue C backend en CHANGELOG
      y en la docstring de `confirm_and_estimate`
- [ ] **Baja**: añadir `include_histogram` a `estimate_and_diagnose` también

---

## Pendiente

- [ ] **Bloque M**: `_plot_series_at_d` → migrar a pyfug (ver §Optimizaciones)
- [ ] **Bloque M**: `seasonality_form="deterministic"|"multiplicative"` en
      `guided_identification` call 3 como parámetro explícito (no solo texto)
- [ ] **Pruebas de raíz unitaria**: integrar ADF/KPSS/Shin-Fuller en el flujo
- [ ] **Notebook de demostración**: flujo completo IPC_DE con pyfug + fue
