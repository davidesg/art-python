---
id: BUG-0031
title: the autonomous lane cannot specify a seasonal AR/MA at all — suggest_orders ranks (p,q,P,Q) but decide_orders returns only (p,q) and run_full builds its ModelSpec without ever touching P or Q
status: fixed
severity: high
component: policy
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-27
reporter: David / réplica TFM Bolivia
tags:
  - autonomous
  - identification
  - seasonality
  - unreachable-model
references:
  - src/art/policy.py (decide_orders / decide_seasonal_orders)
  - src/art/pipeline.py:797-816 (run_full: el ModelSpec sin P ni Q)
  - src/art/pipeline.py (_make_model, rama `if D == 0`: el motor ya sabía)
  - src/art/model_detection.py:436-447 (suggest_orders, P_max=Q_max=1)
  - bugs/BUG-0031-repro/repro.py
  - tests/test_bug_0031_seasonal_orders_unreachable.py
---

## Summary

`suggest_orders` busca sobre **(p, q, P, Q)** con `P_max = Q_max = 1`, y cada
spec que devuelve **lleva su par estacional**. Pero:

```python
def decide_orders(specs) -> tuple[int, int]:
    ...
    return int(top.p), int(top.q)        # P y Q se quedan aquí
```

y `run_full` construía el spec sin mencionarlos:

```python
p, q = pol.decide_orders(specs)
...
spec = ModelSpec(lam=lam, d=d, D=D, p=p, q=q,      # <-- sin P, sin Q
                 n_harmonics=n_harmonics, ...)      #     por defecto 0
```

**Resultado: el carril autónomo no podía montar un operador AR o MA estacional
nunca**, ni cuando la identificación colocaba uno EN CABEZA del ranking.

No producía un modelo peor. Producía uno **inalcanzable**.

## El motor nunca tuvo la culpa

`_make_model` monta desde siempre la combinación D=0 de "armónicos
deterministas **+** AR/MA estacional estacionario", y lo dice en su propio
comentario:

```python
    # Stationary stochastic seasonality on top of the deterministic harmonics:
    # a free annual AR/MA operator (no seasonal differencing). YW/HR-initialised.
    ar_s_val  = [ars_i] if P > 0 else []
```

Lo que faltaba era **el cable de la política al spec**. Es la forma exacta de
BUG-0013 (la media), BUG-0015 (el dominio) y BUG-0016 (la estacionalidad ante
`decide_d`), por quinta vez: *una decisión que el motor sabe ejecutar y la capa
de política no tiene por dónde pedir*.

## El testigo real — RATIO, réplica del TFM de Bolivia

Gasto/PIB de Bolivia, trimestral 2004:1–2024:4. La identificación encabeza con
un spec que **sí** lleva el operador anual:

```
suggest_orders(RATIO, d=1, D=0, lam=0):
   p=0 q=2 P=1 Q=0  sim=0.7832     <-- en cabeza, con AR estacional
   p=0 q=0 P=1 Q=0  sim=0.7696     <-- (esencialmente el modelo guiado)
   p=0 q=2 P=0 Q=1  sim=0.7612
   p=3 q=0 P=0 Q=0  sim=0.6694
```

El carril autónomo estimaba **(0,1,2) sin AR estacional** y cerraba así:

| | guiado (analista) | autónomo (antes) |
|---|---|---|
| ARMA | AR(1)₄ φ̂=0.7277 (t=+9.57) | MA(1)+MA(2) regulares |
| Q p-mín | 0.1443 ✓ | **0.0000** ✗ |
| AIC | 483.43 | 538.86 |
| veredicto | APROBADA | REVISAR |

El autónomo terminaba el bucle con la diagnosis rechazando el ruido blanco y
**sin ninguna forma de arreglarlo**: el bucle de rondas sólo añade
intervenciones, y ninguna intervención puede absorber una autocorrelación anual.

## Repro sintético y determinista

`bugs/BUG-0031-repro/repro.py` — serie trimestral I(1) de 120 observaciones cuya
primera diferencia es un **AR(1)₄ puro con φ₄ = 0.7**, semilla fija:

```
[1] identificación: el spec en cabeza lleva P=1 Q=0     (sim = 0.9511)
[2] decide_orders(specs) -> (0, 0)   (sólo el par regular)
    no existe decide_seasonal_orders: P y Q se pierden aquí
[3] modelo autónomo: p=0 q=0 | AR_s=0 MA_s=0
    Q min p = 0.0000   ruido blanco: NO
[4] el MISMO motor con P=1: AIC 575.96 -> 512.51, Q min p 0.0000 -> 0.1754
    ar_s = [[0.6782]]
```

