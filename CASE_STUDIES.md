# Casos de estudio — IPC mensual 8 países (2002-2019)

Series utilizadas en la tesis de Guerrero (2023) para modelización univariante de la
inflación mensual. Fuente: `/home/david/Dropbox/Inflation Volatility/Analisis/`.

---

## Estructura de directorios

```
{País}/
  univariate/
    sample_1.2002_12.2019/   (o Sample_2002_2019 para Alemania)
      X.0.inp  X.0.pre  ...  ← iteraciones del análisis (n=216)
      X.k.inp  X.k.pre  ...  ← modelo final univariante
  forecast/
      X.k.inp  X.k.pre  ...  ← modelo extendido para previsiones (n>216)
```

Excepciones:
- **Francia**: archivos univariantes en `France/` raíz; forecast en `France/forecast/`
- **Japón**: directorio padre `Japan/sample_2002_2020/`

---

## Patrón universal

Todos los 8 países comparten la misma estructura de especificación:

| Parámetro | Valor | Decisión |
|-----------|-------|----------|
| λ (Box-Cox) | 0.00 | transformación logarítmica siempre |
| d (diferencias regulares) | 1 | Decisión A |
| D (diferencias anuales) | 0 | Decisión B1: estacionalidad determinista |
| s (frecuencia) | 12 | mensual |
| Variables deterministas | 10 armónicos (cos/sin f=1..5) + ≥1 atípico aditivo (alter) |
| Componente ARMA | solo AR, sin MA |

La opción D=1 (estacionalidad estocástica) fue explorada únicamente en Alemania G.0
y descartada en todas las iteraciones siguientes.

---

## Modelos por país

### España (Spain)

**Rutas:** `Spain/univariate/sample_2002_2019/` → `Spain/forecast/`

| Iteración | n | AR | aAR | det | μ | Cambio |
|-----------|---|----|-----|-----|---|--------|
| S.1 | 216 | lag 1 | – | 11 | 0 | modelo inicial (alter sin estimar) |
| S.2 | 216 | lag 1 | – | 11 | 0.1548 | alter obs 128 (sep-2012, subida IVA) |
| S.2.1 | 216 | lag 1 | – | 11 | 0.1545 | refinamiento menor |
| S.3 | 216 | lag 1 | – | 11 | 0.1545 | convergencia |
| **Forecast S.2** | **279** | lag 1, φ=0.4027 | – | 11 | 0.1545 | serie extendida a 2025 |

**Modelo final:** `ARIMA(1,1,0)(0,0,0)_12` + 10 armónicos + alter(128)  
**Archivo ART:** `Spain/univariate/sample_2002_2019/S.2.pre`

---

### Canadá (Canada)

**Rutas:** `Canada/univariate/sample_1.2002_12.2019/` → `Canada/forecast/`

| Iteración | n | AR | aAR | det | μ | Cambio |
|-----------|---|----|-----|-----|---|--------|
| CA.0 | 216 | lag 1 | – | 11 | 0 | modelo inicial |
| **CA.1** | **216** | **lag 2** | – | 11 | 0.060 | cambio a AR en lag 2 |
| **Forecast CA.1** | **292** | lag 2, φ=0.060 | – | 11 | 0.060 | extendido |

**Modelo final:** `ARIMA(0,1,0)(0,0,0)_12` con AR solo en lag 2 + 10 armónicos + alter  
**Archivo ART:** `Canada/univariate/sample_1.2002_12.2019/CA.1.pre`

---

### Zona Euro / EMU

**Rutas:** `EMU/univariate/sample_1.2002_12.2019/` → `EMU/forecast/`

| Iteración | n | AR | aAR | det | μ | Cambio |
|-----------|---|----|-----|-----|---|--------|
| EU.1 | 216 | lag 1 | – | 11 | 0 | modelo inicial |
| **EU.2** | **216** | **lag 1** | **lag 1 (=B¹²)** | 11 | 0.132 | añade AR estacional |
| EU.3 | 216 | lag 1 | lag 1 | 11 | 0.133 | refinamiento menor |
| **Forecast EU.2** | **293** | lag 1, φ=0.166 | lag 1, Φ=0.290 | 11 | 0.290 | extendido |

