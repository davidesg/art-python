---
id: BUG-0143
title: El panel de la ACF mide sólo medio anómalo — le falta el canal de la varianza, que aquí vale el 20%
status: fixed
severity: medium
component: figuras
found_in: 0.2.2
fixed_in: 0.2.2
reported: 2026-09-10
reporter: David
tags:
  - calibracion
  - figuras
references:
  - BUG-0142
  - BUG-0131
  - BUG-0132
---

## Summary

En el gráfico de calibración de distorsiones, los dos paneles de abajo dicen
«red = the outlier's share» y **no calculan lo mismo**:

| panel | qué dibuja de rojo |
|---|---|
| ACF | `_acf_outlier_contributions`: la descomposición EXACTA por pares, C_k(p) = [ẑ_p·ẑ_{p+k} + ẑ_{p−k}·ẑ_p] / Σⱼẑⱼ² |
| PACF | la diferencia contra la calibrada: `pacf_full − pacf_cal` |

La descomposición de la ACF conserva el denominador **contaminado**. Y ahí está
lo que se pierde: un anómalo distorsiona el correlograma por **dos canales**,

1. el numerador — sus productos cruzados con los vecinos, y
2. **el denominador** — infla σ̂², y con ello hunde TODOS los r(k) hacia cero.

El segundo canal no aparece en el panel. Medido sobre `RATIO_m10`, ∇100·ln,
n=83, umbral 2σ (omitidas las obs. 64, 71 y 75, con z = +2,20, −2,16, −2,06):

    Σẑ² con los anómalos  =  83,00
    Σẑ² sin ellos         =  69,24     →  la varianza cae un 16,6%
                                           los r(k) suben un 19,9%

Las dos lecturas de «la ACF sin el anómalo» difieren hasta **0,191**, que es
casi la banda entera (±0,215):

| k | full − contribución | cero-relleno | dif |
|---|---|---|---|
| 1 | −0,4665 | −0,5589 | +0,0924 |
| 4 | +0,6452 | +0,8362 | **−0,1910** |
| 8 | +0,6461 | +0,7732 | −0,1271 |
| 12 | +0,6409 | +0,7684 | −0,1275 |

O sea: el panel de la ACF **subestima sistemáticamente** el efecto del anómalo,
y lo subestima justo donde se decide —los retardos estacionales 4, 8 y 12—. Y
como el panel de la PACF sí ve los dos canales desde BUG-0142, la figura tiene
hoy dos rojos que significan cosas distintas, uno encima del otro.

Y no es sólo la figura: la TABLA de `calibra_correlograma` publica `acf_cal` con
el estimador de cero-relleno, mientras el panel dibuja `acf_full − contribución`.
Tabla y figura no concuerdan.

## Por qué esto importa más de lo que parece

El canal del denominador es el **dominante** en el efecto clásico de un anómalo
aditivo sobre el correlograma: sesga toda la ACF hacia cero. Un panel que sólo
mide el numerador puede enseñar una contribución pequeña —«el anómalo casi no
toca este retardo»— cuando el anómalo está deprimiendo ese retardo un 20% por la
otra vía. Ésa es la conclusión contraria a la correcta, en el panel que decide
el orden MA.

## Fix — el reparto, con sus dos canales y su identidad

Decisión del analista: la opción **(b)**, renormalizar conservando la
atribución por anómalo. Con `I` los anómalos, `R` lo retenido, μ_c la media de
`R` y c = w − μ_c:

    D_c = Σ_{t∈R} c_t²        D_m = Σ_t c_t² = D_c + Σ_{p∈I} c_p²
    A_k(p) = c_p·c_{p+k}·1{p+k∈R} + c_{p−k}·c_p·1{p−k∈R}
    B_k    = Σ_{p,q∈I, q−p=k} c_p c_q

    contrib[p, k] = [ A_k(p) − r_cal(k)·c_p² ] / D_m
                      ╰─numerador─╯   ╰─varianza─╯

    resto(k)      = [ r_obs(k) − r_m(k) ]  +  B_k / D_m
                      ╰─canal de la media─╯   ╰─pares─╯

con `r_m` la ACF de media limpia pero SIN omitir — el eslabón que separa el
efecto de la media del de la omisión. Y entonces

    Σᵢ contrib[i,k]  +  resto[k]  ==  r_obs(k) − r_cal(k)

**exacto**. Comprobado sobre el caso real y ocho aleatorios: máximo 6,1e-16. Las
dos partes se calculan por caminos independientes —el reparto por su fórmula, la
calibrada por `_acf_pacf`— y la prueba exige que coincidan; `resto` NO se obtiene
restando.

La barra roja del panel de la ACF pasa a ser `Σcontrib + resto`, o sea
`r_obs − r_cal`: **la misma definición que el panel de la PACF y que la tabla**.
Un solo significado del rojo en toda la figura.

### Lo que enseña el reparto sobre el caso real

Retardo 4 de `RATIO_m10` —el estacional—, con los tres anómalos:

| | numerador | varianza | neto |
|---|---|---|---|
| obs 64 (Q2/2020) | +0,0620 | −0,0476 | **+0,0144** |
| obs 71 (Q1/2022) | +0,0434 | −0,0479 | **−0,0045** |
| obs 75 (Q1/2023) | +0,0461 | −0,0436 | **+0,0025** |
| resto (pares + media) | | | **+0,0546** |
| **total** | | | **+0,0671** |

Los dos canales **casi se cancelan** anómalo a anómalo: el panel anterior
dibujaba sólo la columna de la izquierda —unos +0,15 en total— cuando el efecto
neto de los tres por separado es +0,012. Exageraba el anómalo por un factor de
doce en el retardo que decide la estacionalidad.

Y lo que de verdad mueve ese retardo no es ninguno de los tres: es el **par**.
Separando `resto` en sus dos partes:

    canal de la media, máximo sobre 15 retardos:  0,0018   ← despreciable
    canal de los pares, máximo:                   0,0571
    y aparece SÓLO en los retardos 4, 7 y 11

que son exactamente las distancias entre 64, 71 y 75. Las obs. 71 y 75 —ambas de
z≈−2,1, **un año aparte**— fabrican +0,055 en el retardo 4. Dos anómalos del
mismo signo separados k períodos fabrican correlación en el retardo k, y eso no
es atribuible a ninguno de los dos por separado: por eso vive en `resto` y no en
`contrib`. Es justo la clase de artefacto que esta figura existe para cazar, y
el reparto anterior no lo asignaba a nada.

## Test

`tests/test_acf_contributions.py`, tres pruebas nuevas que sustituyen a la que
fijaba la fórmula anterior:

- `test_la_identidad_CIERRA_exacta` — ocho series aleatorias, < 1e-12.
- `test_el_canal_de_la_VARIANZA_esta_dentro` — aísla el término que faltaba y
  comprueba que no es despreciable.
- `test_dos_anomalos_a_distancia_k_fabrican_correlacion_en_el_retardo_k` — el
  canal de los pares, con dos anómalos plantados a cuatro períodos.
