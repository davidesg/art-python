# IPC_ES — Control de cambios de modelo

Serie: Índice de Precios al Consumo España (IPCA, base 2016=100)
Fuente: IPC.xlsx Sheet1 col D, mensual, 2002/01–2024/03 (n=263)
Transformación: λ=0 (log), d=1, D=0 (B1/Treadway)

## Convención de numeración

```
IPC_ES_mNN.pre   — parámetros estimados del modelo NN (punto de partida para NN+1)
IPC_ES_mNN.inp   — especificación de NN antes de estimar (si se genera desde .pre)
```

Flujo: `mNN.pre` → modificar especificación → `m(NN+1)` estimado → `m(NN+1).pre`

---

## m00 — Modelo armónico base

**Especificación**: d=1, D=0, λ=0, 5 pares cos/sin + alter, sin ARMA, sin media  
**Parámetros libres**: 11 (armónicos)  
**σ̂**: 0.4192%  
**Archivo**: `IPC_ES_m00.pre`

**Cambios respecto al anterior**: modelo inicial

---

## m01 — Armónicos + 20 intervenciones

**Especificación**: m00 + 20 escalones (step) en fechas de outliers identificados

**Outliers tratados** (scan sobre residuos m00, umbral 2.5σ, identificación iterativa):

| Fecha | Evento |
|-------|--------|
| 12/2010 | — |
| 01/2016 | — |
| 05/2018 | — |
| 03/2020 | COVID-19 crash |
| 01/2021 | Inicio rebote post-COVID |
| 09/2021 | — |
| 10/2021 | Inicio crisis energética |
| 12/2021 | — |
| 01/2022 | — |
| 02/2022 | — |
| 03/2022 | Pico máximo crisis energética (+5.7σ) |
| 04/2022 | — |
| 05/2022 | — |
| 06/2022 | — |
| 10/2022 | — |
| 01/2023 | — |
| 02/2023 | — |
| 04/2023 | — |
| 07/2023 | — |
| 10/2023 | — |

**Parámetros libres**: 31 (11 armónicos + 20 escalones)  
**σ̂**: 0.2653% (−36.7% vs m00)  
**Archivo**: `IPC_ES_m01.pre`

**Cambios respecto a m00**: +20 intervenciones step; identificadas iterativamente
con `describe_prelim_scan` sobre residuos del modelo anterior

---

## m02 — Armónicos + 20 intervenciones + AR(1) + media

**Especificación**: m01 + AR(1) regular + media μ libre

**Identificación ARMA** (sobre residuos m01):
- ACF: decae geométricamente desde +0.35 (k=1)
- PACF: corte brusco en k=1 (+0.35*), k≥2 dentro de bandas
- Patrón: AR(1) con media ≠ 0 (μ̂=+0.14%/mes, 7σ del cero)

**Parámetros estimados**:
```
φ₁  = +0.387   (AR regular lag 1)
μ   = +0.140%  mensual  (= 1.68% anual)
σ̂  =  0.246%
```

**Diagnóstico de residuos**:
- Q(39) = 24.0 → no significativo ✓ (ruido blanco)
- JB = 0.8 (p=0.685) → normalidad ✓
- S = −0.1, K = −0.1 → prácticamente normal

**Outliers marginales restantes** (2.5–3σ, no tratados aún):
- 09/2012 z=+2.92
- 03/2021 z=+2.70
- 09/2022 z=−2.50

**Parámetros libres**: 33 (11 + 20 + 1 AR + 1 μ)  
**σ̂**: 0.2461% (−7.2% vs m01, −41.3% vs m00)  
**Archivo**: `IPC_ES_m02.pre`

**Cambios respecto a m01**: +AR(1) φ₁=0.387, +media μ=0.140%/mes
Cargado desde `IPC_ES_m01.pre` → añadida especificación ARMA → estimado → guardado

### Ecuación del modelo m02

$$
(1 - 0.387\,B)(1-B)\ln \text{IPC}_{ES,t}
  = \mu^* + H_t + \sum_{j=1}^{20} \omega_j S(t,t_j) + \varepsilon_t
$$

equivalente a:

$$
\nabla \ln \text{IPC}_{ES,t} = 0.140\% + 0.387\,(\nabla \ln \text{IPC}_{ES,t-1} - 0.140\%)
  + H_t + \sum_{j=1}^{20} \omega_j \Delta S(t,t_j) + \varepsilon_t
$$

donde $H_t = \sum_{k=1}^{5}[a_k \cos(2\pi k t/12) + b_k \sin(2\pi k t/12)] + c\,(-1)^t$
y $\varepsilon_t \sim \text{RB}(0,\,(0.246\%)^2)$

---

## Próximos pasos

- [ ] Contrastar 3 outliers marginales: 09/2012, 03/2021, 09/2022 (Q=24.0 no urge)
- [ ] Test MEG de estacionalidad residual (armonicos significativos?)
- [ ] Parsimonia: ¿son necesarios los 5 pares de armonicos o sobran algunos?
- [ ] Diagnóstico formal: Ljung-Box por sub-períodos, ARCH test
