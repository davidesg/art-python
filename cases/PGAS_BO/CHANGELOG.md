# PGAS_BO — Control de cambios de modelo

Serie: Precio implícito de exportación del gas natural, Bolivia. USD por tonelada
(valor/volumen ×10⁶). Trimestral, 2004:1–2024:4 (n=84).
Fuente: datos de un TFM de la UCM (M. Tapia Torrico, 2026), de fuentes oficiales
bolivianas. **Incorporado con permiso.**
Transformación: λ=0 (log), d=1, D=0, sin estacionalidad, sin media.

## Por qué este caso está en la batería

Aporta cuatro cosas que la batería no tenía:

1. **Un AR(2) de raíces COMPLEJAS**, que es la especificación con la que
   `formal_tests` reventaba antes de `bugs/BUG-0021` — el bloque RV sólo se
   activa con discriminante negativo. Es el caso de regresión de ese defecto.
2. **Un orden de integración decidido CONTRA los contrastes exploratorios y
   confirmado por los formales.** ADF y KPSS decían d=0; el par
   Shin-Fuller/DCD sobre el modelo estimado confirma d=1 por los dos lados. Es
   la ilustración de por qué la especificación inicial no es el veredicto.
3. **Una identificación donde ART se equivoca de candidato**, y la razón es
   medible: propone primero un MA(1) que no puede generar la ACF observada.
4. **La colinealidad de escalones consecutivos en un modelo I(1)**, medida: cada
   escalón añadido multiplica el error típico de la ganancia de largo plazo.

---

## m10 — AR(2), sin intervenciones

**Especificación**: λ=0, d=1, D=0, AR(2), sin media, sin estacionalidad
**φ**: 0,7491 (0,1045) · −0,2869 (0,1038)
**σ̂ₐ**: 8,3338%  ·  **ℓ**: −294,39  ·  **AIC**: 592,79
**Diagnosis**: Q(15)=6,1 ✓ · **JB=87,47 ✗** · 1 anómalo (2009:1, z=−4,54)

### λ=0, decidido contra la recomendación de ART

ART recomienda **identidad** (corr media-std 0,150 frente a 0,173 en log) y marca
la decisión ambigua (Δ=0,024). Se decide log, y **no por el estadístico** —que no
discrimina y encima apunta al otro lado— sino por lo que la serie es:

* **No es un índice**: es un precio en USD/t, con unidad física, así que el
  argumento de invariancia a la base **no aplica** aquí.
* Pero **es un precio de materia prima**, y ésos varían en proporción.
* El **rango es amplio** (máx/mín ≈ 5,3), de modo que la escala tiene
  consecuencias — al contrario que en una serie de rango estrecho.

### d=1, hipótesis de trabajo confirmada después

| d | ADF | KPSS |
|---|---|---|
| 0 | p=**0,0134** ✓ rechaza raíz unitaria | p=**0,0912** ✓ no rechaza estacionariedad |
| 1 | p=0,0000 ✓ | p=0,1000 ✓ |

ART recomienda **d=0**. Se decide d=1 por cuatro razones: los dos contrastes son
**marginales** (el ADF rechaza al 5% pero no al 1%; el KPSS con 0,0912 casi
rechaza); el gráfico no muestra nivel al que volver; **un precio que vacía
mercado difícilmente es estacionario** de forma predecible sin abrir arbitraje; y
el error es **asimétrico** — sobrediferenciar lo destapa el testigo del DCD,
subdiferenciar deja una raíz AR cerca de 1 mucho más difícil de ver.

**A7 lo confirmó por los dos lados.** Los contrastes exploratorios se equivocaban.

### El AR(2), corrigiendo a ART

| lag | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| ACF | **0,575** | 0,132 | −0,008 | −0,022 |
| PACF | **0,575** | **−0,296** | 0,105 | −0,044 |

Banda ±0,220: la ACF tiene **un** coeficiente fuera, la PACF **dos**.

**ART clasifica primero un modelo imposible**: propone `ARIMA(0,1,1)` con
sim=0,878, pero para un MA(1) ρ₁ = θ/(1+θ²) tiene máximo absoluto **0,5**, y el
observado es **0,575** — ningún MA(1), con ningún θ, puede generarlo. El AR(2)
queda cuarto (sim=0,755).

La lectura correcta sale de la PACF: φ₂ = φ₂₂ = −0,296 y φ₁ = φ₁₁(1−φ₂) = **0,745**,
que reproducen ρ₁=0,575 y ρ₂=0,132 exactamente. Lo estimado: **0,7491 y −0,2869**.

*(La cota `|ρ₁| ≤ cos(π/(q+2))` no es significativa aquí — z=0,97 — así que no es
un defecto sino un hueco del motor de identificación: ver
`docs/TODO-identification.md`.)*

## m20 — **MODELO FINAL** — escalón en 2009:1

**Cambio**: + `ω Ξ^step_{2009:1}`
**ω**: −19,476 (6,2917)  ·  **φ**: 0,7647 (0,1060) · −0,2640 (0,1071)
**σ̂ₐ**: 7,8695%  ·  **ℓ**: −289,74  ·  **AIC**: 585,49  ·  **BIC**: 592,75
**Diagnosis**: **APROBADO ✓** — Q p-mín **0,5316** · JB **3,580 (p=0,167)** · sin anómalos

