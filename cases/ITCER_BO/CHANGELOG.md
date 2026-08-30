# ITCER_BO — Control de cambios de modelo

Serie: Índice de Tipo de Cambio Efectivo Real multilateral, Bolivia (BCB).
Trimestral, 2004:1–2024:4 (n=84).
Fuente: datos de un TFM de la UCM (M. Tapia Torrico, 2026), de fuentes oficiales
bolivianas. **Incorporado con permiso.**
Transformación: λ=0 (log), d=1, D=0, sin estacionalidad.

## Por qué este caso está en la batería

Es el caso limpio de la trilogía, y aporta dos cosas concretas:

1. **Una intervención cuya FORMA se decidió por contraste, no por inspección.**
   El episodio 2008:4–2009:1 admitía dos lecturas —impulsos (efecto transitorio)
   o escalones (permanente)— y la segunda anida a la primera. Se estimó la
   encompassing y se contrastó la restricción, en vez de elegir. Ver §m10.
2. **Un caso donde el anómalo DECIDE la identificación.** La ACF de ∇ln tiene un
   único coeficiente fuera de banda (0,27 en el retardo 1) y el anómalo de
   2008:4 aporta el **55%**. Sin tratarlo se identifica un ARMA; tratado, el
   retardo cae dentro de banda. La calibración previa no es un adorno aquí: es
   lo que separa un modelo de otro.

---

## m00 — Deterministas solos

**Especificación**: λ=0, d=1, D=0, sin estacionalidad, con media, sin ARMA
**μ**: −0,7202  ·  **σ̂ₐ**: 2,7020%  ·  **ℓ**: −200,27
**Diagnosis**: Q falla en 2 y 4; JB=17,58; 1 anómalo (2008:4, z=−3,91)

> ⚠ **El error típico de μ en este modelo NO es válido.** Sale 0,1552, que es
> √(2/83) — la semilla del BFGS. Un modelo de media sola tiene solución cerrada
> (su estimador máximo-verosímil es la media muestral), así que el optimizador
> para en `niter=0` y nunca construye el hessiano. Es `bugs/BUG-0027`, y este
> caso es el que lo destapó en su forma `npar=1`. El valor de μ es correcto; su
> error típico hay que tomarlo del m10 o del m20 (0,2543 y 0,2895).

*λ=0 se decide por ser un ÍNDICE de base arbitraria: un cambio de base lo
multiplica por una constante, y sólo en logaritmos eso es un desplazamiento que
absorbe la constante. La correlación media-std (0,245 → 0,084) apoya pero no
decide — parte de un valor ya bajo.*

*Sin estacionalidad, y no por falta de potencia: F-HAC = 1,70 (p=0,1735) y las
amplitudes van de 0,08% a 0,66% frente a σ̂ = 2,70%. Aunque el patrón existiera
sería una cuarta parte del ruido.*

## m10 — Impulso con ω(B) de orden 1 en 2008:4

**Cambio**: + `(ω₀ − ω₁B) Ξ^impulse_{2008:4}`
**ω**: −8,9851 (1,8910) · +8,9352 (1,8911)  ·  **μ**: −0,7202 (0,2543)
**σ̂ₐ**: 2,3165%  ·  **ℓ**: −187,50  ·  **AIC**: 381,00
**Diagnosis**: **APROBADO ✓** — Q(15)=10,0 · JB=1,995 (p=0,369) · sin anómalos

*La forma, contrastada y no elegida.* Integrando los residuos, el episodio son
**dos impulsos consecutivos en el NIVEL** (2008:4 y 2009:1) — porque un impulso
en la diferencia es, integrado, un escalón en el nivel, y `fue` especifica las
intervenciones en el nivel.

Dos especificaciones defendibles, y la segunda anida a la primera:

| | efecto permanente |
|---|---|
| `(ω₀ − ω₁B) Ξ^impulse` | **cero por construcción** |
| `(ω₀ − ω₁B − ω₂B²) Ξ^step` | ω(1), libre |

Con ω(1)=0 el escalón conserva dos parámetros libres y genera el mismo espacio.
Estimadas ambas: ω(1) = **−0,0495** (−4,95% permanente), **LR = 1,223, χ²(1),
p = 0,269 → no se rechaza**. El episodio fue **transitorio**: el ITCER cayó ~9%
durante dos trimestres y volvió a su trayectoria.

*Ir directo al impulso habría impuesto por decreto la respuesta a la pregunta que
más interesa.*

*ART no expresa ω(B) (`docs/TODO-interventions.md`): se escribe el `.inp` con las
ω a cero como semilla y se deja que ART estime.*

## m20 — **MODELO FINAL** — + AR(1)

**Cambio**: + AR(1) regular
**σ̂ₐ**: 2,2709%  ·  **ℓ**: −185,87  ·  **AIC**: 379,74  ·  **BIC**: 389,42
**Diagnosis**: **APROBADO ✓** — Q(15)=**6,3** · JB=1,760 (p=0,415) · sin anómalos

```
(1 − 0,2077·B) (∇ ln ITCER_BO + 0,7308) = (−8,1195 + 7,9539·B) Ξ^impulse_{2008:4} + aₜ
```

| parámetro | estimado | ee | t |
|---|---|---|---|
| ω₀ (2008:4) | −8,1195 | 1,7950 | −4,52 |
| ω₁ | +7,9539 | 1,6600 | +4,79 |
| φ (AR 1) | +0,2077 | 0,1112 | +1,87 |
| μ | −0,7308 | 0,2895 | −2,52 |

### Por qué el AR(1), estando en el filo

**El estadístico no decide**: LR = 3,26 (1 g.l., p=0,071), AIC prefiere el AR(1),
BIC prefiere el m10. Deciden dos cosas:

1. **El Q pasa de 10,0 a 6,3.** El m10 ya pasaba, pero sin holgura; el AR(1) deja
   la ACF plana. Un Q ajustado con n=84 es una advertencia que no conviene llevar
   a un sistema multivariante, donde tres series con residuos flojos se acumulan.
2. **Un índice de precios tiene persistencia por naturaleza.** Aquí muy leve:
   φ=0,21. El ITCER es poco más que un paseo aleatorio con deriva, y el AR(1)
   recoge esa persistencia mínima en vez de negarla.

### Contrastes formales (etapa correcta, diagnosis limpia)

| contraste | resultado |
|---|---|
| Shin-Fuller (H₀: ρ≈0,9524) | Φ̂₁ᵤ=**19,006** vs crít. 1%=3,41 → estacionario ✓ |
| DCD sobrediferenciación | θ̂=**+1,0000**, LR=−0,000 → **d=1 confirmado** ✓ |
| Par en f=0 | **los dos lados coinciden** — fuera de la banda ambigua |

Sin MEG: no hay estacionalidad que contrastar.

**Lectura:** deriva de **−0,73% trimestral** (≈ −2,9% anual), persistencia leve, y
una caída transitoria de ~8% en 2008:4–2009:1 íntegramente recuperada.
