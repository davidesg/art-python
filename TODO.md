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

**Análisis de casos (jun-2026)**:

| Serie | Nivel m-dt | Log m-dt | Decisión | Razón |
|-------|-----------|----------|----------|-------|
| IPC_DE | nube casi horizontal, outlier 2022 en esquina sup-der | similar, sin cambio apreciable | **λ=0** | número índice (base 2015=100) |
| WTI | pendiente positiva visible (σ crece con μ) | nube dispersa sin pendiente | **λ=0** | precio commodity + evidencia empírica |

Para IPC_DE el m-dt no muestra heteroscedasticidad fuerte (la serie crece despacio
y de forma muy regular hasta 2022); la decisión λ=0 se apoya principalmente en la
naturaleza de índice. Para WTI la evidencia empírica es clara: el log estabiliza σ.

---

### Paso 2 — Diferenciación (d, D)

Sobre la serie transformada (`ln x` si λ=0):

1. **Nivel** `plot_combined(ln x)` → ACF decae lentamente → d=1
2. **∇ ln x** `plot_combined(∇ ln x)` → patrón estacional en ACF → D=1 (si aplica)
3. **∇_s ln x** `plot_combined(∇_s ln x)` → ACF decae regular → d=1
4. **∇∇_s ln x** `plot_combined(∇∇_s ln x)` → ACF/PACF → identificar p,q,P,Q

**IPC_DE** (mensual, freq=12): d=1, D=1 → ARIMA(0,1,0)(0,1,1)₁₂
**WTI** (mensual, freq=12): d=1, D=0 → AR(2) + escalones para outliers COVID/crisis

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
