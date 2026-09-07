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

---

# CASO DE REFERENCIA PARA EL DESARROLLO DE MEG Y SHIN-FULLER

## UEM HICP agregado, 2002:01–2019:12 (n=216)

**Ruta:** `~/Dropbox/SRC/DVR/cases/UEM_HCPI_0219/`
**Guion:** `work/UEM_HCPI_0219_guion.json` — 22 entradas: 18 modelos, 4 nodos de
decisión, 2 callejones marcados. **El grafo es la pieza que hay que leer**
(`guion_map`); el recorrido no es una línea, y ahí está lo que enseña.

Marcado como caso de referencia el 2026-09-06. Es **difícil**, y esa es la razón
de conservarlo: los ocho casos país de la tesis de arriba resuelven todos con
B1 —estacionalidad determinista, D=0, diez armónicos— y con la única exploración
de D=1 (Alemania G.0) descartada. El agregado UEM **no admite ninguna de las dos
rutas enteras**: la respuesta es por frecuencia, que es exactamente la forma
canónica de Abraham y Box a la que el MEG existe para llegar, y que el binomio
B1/B2 no sabe expresar.

### Modelo final adoptado — m16, por parsimonia

```
  ln HICPt = Dt + Nt

  Dt:  + 0.0509 (-1)^t  - 0.3023 cos(pi/6 t) - 0.0838 sin(pi/6 t)
       + 0.0601 cos(pi/2 t) - 0.0327 sin(pi/2 t)
       + 0.0720 cos(5pi/6 t) + 0.0380 sin(5pi/6 t)  + 0.1368 xi_Easter

  (1 - 0.3403 B) [ (1-B+B2)_f=2 (1+B+B2)_f=4 grad Nt - 0.3988 ]
        = (1 + B + 0.8663 B2)_f=4 (1 - B + 0.9150 B2)_f=2 at

  sigma_a = 0.1846%   l = 53.40   AIC = -82.80   BIC = -42.58
  Q p-min 0.371 OK   JB 2.989 p=0.224 OK   1 residuo |z|=3.03 (lo esperado con n=215, BUG-0105)
```

**UN solo parametro AR regular.** Shin-Fuller Phi_1u = 41.410 (crit. 1% = 3.43).
d=1 cerrado por ambos lados tres veces (sub-diferenciacion LR = 26.001). Testigos
MA_f invertibles con LR = 47.628 (f=4) y 20.030 (f=2) contra critico 2.07: las
raices unitarias estacionales son genuinas, no cuasi-cancelaciones.

**Veredicto estacional:** f=2 (periodo 6) y f=4 (periodo 3) **estocasticas**;
f=1, 3, 5 y 6 **deterministas**.

### El gemelo m17, y por que el resultado son los dos

`m17 = m16 x (1 - 0.0956 B^12)`. **Un solo parametro de diferencia**, y todo lo
demas identico. La verosimilitud no distingue entre ellos (LR = 1.56, 1 g.l.,
p = 0.212), el BIC prefiere m16 (-42.58 frente a -38.78) y sigma_a apenas se
mueve (0.1846% frente a 0.1839%). Por Ockham se adopta m16.

**Pero el barrido MEG sobre m16 declara f=1 y f=5 estocasticas, y no se
adoptan.** No es una omision: es el resultado del experimento de sensibilidad.
Con el SAR devuelto (m17) las dos revierten a deterministas y las otras dos se
refuerzan. m16 **no esta cerrado por el MEG en sus propios terminos**: lo esta
DADO m17. Quien corra `formal_tests` sobre `m16.pre` sin este contexto recibira
la instruccion de reformular f=1 y f=5, y seguirla seria un error.

Por eso el resultado de este caso **son los dos modelos juntos**, y ninguno por
separado. El veredicto a reportar: f=2 y f=4 estocasticas de forma robusta;
f=3 y f=6 deterministas de forma robusta; f=1 y f=5 deterministas pero
**sensibles a la especificacion del ruido** -- y eso se declara, no se esconde.

Coherente con el punto 4 de las decisiones metodologicas de la tesis --«EMU y
Francia necesitan AR en lag 12»--: el SAR_12 no entra en el modelo final, pero
es la pieza que decide el veredicto estacional, por una razon que alli no podia
verse (hallazgo 1).

### Seis hallazgos para MEG / SF

1. **El veredicto del MEG es condicional al modelo de ruido, y lo es de forma
   decisiva.** m16 y m17 se diferencian en **un solo parámetro**: el SAR(1)₁₂ =
   0.0956. No es significativo (LR = 1.56, 1 g.l., p = 0.212), el BIC lo
   penaliza (−38.78 frente a −42.58) y σ̂ₐ apenas se mueve (0.1846 → 0.1839).
   Y sin embargo **decide el veredicto estacional**: sin él, f=1 pasa a
   estocástica (LR 1.814 → 2.743) y f=5 también (1.385 → 2.469), las dos
   cruzando el crítico 2.07. Un parámetro de estorbo que la verosimilitud no
   sabe decidir cambia la conclusión sustantiva. Mecánica: un operador en B¹²
   absorbe correlación estacional repartida por todas las frecuencias; al
   quitarlo, esa correlación se redistribuye y empuja los contrastes marginales
   por encima de su crítico. **Un ruido levemente infraespecificado sesga el
   DCD_f hacia «estocástico».**

