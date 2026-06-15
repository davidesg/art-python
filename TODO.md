# art-python — TODO

## Filosofía: ART simple + Claude como analista BJ

### Modelo de colaboración (documentado en sesión jun-2026)

La experiencia con IPC_DE, IPC_FR, IPC_ES y WTI mostró que Claude funciona bien
como analista Box-Jenkins independiente, usando directamente `pyfug` y `fue` como
instrumentos. Por eso ART no necesita ser un agente complejo que automatice el
flujo entero.

**División de responsabilidades**:

| Capa | Qué hace | Herramienta |
|------|----------|-------------|
| **pyfug** | Gráficos Jenkins-Treadway (serie, ACF/PACF, histograma, media-σ) | Python + matplotlib |
| **fue** | Estimación ML exacta ARIMA + intervenciones | Python (+ C opcional) |
| **ART** | Pruebas formales, selección de modelo, criterios de parada | Python |
| **Claude** | Identificación BJ, interpretación, refinamiento iterativo | LLM |

**Lo que ART debe proveer** (instrumentos, no automatización):
- `plot_combined`, `plot_acf_pacf`, `plot_histogram`, `plot_mean_deviation` (pyfug)
- `fue.Model`, `add_intervention`, `m.fit()` (fue)
- Pruebas de raíz unitaria: ADF, KPSS (identificación inicial), Shin-Fuller (contraste formal)
- Pruebas de diagnóstico: Q(k), JB, outlier detection
- Criterios de información: AIC, BIC, log-verosimilitud
- Tabla de correlaciones de parámetros (sobreparametrización)

**Lo que Claude hace** como analista:
- Interpreta ACF/PACF → sugiere p, q, P, Q
- Juzga estacionariedad, estacionalidad
- Propone y descarta intervenciones
- Detecta problemas (multicolinealidad entre escalones, outliers extremos)
- Toma decisiones de refinamiento iterativo

---

## Flujo BJ documentado (sesión IPC_DE / WTI, jun-2026)

### Identificación (demostrado sobre IPC_DE)

1. **Nivel** (d=0, ds=0): `plot_combined` → ACF decae lentamente → d=1
2. **∇x** (d=1, ds=0): `plot_combined` → patrón estacional en ACF → D=1
3. **∇_s x** (d=0, ds=1): `plot_combined` → ACF decae → ∇∇_s
4. **∇∇_s x** (d=1, ds=1): `plot_combined` → ACF(12)=-0.40*, PACF(12)=-0.43* → SMA(1)
5. **Modelo sugerido**: ARIMA(0,1,0)(0,1,1)₁₂
6. **Histograma**: `plot_histogram` con S, K, JB+p-valor

### Estimación + refinamiento (demostrado sobre WTI)

1. `fue.Model(ts, boxlam=0.0, d=1, D=0, ar=[[...]])` + `.fit()`
2. Residuos: `np.array(m.residuals.data)` — revisar Q(k), JB, outliers >2σ
3. Añadir intervenciones con `m.add_intervention('step', at=...)` para outliers
4. Iterar hasta diagnosticos OK
5. Verificar significación de cada parámetro (t > 2)

**Lección WTI** (jun-2026): escalones consecutivos muy próximos (at=218,219,220 para
el crash COVID de mar-abr-may 2020) presentan multicolinealidad alta. Un escalón con
t bajo puede ser necesario para la estabilidad del ajuste — no eliminar
mecánicamente.

---

## Usar pyfug para gráficos de identificación

### Gráficos pyfug a usar

| Situación | Función pyfug |
|-----------|--------------|
| Identificación inicial | `plot_combined(ser, ...)` |
| Análisis ACF detallado | `plot_acf_pacf(ser, ...)` |
| Normalidad de residuos | `plot_histogram(ser, ...)` |
| Selección Box-Cox | `plot_mean_deviation(ser, ...)` ← **pendiente en pyfug** |
| Serie sola | `plot_series(ser, ...)` |

### Número de retardos por defecto (ya implementado en pyfug)

```python
nlags = max(10, 3 * (freq + 1))
# mensual (s=12): 39
# trimestral (s=4): 15
# anual/semestral: 10
```

### Instalación pyfug

```bash
pip install -e /home/david/Dropbox/SRC/atws/fug/pyfug
```

---

## Usar fue para estimación

ART identifica el modelo → FUE (`fue` Python) estima → pyfug produce gráficos
diagnósticos del modelo estimado.

```python
import fue
import numpy as np
from pyfug.graphics.combined import plot_combined
from pyfug.core import Tseries

ts, _ = fue.inp.load("serie.inp")

m = fue.Model(ts, boxlam=0.0, d=1, D=0, ar=[[-0.3]], ar_free=[[True]])
m = m.add_intervention('step', at=82)
m.fit()

resids = np.array(m.residuals.data)
# construir Tseries de residuos y llamar plot_combined(...)
```

---

## Pendiente

- [ ] **`plot_mean_deviation`**: implementar en pyfug (ver pyfug/TODO.md)
- [ ] **Pruebas de raíz unitaria**: integrar ADF/KPSS/Shin-Fuller en el flujo
- [ ] **Notebook de demostración**: flujo completo IPC_DE con pyfug + fue