### La forma, leída integrando los residuos

| | residuo | z | acumulado |
|---|---|---|---|
| 2008:Q1 | +10,35 | +1,24 | +12,9 |
| 2008:Q3 | +13,76 | +1,65 | +25,7 |
| 2008:Q4 | +6,92 | +0,83 | **+32,6** |
| **2009:Q1** | **−37,27** | **−4,47** | **−4,6** |

El nivel se aleja **+33 puntos logarítmicos** a lo largo de 2008 y el −37 de
2009:Q1 **lo devuelve a cero**: es la **corrección de un exceso acumulado**, no un
desplome aislado. Encaja con el mecanismo — el precio se indexa a fuelóleos con
rezago de ~2 trimestres, así que el pico del petróleo de mediados de 2008 llega
en Q3–Q4 y el desplome de finales de 2008 llega en Q1/2009.

**Eso descarta el impulso**, que afirma que el nivel se desvía un período y
vuelve. Aquí el nivel **se queda** donde lo deja la caída.

### Seis candidatas, comparadas por su ganancia de largo plazo

| | ganancia LP | ee | p | JB | \|z\|>3 |
|---|---|---|---|---|---|
| impulso 2009:1 | 0 (por construcción) | — | — | 42,41 | 1 |
| **escalón 2009:1** | **−0,1948** | **0,0631** | **0,0020** | **3,58** | **0** |
| escalón ω orden 1 | −0,7082 | 0,1196 | 0,0000 | 6,35 | 2 |
| escalones 2008:3+2009:1 | −0,1769 | 0,0816 | 0,0302 | 3,86 | 0 |
| escalones 2008:1+2009:1 | −0,1028 | 0,0887 | 0,2462 | 4,45 | 0 |
| tres escalones | +0,4269 | 0,2268 | 0,0598 | 2,95 | 0 |

**El impulso queda descartado empíricamente**: logL sube 0,5, JB sigue en 42 y el
residuo extremo permanece.

**La hipótesis del incidente de 2008 queda contrastada**: darle escalón propio no
aporta (LR 0,12 y 2,11). El AR(2) ya absorbe la acumulación.

**El ω de orden 1 se descarta pese a ganar** (LR 19,18 sobre el simple): implica
−70,8% permanente cuando el precio se recuperó, **empeora** la diagnosis (JB de
3,58 a 6,35) y desestabiliza el AR(2) (φ₂ de t=−2,45 a −1,74).

**Y el hallazgo del nodo está en la columna del error típico**: cada escalón
añadido multiplica la incertidumbre sobre el efecto permanente — ×3,6 al pasar de
uno a tres — hasta invertirle el signo. Con `d=1` un escalón es casi colineal con
el propio paseo aleatorio, y varios consecutivos lo son entre sí. El reparto lo
delata: el escalón de 2009:1 vale −0,199 con dos y **−0,036** con tres.

### El AR(2): raíces complejas

Raíces en B: **1,4485 ± 1,3000 i**, módulo 1,9463. Discriminante φ₁²+4φ₂ = −0,4711.

| | valor |
|---|---|
| amortiguamiento d | **0,51 ± 0,10** |
| periodo | **8,59 ± 2,09** trimestres |

**No es un factor estacional oculto**: el periodo no coincide con f=1 (4,00) ni
f=2 (2,00), y d=0,51 está lejos de 1. El RV lo confirma por su cuenta: f̂=0,466 en
unidades armónicas ⇒ periodo 4/0,466 = **8,58**, y rechaza las dos frecuencias
estacionales con LR ≈ 44.

**El ciclo no llega a verse**: semivida de la amplitud **1,04 trimestres**. Lo que
sí está determinado es la forma de la respuesta —

| j | 0 | 1 | 2 | 3 | 4 | 6 |
|---|---|---|---|---|---|---|
| ψⱼ sobre ∇ln | 1,000 | 0,765 | 0,321 | 0,043 | **−0,051** | −0,025 |
| acumulado en el nivel | 1,000 | 1,765 | 2,086 | **2,129** | 2,078 | 2,002 |

φ₂<0 produce un **rebote correctivo**: el choque cruza a negativo en el cuarto
trimestre. Multiplicador de largo plazo **1/φ(1) = 2,003**, con sobrerreacción
hasta 2,13. Es el patrón de una indexación con rezago, y el mismo que el episodio
2008–2009 muestra a lo grande.

### Contrastes formales

| contraste | resultado |
|---|---|
| Shin-Fuller | Φ̂₁ᵤ=**10,919** vs crít. 1%=3,41 → estacionario ✓ |
| DCD sobrediferenciación | θ̂=**+0,9694**, LR=0,138 → **d=1 confirmado** ✓ |
| Par en f=0 | **los dos lados coinciden** |
| RV | f̂=0,466 → rechaza f=1 (LR=43,99) **y** f=2 (LR=44,27) → no estacional |
