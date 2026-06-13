"""
Demo ART — IPC Chile 1986-2001 (muestra_1.86_12.01, guion3)

Recorre el flujo completo Box-Jenkins-Treadway:
  Etapa 1 — Identificación
  Etapa 2 — Estimación (fue)
  Etapas 3-4 — Diagnosis + Contrastes formales
  Etapa 5 — Informe integrado

Cada paso indica si es automático, requiere decisión del analista,
o es un punto de entrada natural para asistencia de Claude (LLM).
"""

import os
import fue
import art

OUT = os.path.expanduser("~/Desktop/demo_art/")
os.makedirs(OUT, exist_ok=True)

GUION = os.path.expanduser(
    "~/Documents/Documentos/Tesis/Analisis/Chile/ipc/mensuales/"
    "analisis/muestra_1.86_12.01/guion3/"
)

# =============================================================================
# ETAPA 1A — Transformación Box-Cox
# =============================================================================
# AUTOMÁTICO: ART calcula la varianza por subperiodo para λ=0 y λ=1.
# ANALISTA:   decide λ observando la dispersión de la serie tipificada.
# CLAUDE:     puede leer la tabla de varianzas y recomendar λ con justificación.

ts, _ = fue.inp.load(GUION + "PC1.inp")   # carga la serie (modelo ignorado aquí)
ts.name = "IPC Chile"

art.save_boxcox_selection(ts, OUT + "1_boxcox.html")
print("1. Box-Cox →", OUT + "1_boxcox.html")

# =============================================================================
# ETAPA 1B — Detección de estacionalidad
# =============================================================================
# AUTOMÁTICO: ART ejecuta el F-test HAC sobre regresión armónica.
# ANALISTA:   confirma si procede estacionalidad determinista o estocástica.
# CLAUDE:     puede interpretar el p-valor y los Wald por frecuencia,
#             y recomendar D=0 (armónicos) o D=1 (diferencia estacional).

r_seas = art.detect_seasonality(ts)
art.save_seasonality(ts, OUT + "2_estacionalidad.html")
print(f"2. Estacionalidad → F={r_seas.f_stat:.2f}, p={r_seas.p_value:.4f}",
      "→", OUT + "2_estacionalidad.html")

# =============================================================================
# ETAPA 1C — Listado de identificación (elección de d y p,q)
# =============================================================================
# AUTOMÁTICO: ART genera la serie diferenciada y sus ACF/PACF para d=0,1,2.
# ANALISTA:   elige d observando cuál diferenciación estacionaliza la serie,
#             y lee el patrón ACF/PACF para decidir p y q.
# CLAUDE:     puede describir el patrón ("ACF decrece suavemente, PACF corta
#             en lag 1 → AR(1)") y sugerir (p,q) con razonamiento.

art.save_identification_report(ts, OUT + "3_identificacion.html")
print("3. Identificación →", OUT + "3_identificacion.html")

# =============================================================================
# ETAPA 1D — Sugerencia automática de órdenes ARIMA
# =============================================================================
# AUTOMÁTICO: ART compara ACF/PACF teórica de candidatos con la empírica.
# ANALISTA:   elige del top-5 basándose en la similitud y la parsimonia.
# CLAUDE:     puede explicar por qué el top-1 tiene ese score, señalar si
#             dos candidatos son casi equivalentes, o alertar sobre modelos
#             sobreparametrizados.

specs = art.suggest_orders(ts, d=2, D=0, lam=0.0, top_n=5)
print("4. Órdenes sugeridos:")
for s in specs:
    print(f"   ARIMA({s.p},{s.d},{s.q}) similitud={s.similarity:.3f}")

# =============================================================================
# ETAPA 2 — Estimación (fue, no ART)
# =============================================================================
# AUTOMÁTICO: fue estima por MVENC (máxima verosimilitud exacta).
# ANALISTA:   ha especificado el modelo tras la identificación.
# CLAUDE:     puede verificar que la especificación es coherente con lo
#             identificado antes de lanzar la estimación.

ts_pc6, m = fue.inp.load(GUION + "PC6.inp")
m.fit()
print(f"\n5. Estimado: loglik={m._result.loglik:.3f}, AIC={m._result.aic:.2f}")

# =============================================================================
# ETAPAS 3-4 — Diagnosis + Contrastes formales + Informe
# =============================================================================
# AUTOMÁTICO: ART ejecuta todos los contrastes y genera el HTML.
# ANALISTA:   interpreta los resultados y decide si reformular (etapa 4).
# CLAUDE:     puede leer el informe y redactar un diagnóstico narrativo:
#             qué tests pasan, qué problemas hay, qué reformulación sugiere.

r = art.save_full_report(m, OUT + "6_informe_PC6.html")
print(f"\n6. Informe PC6 → {OUT}6_informe_PC6.html")
print(f"   Diagnosis: {'APROBADO' if r.diagnosis.clean else 'REVISAR'}")
print(f"   DCD MA(1): LR={r.dcd_results[0].lr:.2f}")
print(f"   MEG resultados: {len(r.meg_results)} frecuencias")
print(f"   Outliers (3.5): {r.interventions.has_outliers}")

print("\nTodos los informes en:", OUT)
