---
id: BUG-0161
title: El denominador δ(B) está cableado de punta a punta —se escribe, se lee, se estima, se dibuja— y no hay ninguna superficie que lo construya
status: open
severity: high
component: interventions
found_in: 0.2.0
fixed_in:
reported: 2026-09-11
reporter: David — «¿tenemos una función que crea/modifica las intervenciones en forma de FLT?»
tags:
  - intervenciones
  - flt
  - superficie
references:
  - BUG-0076
  - BUG-0090
  - BUG-0157
  - BUG-0162
  - BUG-0163
---

## Summary

La función de transferencia de una intervención es **ω(B)/δ(B)**. art tiene el
numerador y no tiene el denominador — no porque no lo soporte, sino porque
**nadie lo construye**.

El censo, medido y no supuesto:

| | |
|---|---|
| sitios que **leen** δ (`diagnosis`, `full_report`, `interventions`, `ltf`) | 18 |
| líneas de `pipeline.py` que **escriben** δ en el `.inp` | 8 |
| sitios en todo `src/art/` que **construyen** un δ (`delta=[…]`) | **0** |

Y el sello empírico: **216 `.inp` leídos** del corpus de casos y de la réplica
del TFM, **0 intervenciones con δ**. La forma racional no se ha usado nunca en
ningún modelo que art haya producido, porque no se puede producir.

## El motor sí sabe

No es una limitación de `fue`. Sobre un testigo sintético con respuesta que
decae —ω₀/(1−δB) con δ=0,6 y ω₀=−8 sobre un impulso— construyendo la
intervención **a mano**:

    fue.Intervention("impulse", at=70, omega=[0.0], omega_free=[True],
                     delta=[0.0], delta_free=[True])

    _write_inp  → escribe el orden y el coeficiente de δ, correctamente
    estimar     → niter=14
    δ̂ = 0,5692   (verdad 0,6)
    ω̂ = −777,09  (verdad −800 en la escala ×100·log)

**Todo el camino funciona.** La tubería está puesta de punta a punta y no tiene
grifo.

## Dónde falta el grifo

La superficie que construye intervenciones toma tres de las cuatro cosas que
definen una FLT:

| | parámetro | valores |
|---|---|---|
| forma funcional | `form` | `step` · `pulse`/`impulse` · `ramp` |
| fecha de inicio | `date` | `"Q3/2008"`, `"03/2008"`, `"2008"` |
| orden de ω | `n_omega` | N coeficientes libres |
| **orden de δ** | — | **no existe** |

Es así en las dos puertas que lo hacen —`guided_intervention` y
`suggest_intervention_form`— y en los dos constructores internos
(`escalera.escalera_de_ockham`, `configuracion.evalua_configuraciones`), que
montan siempre `omega=[0.0]*n, omega_free=[True]*n` sin tocar δ.

*(Lo que NO falta es el retardo muerto. `fue.Intervention` no tiene campo `b` y
no lo necesita: ω(B)·Bᵇ es ω(B) con b ceros de cabeza, y `at` mueve el arranque.
`art.ltf` lleva `b=` sólo como comodidad de dibujo. Lo apunté como hueco al hacer
el censo y el analista lo corrigió.)*

## Impact

Alto, y es de método, no de comodidad.

**Una respuesta que decae no se puede representar.** Con sólo numerador, una
recuperación gradual hay que aproximarla con N escalones —un parámetro por
período— donde la forma racional gasta dos. Es la diferencia entre describir un
mecanismo y ajustar una curva: δ **es** la tasa de decaimiento, y tiene lectura
sustantiva («el efecto se disipa a un 57 % por trimestre»); los N ω no la tienen.

Y conecta con BUG-0157. La escalera se queda sin peldaños ante un suceso con
vuelta diferida y dice «ninguna forma resuelve el suceso». Una de las formas que
podrían resolverlo —respuesta que sube y decae— está fuera del catálogo **no
porque se haya evaluado y descartado, sino porque no se puede construir**. El
analista lee «ninguna forma» y entiende «ninguna existe», cuando lo cierto es
«ninguna de las que sé montar».

## Repro

```python
import glob, fue
con = [f for f in glob.glob("cases/**/*.inp", recursive=True)
       if any(getattr(i, "delta", None) for i in (fue.load(f)[1].interventions or []))]
assert con, "ningún .inp del corpus lleva δ"        # falla: la lista está vacía
```

Y sobre el fuente:

```bash
grep -rn "delta=\[" src/art/          # 0 resultados
grep -rn "\.delta\b\|delta_free" src/art/ | wc -l   # 18
```

## Fix propuesto

Abrir `n_delta` en las dos puertas que construyen, y pasarlo a
`fue.Intervention(delta=[0.0]*n_delta, delta_free=[True]*n_delta)`. El resto del
camino ya funciona, medido arriba.

Lo que hay que decidir con criterio —y lo que hace que esto no sea un parámetro
más— es **cuándo proponerla**. La forma racional cuesta un parámetro y compra
una cola infinita, así que compite directamente con el peldaño 2 de la escalera
(N escalones). La comparación es legítima: no están anidadas y cuestan distinto,
así que decide el AIC más la firma en los residuos, no el AIC solo. Eso pide un
peldaño nuevo en `escalera_de_ockham`, no sólo un argumento.

## Validation

Que `guided_intervention(form="impulse", n_delta=1)` produzca un `.inp` con δ,
que se estime, y que `test_interventions` publique δ̂ y la ganancia — esto último
es **BUG-0163**, que hoy no lo hace ni con un δ construido a mano.

Y sobre el testigo sintético de decaimiento: recuperar δ=0,6 dentro del error
típico, y que el AIC de la forma racional (2 parámetros) gane al de los N
escalones que hoy haría falta.
