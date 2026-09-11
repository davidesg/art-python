---
id: BUG-0161
title: El denominador δ(B) está cableado de punta a punta —se escribe, se lee, se estima, se dibuja— y no hay ninguna superficie que lo construya
status: fixed
severity: high
component: interventions
found_in: 0.2.0
fixed_in: 0.2.1
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

## Fix

**1 · `n_delta` en las dos puertas.** `suggest_intervention_form` y
`guided_intervention`; `n_delta=0` es el comportamiento de siempre. Con
`form="impulse", n_omega=1, n_delta=1` sale la forma racional ω₀/(1−δB): salta y
decae, en **dos parámetros** donde N escalones gastan N.

**2 · La semilla va en 0.0, y eso está MEDIDO.** Sobre el testigo con δ=0,6:

    semilla  0,0 / 0,5 / −0,5   →   δ̂ = 0,5692   AIC 1616,41   ~14 iteraciones
    semilla  0,9                →   δ̂ = 0,7070   AIC 1864,56   500 iteraciones,
                                                  gradiente sin anular

Una semilla cerca de la raíz unidad manda el ajuste a un óptimo espurio **248
puntos de AIC peor**, y llega con números de aspecto normal. Hay una prueba que
fija la semilla y otra que comprueba que el testigo sigue separando las dos.

**3 · Y δ entra en `admissibility_problems`.** No estaba, y hasta ahora daba
igual porque no podía haber ninguno. Al abrir el grifo pasa a importar mucho:
**es el operador con la lectura más brutal si se va.** Una raíz de δ dentro del
círculo unidad es una respuesta **explosiva** —el efecto crece sin límite en vez
de decaer— y, a diferencia de un MA no invertible, **la diagnosis no lo delata**:
los residuos pueden salir perfectos mientras la respuesta que el modelo AFIRMA es
imposible. Se distingue «dentro» de «frontera», como en los demás operadores.

`fue` guarda δ(B) = 1 − δ₁B − δ₂B², la MISMA convención que el AR, así que los
coeficientes van tal cual a `_raices_factor`; que `test_intervention` calcule
δ(1) = 1 − Σδᵢ es la comprobación de que ésa es la lectura.

## Lo que NO se ha hecho, y es una decisión

**Proponerla.** La forma racional compite con el peldaño 2 de la escalera —N
escalones— y no están anidadas ni cuestan lo mismo, así que la comparación no la
arbitra el AIC solo: pide un peldaño nuevo en `escalera_de_ockham` con su propio
criterio de subida, y eso es diseño del método, no un argumento más. Se abre el
grifo y se deja la propuesta para cuando el criterio esté pensado. Ofrecer una
forma sin saber cuándo recomendarla sería repetir lo que BUG-0156 acaba de
arreglar: dos instrumentos sin jerarquía.

## Validation

`tests/test_bugs_0161_0163_el_denominador.py`. Sobre un testigo con respuesta
que decae —ω₀·δᵏ con δ=0,6— construido **por la superficie**, que es lo que el
defecto decía imposible: se construye el δ, se recupera 0,5692 contra la verdad
0,6, y sin `n_delta` nada cambia. Más el guardián: un δ=1,2 se anuncia con su
raíz en 0,833 «dentro», un δ=1,0 como «frontera» y un δ=−0,8 como admisible.
