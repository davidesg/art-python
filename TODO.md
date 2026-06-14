# art-python — TODO

## Usar pyfug para gráficos de identificación

Integrar `pyfug` (Jenkins-Treadway graphics) en el flujo BJ de identificación de ART,
sustituyendo los gráficos matplotlib ad-hoc actuales por los gráficos estandarizados
de pyfug.

### Flujo de identificación documentado (sesión IPC_DE, 2026-06-14)

El flujo que ART debe automatizar es el siguiente (demostrado manualmente sobre IPC_DE):

1. **Cargar serie** — desde `.inp`, Excel o pandas
2. **Nivel** (d=0, ds=0):
   - `plot_combined` → serie + ACF/PACF
   - ACF que decae lentamente → no estacionaria → aplicar diferencia
3. **Primera diferencia** (d=1, ds=0):
   - `plot_combined` → si ACF muestra patrón estacional → aplicar diferencia estacional
4. **Diferencia estacional** (d=0, ds=1):
   - `plot_combined` → si ACF todavía decae → no estacionaria regular
5. **Diferencia regular + estacional** (d=1, ds=1):
   - `plot_combined` → ACF/PACF → sugerir modelo ARIMA(p,d,q)(P,D,Q)_s
   - En IPC_DE: ACF(12)=-0.40*, PACF(12)=-0.43*, ACF(24)=-0.13* → SMA(1) → ARIMA(0,1,0)(0,1,1)₁₂
6. **Histograma** (`plot_histogram`) — estadísticos S, K, JB con p-valor
7. **ACF/PACF individual** (`plot_acf_pacf`) — para análisis detallado

### Gráficos pyfug a usar

| Situación | Función pyfug |
|-----------|--------------|
| Identificación inicial | `plot_combined(ser, ...)` |
| Análisis ACF detallado | `plot_acf_pacf(ser, ...)` |
| Normalidad de residuos | `plot_histogram(ser, ...)` |
| Serie sola | `plot_series(ser, ...)` |
| Box-Cox (futuro) | `plot_mean_deviation(ser, ...)` |

### Instalación pyfug

```bash
pip install -e /path/to/pyfug
```

### Número de retardos por defecto (ya implementado en pyfug)

```python
nlags = max(10, 3 * (freq + 1))
# mensual (s=12): 39
# trimestral (s=4): 15
# anual/semestral: 10
```

---

## Usar fue para estimación

ART identifica el modelo → FUE (`fue` Python) estima → pyfug produce gráficos
diagnósticos del modelo estimado.

Workflow completo:
```python
import fue
from pyfug.graphics import plot_combined, plot_acf_pacf, plot_histogram

# 1. Identificación (ART)
# ... → modelo sugerido: ARIMA(0,1,0)(0,1,1)_12

# 2. Estimación (FUE)
ts, model = fue.inp.load("IPC_DE_011_011.inp")
result = model.fit()

# 3. Diagnóstico (pyfug)
resid_ser = ...  # extraer residuos como Tseries
fig = plot_combined(resid_ser, title="Residuos ARIMA(0,1,0)(0,1,1)_12")
```
