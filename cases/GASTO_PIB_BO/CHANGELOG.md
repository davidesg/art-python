# GASTO_PIB_BO — Control de cambios de modelo

Serie: Gasto público sobre PIB, Bolivia. Trimestral, 2004:1–2024:4 (n=84).
Fuente: datos de un TFM de la UCM (M. Tapia Torrico, 2026), a su vez de fuentes
oficiales bolivianas. **Incorporado con permiso.**
Transformación: λ=0 (log), d=1, D=0 (B1/Treadway) + AR(1) estacional.

## Por qué este caso está en la batería

Es el primer caso de la batería con **estacionalidad que domina la serie**: las
amplitudes estacionales son del orden de la desviación típica de ∇ln
(−17,2% y +12,6% frente a σ̂=19,8%), F-HAC conjunto **216,6**. Y aporta cuatro
cosas que la batería no tenía:

1. **Un ω(B) de orden 1** sobre un impulso — la forma que la capa ART todavía no
   sabe especificar (`docs/TODO-interventions.md`), aquí estimada y contrastada.
2. **Un caso donde el MEG cambia de veredicto según la etapa**: corrido sobre un
   modelo inadecuado dijo que las DOS frecuencias eran estocásticas (LR 38,0 y
   4,94); corrido en su etapa sobre el modelo adecuado dice sólo f=1, y con LR
   4,71 — y f=2 pasa a **determinista** (1,79 contra 1,94). Es la ilustración
   medida de `bugs/BUG-0025`.
3. **Un anómalo que resulta ser propagación de otro**: el residuo de 4/2009
   (z=−2,81) desaparece al intervenir 4/2008, porque el SAR(1)₄ propagaba el
   choque un año después. Una intervención arregla dos.
4. **Estacionalidad determinista fuerte + AR estacional estacionario** como
   línea base contra la que contrastar reformulaciones estocásticas.

## Convención de numeración

```
GASTO_PIB_BO_mNN.pre   — parámetros estimados del modelo NN
GASTO_PIB_BO_mNN.inp   — especificación de NN antes de estimar
GASTO_PIB_BO_mNN.out   — registro de la estimación: parámetros CON SUS ERRORES
                          TÍPICOS, covarianza, residuos con fechas, y la tabla
                          de calibración de distorsiones de la ACF
```

Flujo: `mNN.pre` → modificar especificación → `m(NN+1).inp` → estimar → `.out` + `.pre`

---

## m00 — Línea base determinista

**Especificación**: λ=0, d=1, D=0, 1 par cos/sin + alter de Nyquist, sin ARMA, sin media
**σ̂ₐ**: 6,8166%  ·  **ℓ**: −277,09  ·  **AIC**: 560,18
**Diagnosis**: Q falla en 2, 4, 8 y 12 (Q(15)=89,8); JB=14,86; 2 anómalos

*Los armónicos absorben mucho —σ̂ de 19,8% a 6,8%— pero dejan estructura
estacional masiva: ACF 0,510 / 0,410 / 0,329 en los retardos 4, 8 y 12.*

## m10 — AR(1) estacional

**Cambio**: + SAR(1)₄
**Φ**: 0,5459 (0,0916)  ·  **σ̂ₐ**: 5,6695%  ·  **ℓ**: −263,42  ·  **AIC**: 534,83
**Diagnosis**: Q p-mín 0,0446; JB=32,66; **2 anómalos, que EMERGEN**

*El patrón que lo identifica: en la ACF del m00 los retardos impares están dentro
de banda y los pares TODOS fuera, alternando de signo (−,+,−,+,−,+). Eso es un
factor amortiguado en la frecuencia f=1, que genera ρₖ ∝ rᵏ·cos(2πk/4). Decae a
razón 0,80 cada cuatro retardos: módulo 0,946 por retardo.*

*Al recoger la estacionalidad, los anómalos empeoran — de +3,49 a +3,92 y de
+2,99 a +3,16. Es la señal de que ya son lo único que queda.*

## m20 — Impulso con ω(B) de orden 1 en 2020:2

**Cambio**: + `(ω₀ − ω₁B) Ξ^impulse_{2020:2}`
**ω**: 20,407 (3,184) · −7,645 (3,128)  ·  **σ̂ₐ**: 4,6286%  ·  **AIC**: 506,93
**Diagnosis**: Q falla en 8 y 12; JB=14,29; 1 anómalo (4/2008, z=+3,73)

*La forma se leyó integrando los residuos: el nivel salta +20,5 en 2020:Q2, queda
+9,0 en Q3 y vuelve a cero en Q4. Contrastada por dos vías — LR contra el orden 0
la exige (5,408, p=0,020) y LR contra tres escalones consecutivos la permite
(0,021, p=0,886, o sea ganancia de largo plazo nula).*

*ART no expresa ω(B): estimado escribiendo el `.inp` con las ω a cero como
semilla y dejando que ART estime. Ver `docs/TODO-interventions.md`.*

## m30 — Dos escalones (descartado)

**Cambio**: + escalones en 4/2008 y 4/2009
**ω**: 18,229 (3,570) · **0,223 (3,423), t=0,07**  ·  **AIC**: 485,42

*El escalón de 4/2009 sale CERO. El residuo de −12,96 en esa fecha no era una
anomalía propia: era el SAR(1)₄ propagando el choque de 2008:Q4 un año después.
Corregido el primero, el segundo se normaliza solo.*

## m31 — **MODELO FINAL** — un escalón

**Cambio**: se retira el escalón de 4/2009
**σ̂ₐ**: 3,9209%  ·  **ℓ**: −234,71  ·  **AIC**: 483,43  ·  **BIC**: 500,36
**Diagnosis**: **APROBADO ✓** — Q(15)=14,1 ✓ · JB=1,212 (p=0,546) ✓ · sin anómalos

```
(1 − 0,7277·B⁴) ∇ ln GASTO_PIB  =  armónicos f=1,f=2
                                 + (20,246 − 7,4065·B) Ξ^impulse_{2020:2}
                                 + 18,123 Ξ^step_{2008:4}  +  aₜ
```

| parámetro | estimado | ee | t |
|---|---|---|---|
| alter (Nyquist) | +7,4778 | 0,6736 | +11,10 |
| cos(π/2·t) | +5,1122 | 1,3814 | +3,70 |
| sin(π/2·t) | −9,2213 | 1,3762 | −6,70 |
| ω₀ impulso 2020:2 | +20,246 | 2,6225 | +7,72 |
| ω₁ impulso 2020:2 | −7,4065 | 2,5899 | −2,86 |
| escalón 4/2008 | +18,123 | 3,4595 | +5,24 |
| Φ (SAR 1)₄ | +0,7277 | 0,0761 | +9,56 |

Idéntica verosimilitud que m30 con un parámetro menos.

### Contrastes formales (etapa correcta, diagnosis limpia)

| contraste | resultado |
|---|---|
| DCD sobrediferenciación | θ̂=+1,0000, LR=−0,000 → **d=1 confirmado** |
| MEG f=1 | coef=−0,8720, LR=**4,709** (crít 2,06) → estocástica |
| MEG f=2 | coef=−0,9511, LR=**1,786** (crít 1,94) → **determinista** |

**Se conserva como línea base DETERMINISTA**, sin reformular f=1, por decisión
del analista: el margen del MEG es estrecho (4,71 contra 2,06, viniendo de 38,0
al corregir la especificación) y el modelo actual ya tiene diagnosis aprobada y
todos los parámetros significativos. La reformulación estocástica de f=1 queda
como contraste pendiente contra esta línea base.
