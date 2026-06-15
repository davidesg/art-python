# art-python — TODO

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

### Paso 3 — Identificación ARMA

`plot_combined(∇∇_s ln x)` — ACF/PACF sobre la serie estacionaria.

Señales habituales:
- ACF(s) significativo, PACF(s) decae → SMA(1): θ_s < 0 si ACF(s) < 0
- ACF(1..p) significativo, PACF corta en p → AR(p)
- ACF y PACF decaen → ARMA(p,q)

---

### Paso 4 — Estimación

```python
m = fue.Model(ts, boxlam=0.0, d=1, D=1,
              ma_s=[[-0.4]], ma_s_free=[[True]])
m.fit()
resids = np.array(m.residuals.data)
npar = len(m.params)
```

---

### Paso 5 — Diagnóstico de residuos

- `plot_combined(residuos)` — serie + ACF/PACF: buscar Q(k) no significativo
- `plot_histogram(residuos)` — normalidad: JB+p-valor
- Outliers > 2σ → `m.add_intervention('step', at=...)` y reestimar

**Lección WTI** (jun-2026): escalones consecutivos (at=218,219,220 para crash COVID
mar-abr-may 2020) tienen multicolinealidad alta. Un t bajo no implica que el escalón
sea prescindible — revisar los residuos antes de eliminar.

---

## Gráficos pyfug en el flujo

| Paso | Función pyfug |
|------|--------------|
| 1. λ | `plot_mean_deviation_pair(ser, name="X")` |
| 2-3. d, D, ARMA | `plot_combined(ser, d=..., ds=..., title="...")` |
| 3b. ACF detallado | `plot_acf_pacf(ser, ...)` |
| 4. Histograma residuos | `plot_histogram(ser, ...)` |
| — Serie sola | `plot_series(ser, ...)` |

```python
# Número de retardos por defecto (pyfug)
nlags = max(10, 3 * (freq + 1))   # 39 mensual, 15 trimestral, 10 anual
```

---

## Pendiente

- [ ] **Pruebas de raíz unitaria**: integrar ADF/KPSS/Shin-Fuller en el flujo
- [ ] **Notebook de demostración**: flujo completo IPC_DE con pyfug + fue
