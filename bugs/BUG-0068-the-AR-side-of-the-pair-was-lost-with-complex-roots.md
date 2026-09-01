---
id: BUG-0068
title: con un AR de raíces complejas se perdía el lado AR del par confirmatorio — recuperado por sobreajuste a AR(p+1), como rama de diagnóstico
status: fixed
severity: medium
component: formal-tests
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-09-01
reporter: David — la opción 2 de las tres de la escuela, cableada tras medirla
tags:
  - shin-fuller
  - integration-order
  - overfitting
references:
  - src/art/formal_tests.py (shin_fuller_sobreajuste)
  - src/art/describe.py (presentación de la rama)
  - docs/TODO-shin-fuller-raices-complejas.md
  - bugs/BUG-0065-the-shin-fuller-null-was-not-shin-fullers.md
  - tests/test_bug_0068_sobreajuste_diagnostico.py
  - bugs/BUG-0068-repro/repro.py
---

## Summary

BUG-0065 dejó Shin-Fuller correcto, y con ello una consecuencia: sobre un AR cuyas
raíces son un **par conjugado** el contraste **no existe** —su reparametrización
`(m − ρ)·A(m)` exige ρ real— así que se pierde el **lado AR del par**. Y el par es
lo que da valor a los contrastes de frontera: dos nulas **opuestas**.

Quedaba sólo el DCD, que mira desde un lado.

## Lo que hubo que descartar primero

La hipótesis cómoda era que un AR(2) complejo fuese *de por sí* evidencia contra
la raíz unitaria. **Es falsa**, medido sobre 40 réplicas (n=83):

| verdad | el AR(2) ajustado sale complejo |
|---|---|
| AR(2) estacionario complejo, mod 1,30 | 40/40 |
| **I(1) × AR(2) complejo, mod 1,30** | **35/40** |

Con raíz unitaria presente y un ciclo cerca del círculo, el ajuste sale complejo
en 35 de 40. El hueco es real.

## La salida, medida antes de cablearla

Sobreajustar: si el AR(p) no ofrece raíz real, se estima un AR(p+1), se factoriza
en AR(1)·AR(p) y se contrasta el AR(1). Condicionado a que el AR(2) salga
complejo, que es donde la pregunta se plantea:

| verdad | n | **AR(3)+SF** → d+1 | DCD solo → d+1 | ΔAIC |
|---|---|---|---|---|
| estacionario complejo, mod 1,95 | 37 | **0/37** | 3/37 | +1,10 |
| estacionario complejo, mod 1,30 | 40 | **0/40** | 3/40 | +0,62 |
| I(1) × complejo, mod 1,95 | 16 | **14/16** | 13/16 | −3,79 |
| I(1) × complejo, mod 1,30 | 35 | **32/35** | 33/35 | −23,64 |

Tamaño **0/77**, potencia **88-91 %**: mejor que el DCD solo en falsos positivos
e igual de potente. La raíz espuria se queda lejos del uno — φ ≈ 0,12-0,31 de
media, máximo 0,76 en 75 réplicas.

## Y la preocupación por la superficie de verosimilitud resulta informativa

El riesgo de sobreajustar es real, pero **el ΔAIC del propio sobreajuste dice en
qué mundo se está**: con la verdad estacionaria la raíz añadida es espuria y se
paga como un parámetro de más (+0,6 a +1,1); con raíz unitaria el AR(p+1) mejora
mucho (−3,8 a −23,6) porque captura algo real.

Así que la rama publica ese ΔAIC como segundo dato, no como detalle.

## Fix

`shin_fuller_sobreajuste(model)` en `formal_tests.py`, y su presentación en el
informe justo donde antes se decía «sin par». Sobre el caso real (`PGAS_m20`, AR(2)
con pseudociclo de 8,6 trimestres):

```
⚠ Sin par confirmatorio. […] El lado AR no está disponible DIRECTAMENTE, y los
  contrastes de frontera se leen en pareja. Se recupera abajo por sobreajuste.

  Lado AR recuperado por SOBREAJUSTE (rama de diagnóstico, no un modelo):
  estimado un AR(3) en lugar del AR(2), su factorización sí ofrece una raíz real
  (φ̂=0.5174) y sobre ella el contraste existe.
  - Φ̂₁ᵤ=6.562 (crít 5%=1.75) → estacionario ✓ — d basta por el lado AR
  - ΔAIC del sobreajuste = +1.04 → la raíz añadida no compra nada: es espuria,
    que es lo esperado si no hay raíz unitaria.
  ⚠ No adoptes este modelo. Existe para poder preguntar; su última raíz es
    espuria por construcción cuando no hay raíz unitaria. Con esto el par queda
    recuperado: DCD por el lado MA, y este contraste por el lado AR.
```

**No es un modelo candidato** y se dice tres veces, porque el riesgo de esta rama
no es estadístico sino de uso: que alguien adopte el AR(p+1).

## Lo que no cubre

Un par complejo con módulo → 1 es no estacionariedad **en ω≠0**, y eso no lo
contrasta ni esta rama ni el `DCD_f` existente, que está calibrado para la
rejilla de frecuencias **estacionales**. Es la opción 3 —el contraste de módulo a
frecuencia libre— y queda como investigación, ligada a SF_MEG.

## Salvedad de la evidencia

Una sola frecuencia (ω = 0,12·2π), n=83, sin MA competidor, 40 réplicas por
celda. Basta para **decidir el diseño**, no para publicar tamaños: antes de
fijarlos hay que barrer frecuencia, n y la presencia de un MA, que es donde
Schwert (1989) encontró los problemas de tamaño de toda esta familia.