**Modelo final:** `ARIMA(1,1,0)(1,0,0)_12` + 10 armónicos + alter  
(aAR lag 1 en dominio anual = AR en lag 12 en dominio regular)  
**Archivo ART:** `EMU/univariate/sample_1.2002_12.2019/EU.2.pre`

---

### Alemania (Germany)

**Rutas:** `Germany/univariate/Sample_2002_2019/` → `Germany/forecast/`

| Iteración | n | AR | aAR | det | μ | Cambio |
|-----------|---|----|-----|-----|---|--------|
| G.0 | 216 | lag 1 | – | **0** | 0.115 | **D=1**, sin armónicos (test estoc.) |
| G.1 | 216 | lag 1 | – | 11 | 0 | vuelta a D=0, armónicos |
| **G.2** | **216** | **lag 2** | – | 11 | 0.115 | cambia a AR en lag 2 |
| G.2.1 | 216 | lag 2 | – | 11 | 0.114 | refinamiento |
| G.3 | 216 | lags 1+2 | – | 11 | 0.114 | prueba AR(1,2) |
| G.3.1 | 216 | 2×AR(1) | – | 11 | 0.115 | factores separados |
| G.4 | 216 | lags 1+2 | lag 1 | 11 | 0.115 | añade aAR |
| G.5 | 216 | lag 2 | lag 1 | 11 | 0.114 | reduce AR regular |
| G.6 | 216 | – | lag 1 | 11 | 0.114 | solo aAR |
| **Forecast G.2** | **290** | lag 2, φ=−0.299 | – | 11 | 0.115 | extendido |

**Nota:** G.0 es el único caso con D=1 en toda la colección. Fue descartado.  
**Modelo final:** AR solo en lag 2 (sin aAR).  
**Archivo ART:** `Germany/univariate/Sample_2002_2019/G.2.pre`

---

### Estados Unidos (USA)

**Rutas:** `USA/univariate/sample_1_2002_12_2019/` → `USA/forecast/`

| Iteración | n | AR | aAR | det | μ | Cambio |
|-----------|---|----|-----|-----|---|--------|
| US.0 | 216 | lag 1 | – | 11 | 0.115 | d=0 (test sin diferenciar) |
| US.1 | 216 | lag 1 | – | 11 | 0.115 | d=1 |
| US.2 | 216 | lag 2 | – | 11 | 0.174 | AR en lag 2 |
| US.3 | 216 | lag 2 | lag 2 | 11 | 0.174 | añade aAR en lag 2 |
| US.4 | 216 | lag 2 | lag 2 | 11 | 0.174 | refinamiento |
| **US.5** | **216** | **lag 2** | – | **13** | 0.186 | elimina aAR, añade impulse(9,2005)+step(10,2008) |
| **Forecast US.3** | **292** | **lag 1** | – | **11** | 0.174 | simplificado para previsión |

**Nota:** US.5 tiene 3 intervenciones: alter + impulse(sep-2005) + step(oct-2008, crisis Lehman).  
El modelo de previsión (US.3 forecast) revierte a AR(1) y solo conserva el alter.  
**Archivo ART (univariante):** `USA/univariate/sample_1_2002_12_2019/US.5.pre`

---

### Francia (France)

**Rutas:** `France/` (raíz) → `France/forecast/`

| Iteración | n | AR | aAR | det | μ | Cambio |
|-----------|---|----|-----|-----|---|--------|
| F.1 | 216 | lag 1 | – | 11 | – | modelo inicial |
| **F.2** | **216** | **–** | **lag 1** | 11 | 0.113 | sustituye AR por aAR |
| **F.3 (forecast)** | **288** | **lag 1** | **lag 1** | 11 | 0.112 | añade AR(1) para previsión |

**Nota:** F.2 es inusual — usa solo AR estacional (aAR en lag 12), sin AR regular.  
El modelo de previsión F.3 añade AR(1) al modelo univariante.  
**Archivo ART:** `France/F.3.pre`

---

### Reino Unido (UK)

**Rutas:** `UK/Analisis/sample_1.2002_12.2019/` → `UK/Forecast/`