El paso [4] es el que cierra el argumento: **el mismo `build_and_fit`, la misma
serie, el mismo λ/d/D — sólo P=1 — recupera φ̂₄ = 0.678 contra un 0.7 verdadero,
baja el AIC 63.5 puntos y convierte los residuos en ruido blanco.** El motor
podía; nadie se lo pedía.

En el repro λ, d y D van FIJADOS (vía `ClaudePolicy`) para que el único nodo que
decide la heurística sea el de los órdenes. Con `DefaultPolicy` pura esta serie
sintética decide además λ=1 y d=2 — otro asunto, que enturbiaría el testigo.

## Por qué no había saltado antes

Tres cosas lo tapaban a la vez:

1. **Con D=1 el problema no existe.** La rama `else` de `_make_model` también
   lee P y Q, pero una serie que diferencia estacionalmente rara vez necesita
   además un AR anual, así que los casos con D=1 pasaban limpios.
2. **Los armónicos absorben la parte determinista.** Una serie con
   estacionalidad determinista y nada estocástico encima sale bien sin P. El
   defecto sólo muerde cuando queda estacionalidad **estocástica** tras los
   armónicos — que es exactamente el caso B1 de RATIO.
3. **La diagnosis lo denunciaba y nadie lo leía como esto.** Q rechazando en los
   retardos 4, 8, 12 es la firma; se leía como "faltan términos ARMA", que es
   cierto pero no accionable, porque el bucle sólo sabe añadir intervenciones.

## Fix

Una función hermana en la capa de política, y el cable.

```python
def decide_seasonal_orders(specs) -> tuple[int, int]:
    if not specs:
        return 0, 0
    top = specs[0]
    P = int(getattr(top, "P", 0) or 0)
    Q = int(getattr(top, "Q", 0) or 0)
    if P >= 1 and Q >= 1:
        Q = 0          # constraint del backend, no criterio — ver abajo
    return P, Q
```

```python
p, q = pol.decide_orders(specs)
P, Q = pol.decide_seasonal_orders(specs)
...
spec = ModelSpec(lam=lam, d=d, D=D, p=p, q=q, P=P, Q=Q, ...)
```

`Policy` declara el método, `DefaultPolicy` delega en la regla, y `ClaudePolicy`
acepta `P=` y `Q=` del analista igual que ya aceptaba `p=` y `q=`. El par también
viaja ahora en `PipelineResult.P/Q`, para que quien presente el modelo pueda
decir qué se decidió.

### Función hermana y no un `decide_orders` de cuatro valores

El par regular y el estacional se deciden sobre **evidencia distinta** (los
retardos bajos del correlograma frente a los múltiplos de s), el carril guiado
los confirma como **actos separados**, y `decide_orders` arrastra un criterio de
dominio propio (el desempate AR(1)/MA(1) en series de precios) que no tiene nada
que decir sobre P y Q. Fundirlos habría metido dos decisiones en una firma.

### La guardia P≥1 ∧ Q≥1

El backend en C de fue **aborta** con un AR estacional y un MA estacional libres
en el mismo modelo (`_make_model` lo documenta; fue/TODO.md, entrada "AR_s+MA_s").
`suggest_orders` **sí** puntúa specs con (P=1, Q=1) —puntúa por similitud de
correlograma y no sabe nada del backend—, así que la guardia tiene que estar
aquí. Cuando el spec en cabeza pide los dos se conserva el AR y se descarta el
MA: en los retardos anuales un AR anida el decaimiento persistente que un MA
estacional sólo puede cortar en el retardo s, y un AR de más se delata luego como
cuasi-cancelación que el DCD puede contrastar — un MA que se cayó no deja nada
que mirar.

Es una **restricción, no un criterio**, y por eso se anuncia en el docstring en
vez de aplicarse en silencio.

## Lo que NO arregla

El bucle de rondas sigue sin reconsiderar los órdenes. Si el par (p,q,P,Q)
elegido en la primera pasada deja Q rechazando, el autónomo añade intervenciones
—que no pueden absorber autocorrelación— y cierra en REVISAR. Este arreglo hace
que el par de partida sea el que la identificación pidió; no le da al bucle la
capacidad de reformularlo. Eso es §5.x del ARCHITECTURE_REVIEW y va aparte.
