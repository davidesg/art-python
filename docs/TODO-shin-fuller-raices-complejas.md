# TODO — cerrar el orden de integración cuando el AR tiene raíces complejas

**Estado:** abierto · **Abierto el** 2026-09-01 · **Origen:** BUG-0065, y la
discusión de las tres opciones de la escuela

---

## El hueco

Shin-Fuller aísla **una raíz real** (ec. 2.2-2.3: el operador se escribe
`(m − ρ)·A(m)` con ρ ∈ (−1,1]). Un AR con sólo raíces **complejas** no admite esa
forma, así que el contraste **no existe** ahí — y forzarlo corrompe en silencio.

Se pierde el **par confirmatorio**: quedan los dos DCD, que miran desde el mismo
lado.

## Lo primero que había que descartar, y no se sostuvo

La hipótesis cómoda era que un AR(2) complejo fuese *de por sí* evidencia contra
la raíz unitaria —si la hubiera, el ajuste mostraría una raíz real—. **Es falsa**,
medido sobre 40 réplicas (n=83, series centradas, μ fijada):

| verdad | el AR(2) ajustado sale complejo |
|---|---|
| AR(2) estacionario complejo, mod 1,95 | 37/40 |
| AR(2) estacionario complejo, mod 1,30 | 40/40 |
| **I(1) × AR(2) complejo, mod 1,95** | **16/40** |
| **I(1) × AR(2) complejo, mod 1,30** | **35/40** |

Con una raíz unitaria presente y un ciclo cerca del círculo, el AR(2) sale
complejo en **35 de 40**. El hueco es real y hay que taparlo.

## Las tres opciones, y lo que miden

Condicionado a que el AR(2) salga complejo, que es donde la pregunta se plantea
(40 réplicas por celda, n=83):

| verdad | n | **AR(3)+SF** → d+1 | **DCD solo** → d+1 | ΔAIC del sobreajuste |
|---|---|---|---|---|
| estacionario complejo, mod 1,95 | 37 | **0/37** | 3/37 | **+1,10** |
| estacionario complejo, mod 1,30 | 40 | **0/40** | 3/40 | **+0,62** |
| I(1) × complejo, mod 1,95 | 16 | **14/16** | 13/16 | **−3,79** |
| I(1) × complejo, mod 1,30 | 35 | **32/35** | 33/35 | **−23,64** |

### 1. DCD con testigo de sobrediferenciación — ya está

Directo y disponible. Tamaño ≈ **8 %** (3/37 y 3/40 falsos positivos) y potencia
81-94 %. Suficiente para orientar, pero es **un solo lado**.

### 2. Sobreajustar a AR(3), factorizar y contrastar el AR(1)

**Tamaño 0/77 y potencia 88-91 %**: en esta configuración es mejor que el DCD en
falsos positivos e igual de potente.

La preocupación legítima —la superficie de verosimilitud de un modelo
sobreparametrizado— resulta **medible y, de hecho, informativa**: el ΔAIC del
propio sobreajuste dice en qué mundo se está. Con la verdad estacionaria el AR(3)
**cuesta** (+0,6 a +1,1: la tercera raíz es espuria y se paga como un parámetro
de más); con raíz unitaria **mejora mucho** (−3,8 a −23,6, porque captura algo
real). La raíz espuria, además, se queda lejos del uno: φ ≈ 0,12–0,31 de media,
máximo 0,76 en 75 réplicas.

Verificado también en el caso real: sobre `∇ln PGAS`, el AR(3) da un par complejo
(mod 2,199) **y una raíz real** en φ=0,5174; SF aplica y dice estacionario
(Φ̂₁ᵤ=6,562), con un coste de +1,04 de AIC.

**Y recupera el par**: DCD por el lado MA, AR(3)+SF por el lado AR.

### 3. Contraste de módulo — la vía de investigación

H₀: |raíz| = 1 en la frecuencia ω̂ del par. Es lo que falta de verdad, y conecta
con SF_MEG: la maquinaria de verosimilitud de frontera es la misma. Nótese que
el `DCD_f` existente **no lo cubre**: está calibrado para la rejilla de
frecuencias ESTACIONALES (ω = 2πf/s), y aquí ω̂ es libre — en `PGAS_m20`, 0,466.

## Recomendación

**Cablear la 2 como complemento automático de la 1, y dejar la 3 como
investigación.** Cuando SF no aplique por raíces complejas, la herramienta puede:

1. decirlo (ya lo hace, BUG-0067);
2. **ofrecer** el sobreajuste a AR(p+1) como rama de contraste, con su ΔAIC a la
   vista, y marcarla como **rama de diagnóstico** —no como modelo candidato— para
   que no se cuele en la selección;
3. presentar los dos lados juntos: DCD y AR(3)+SF, que es el par recuperado.

Lo que **no** se debe hacer es adoptar el AR(p+1) como modelo. Es un instrumento
de contraste, y su tercera raíz es espuria por construcción cuando no hay raíz
unitaria — el propio ΔAIC lo dice.

## Salvedades de la evidencia

Una sola configuración de frecuencia (ω = 0,12·2π), n=83, sin intervenciones ni
MA, 40 réplicas por celda. Basta para decidir el diseño, **no** para publicar
tamaños. Antes de fijar la recomendación en la documentación conviene barrer
frecuencia, n, y la presencia de un MA competidor — que es justo donde Schwert
(1989) encontró los problemas de tamaño de todos estos contrastes.