| Iteración | n | AR | aAR | det | μ | Cambio |
|-----------|---|----|-----|-----|---|--------|
| UK.1 | 216 | lag 1 | – | 11 | 0 | modelo inicial |
| UK.2 | 216 | lag 1 | – | 11 | 0.170 | estima μ |
| **UK.3** | **216** | **lag 2** | – | 11 | 0.170 | cambia a AR en lag 2 |
| UK.4 | 216 | lag 2 | lag 2 | 11 | 0.169 | añade aAR (descartado) |
| **Forecast UK.3** | **292** | lag 2, φ=0.210 | – | 11 | 0.170 | extendido |

**Modelo final:** AR solo en lag 2.  
**Archivo ART:** `UK/Analisis/sample_1.2002_12.2019/UK.3.pre`

---

### Japón (Japan)

**Rutas:** `Japan/sample_2002_2020/univariate/` → `Japan/sample_2002_2020/forecast/`

| Iteración | n | AR | aAR | det | μ | Cambio |
|-----------|---|----|-----|-----|---|--------|
| J.0 | 216 | – | – | – | – | estructura inicial (sin estimar) |
| J.1 | 216 | lag 1 | – | 11 | 0 | primer modelo estimado |
| J.2 | 216 | lag 1 | – | 12 | 0.022 | añade step(abr-2014, subida IVA) |
| J.3 | 216 | lag 1 | – | 12 | 0.013 | refinamiento |
| J.4 | 216 | lag 1 | – | 12 | 0 | ajuste μ |
| **J.5** | **216** | **lag 1** | – | **11** | 0 | elimina step, solo alter |
| **Forecast J.2** | **215** | lag 1 | – | 12 | 0.013 | step 4 2014 conservado |
| Forecast J.3 | 216 | lag 1 | – | 12 | 0.013 | λ=1 (niveles, experimental) |

**Nota:** μ≈0 es coherente con la deflación/inflación nula de Japón en 2002-2019.  
El step(abr-2014) corresponde a la subida del consumo del 5% al 8%.  
J.5 elimina el step en la muestra pero el forecast J.2 lo conserva.  
**Archivo ART:** `Japan/sample_2002_2020/univariate/J.5.pre`

---

## Resumen de modelos finales (n=216)

| País | Archivo .pre | d | D | AR | aAR | det | μ |
|------|-------------|---|---|----|-----|-----|---|
| España | `Spain/.../S.2.pre` | 1 | 0 | lag 1 | – | 11 | 0.155 |
| Canadá | `Canada/.../CA.1.pre` | 1 | 0 | lag 2 | – | 11 | 0.060 |
| EMU | `EMU/.../EU.2.pre` | 1 | 0 | lag 1 | lag 1 | 11 | 0.132 |
| Alemania | `Germany/.../G.2.pre` | 1 | 0 | lag 2 | – | 11 | 0.115 |
| USA | `USA/.../US.5.pre` | 1 | 0 | lag 2 | – | 13 | 0.186 |
| Francia | `France/F.3.pre` | 1 | 0 | lag 1 | lag 1 | 11 | 0.113 |
| UK | `UK/.../UK.3.pre` | 1 | 0 | lag 2 | – | 11 | 0.170 |
| Japón | `Japan/.../J.5.pre` | 1 | 0 | lag 1 | – | 11 | ≈0 |

**Patrón dominante:** AR solo en lag 2 (Canadá, Alemania, UK, USA).  
**Con AR estacional:** EMU y Francia (AR en lag 12).  
**AR en lag 1:** España y Japón.

---

## Uso como casos de prueba del API ART

Todos los `.pre` son cargables con `fue.load(path)` que devuelve `(TimeSeries, Model)`.

```python
import fue
import art

# Cargar serie + modelo estimado
ts, model = fue.load("Spain/univariate/sample_2002_2019/S.2.pre")

# --- Etapa 1: Identificación ---
bc = art.boxcox_selection(ts)
# Esperado: λ=0 claramente mejor

seasonal = art.detect_seasonality(ts, d=1)
# Esperado: seasonal=True, p<0.001, 10 frecuencias significativas

listing = art.identification_listing(ts, d=1, max_d=2, max_D=0, lam=0.0)
# Esperado: 3 paneles (d=0,1,2), D=0 forzado

specs = art.suggest_orders(ts, d=1, D=0, lam=0.0)
# Esperado: AR(1) en top-3, similitud >0.5

# --- Etapa 3: Diagnosis ---
# (pendiente: art.diagnose(model, ts))
```