2. **La contaminación cruzada entre frecuencias es real y bidireccional.** Tres
   barridos sobre el mismo caso:

   | f | m09 (nada adoptado) | m12 (f=4 adoptada) | m16 (f=2 y f=4, podado) | m17 (+SAR) |
   |---|---|---|---|---|
   | 1 | 3.672 estoc. | 0.639 determ. | 2.743 estoc. | 1.814 determ. |
   | 2 | 2.853 estoc. | **9.646** estoc. | — | — |
   | 4 | **23.885** estoc. | — | — | — |
   | 5 | 0.021 determ. | 0.753 determ. | 2.469 estoc. | 1.385 determ. |

   Adoptar f=4 **triplicó** la evidencia en f=2 y desactivó f=1. Barrer una vez
   sobre el modelo todo-determinista y adoptar en bloque habría dado un modelo
   distinto y peor.

3. **Un efecto de calendario móvil se disfraza de estacionalidad estocástica e
   infla el MEG.** Sin el regresor de Semana Santa, f=2 daba LR = 4.878 (por
   encima del crítico del 1 %); con él, 2.853 (entre el 5 % y el 1 %). Parte de
   la «estacionalidad estocástica» era Pascua. Y la Pascua no la puede capturar
   ningún armónico **por construcción** —el armónico es periódico y la Pascua se
   mueve entre marzo y abril—, así que resistió cuatro cambios estructurales
   seguidos: el retardo 14 de la ACF se movió de −0.192 a −0.179 a través de un
   AR(6), una factorización, una restricción de frecuencia y una reformulación
   estocástica, y sólo cedió con `easter=True` (t = 5.04, LR = 19.34, p = 1e−5).

4. **Convergencia entre la factorización de raíces y el MEG.** Las dos únicas
   frecuencias donde el AR(6) libre escondía factores AR(2) complejos —periodos
   estimados **6.64 ± 0.35** y **3.04 ± 0.08**— son exactamente las dos que el
   MEG declara estocásticas. Los factores amortiguados eran **la sombra
   estacionaria de las raíces unitarias**: al introducir la raíz unitaria en su
   frecuencia se marchitan (d 0.724 → 0.427 en f=4; 0.580 → 0.449 en f=2) y la
   LR anidada confirma que sobran (p = 0.164 y p = 0.103). El contraste de
   marchitamiento —dejar el AR_f puesto al adoptar la raíz unitaria, en vez de
   retirarlo— es barato, falsable y debería ser parte del protocolo.

5. **La t miente donde la LR no.** El SAR(1)₁₂ con t = 1.63 cuya retirada la LR
   **rechazó** con p = 0.0368: el error típico venía de una dirección que el
   BFGS apenas movió. En todo este caso la covarianza estuvo degradada
   (niter entre 6 y 23, hasta diez de diecisiete direcciones pegadas a la
   semilla 2/n), lo que además invalida el veredicto de
   `overparameterization_analysis` — una dirección plana devuelve varianza
   pequeña e infravalora a la vez errores típicos y correlaciones. **Con
   covarianza degradada, decidir sólo por LR.**

6. **El AR disperso «sólo en B^s» es una restricción no contrastada**, y este
   caso la cuantifica. Con Θ = θ^s, 1 − Θ·B^s = (1−θB)(1+θB+…+θ^{s−1}B^{s−1}):
   sus s raíces tienen **módulo idéntico** y frecuencias clavadas en múltiplos
   de 2π/s. En m02 los seis módulos salían 1.2684–1.2934 —casi iguales, y el
   LLM propuso imponerlo—; el analista lo paró. Estimado en forma factorizada,
   el AR(2) semianual da periodo 6.64 ± 0.35 frente al 6.00 que B⁶ habría
   fijado por decreto. La restricción conjunta a frecuencia estacional sí se
   sostiene (LR = 5.200, 2 g.l., p = 0.074), pero **contrastada**. Doctrina ya
   registrada como BUG-0095 (identificación) y BUG-0103 (superficie MCP).

### Defectos que este caso destapó

`BUG-0103` (el modelo factorizado no es construible desde la superficie MCP;
`ar_f` no está expuesto — los `.inp` factorizados de este caso se escribieron a
mano) · `BUG-0104` (el φ₁ derivado de un factor de frecuencia fija se imprime
como 1) · `BUG-0105` (un solo residuo |z|>3 declara no sostenible un modelo
aprobado; con n=215 la mediana del máximo |z| es 2.95) · `BUG-0106`
(`_reformulacion_desde` lee claves que la diagnosis no escribe: nunca ve fallar
la Q ni el JB) · `BUG-0107` (`export_guion` revienta si el guion tiene nodos de
decisión — por eso este caso no tiene informe HTML).