### Casos de prueba prioritarios

1. **España S.2** — caso más documentado, iteraciones claras, outlier bien localizado
2. **Alemania G.0 vs G.2** — comparación D=1 vs D=0 para validar `detect_seasonality`
3. **EMU EU.2** — validar que `suggest_orders` propone P=1 (aAR)
4. **Japón J.5** — μ≈0, validar que el API no impone tendencia espuria

### Tests de regresión sugeridos

```python
# tests/real_cases/test_case_studies.py

MODELS = {
    "Spain":   ("Spain/univariate/sample_2002_2019/S.2.pre",
                dict(d=1, D=0, lam=0.0, n_harmonics=5, ar_lags=[1])),
    "Canada":  ("Canada/univariate/sample_1.2002_12.2019/CA.1.pre",
                dict(d=1, D=0, lam=0.0, n_harmonics=5, ar_lags=[2])),
    "EMU":     ("EMU/univariate/sample_1.2002_12.2019/EU.2.pre",
                dict(d=1, D=0, lam=0.0, n_harmonics=5, ar_lags=[1], aar_lags=[1])),
    "Germany": ("Germany/univariate/Sample_2002_2019/G.2.pre",
                dict(d=1, D=0, lam=0.0, n_harmonics=5, ar_lags=[2])),
    "USA":     ("USA/univariate/sample_1_2002_12_2019/US.5.pre",
                dict(d=1, D=0, lam=0.0, n_harmonics=5, ar_lags=[2], n_outliers=3)),
    "France":  ("France/F.3.pre",
                dict(d=1, D=0, lam=0.0, n_harmonics=5, ar_lags=[1], aar_lags=[1])),
    "UK":      ("UK/Analisis/sample_1.2002_12.2019/UK.3.pre",
                dict(d=1, D=0, lam=0.0, n_harmonics=5, ar_lags=[2])),
    "Japan":   ("Japan/sample_2002_2020/univariate/J.5.pre",
                dict(d=1, D=0, lam=0.0, n_harmonics=5, ar_lags=[1])),
}

BASE = pathlib.Path("/home/david/Dropbox/Inflation Volatility/Analisis")

@pytest.mark.parametrize("country,path,expected", [
    (c, BASE / p, e) for c, (p, e) in MODELS.items()
])
def test_seasonality_detected(country, path, expected):
    ts, _ = fue.load(path)
    result = art.detect_seasonality(ts, d=expected["d"])
    assert result.seasonal, f"{country}: estacionalidad no detectada"

@pytest.mark.parametrize("country,path,expected", [...])
def test_suggest_orders_top1(country, path, expected):
    ts, _ = fue.load(path)
    specs = art.suggest_orders(ts, d=expected["d"], D=expected["D"],
                               lam=expected["lam"])
    top = specs[0]
    assert top.p > 0 or top.P > 0, f"{country}: top-1 no tiene componente AR"
```

---

## Decisiones metodológicas observadas

1. **D=0 universal**: todos los países usan estacionalidad determinista (10 armónicos).
   Única excepción explorada: Alemania G.0 con D=1, descartado.

2. **Sin componentes MA**: ningún modelo final usa MA regular ni MA estacional.
   El proceso de diferenciación + media elimina la necesidad de MA.

3. **AR en lag 2 vs lag 1**: predomina AR en lag 2 (4 países: CA, DE, UK, US).
   Interpretación: el componente estacional absorbe la autocorrelación de lag 12;
   la dinámica residual aparece principalmente en lag 2.

4. **AR estacional (aAR)**: EMU y Francia necesitan AR en lag 12.
   Pueden indicar inercia en la transmisión de precios a nivel de zona.

5. **Atípicos**: todos los países tienen al menos 1 alter en el modelo.
   USA es el más complejo (3 intervenciones). Las fechas corresponden a eventos
   fiscales o macroeconómicos verificables (IVA, crisis financiera).

6. **μ (media)**: refleja la tasa de inflación tendencial del período.
   Japón≈0 (deflación), España 0.15% mensual ≈ 1.8% anual.
