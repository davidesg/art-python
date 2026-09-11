---
id: BUG-0172
title: La regla de Treadway lee los residuos DESPLAZADOS cuando hay raíces estacionales integradas — publica «2 de 4 pasan» donde pasan las cuatro
status: fixed
severity: critical
component: interventions
found_in: 0.1.0
fixed_in: 0.2.1
reported: 2026-09-11
reporter: David — run 3 de SF_MEG, incidencia C-21
tags:
  - intervenciones
  - treadway
  - numero-incorrecto
references:
  - BUG-0030
  - BUG-0089
  - BUG-0140
---

## Summary

`check_intervention_fit` mapea la fecha de una intervención al índice de los
residuos con:

```python
desfase = int(model.d) + int(model.D) * freq
ini = int(itv.at) + 1 - desfase
```

**Cuenta `d` y `D`, y no cuenta `ifadf`.** Cada raíz estacional estocástica
consume observaciones: un factor de frecuencia interior `(1 − 2cos(ω)B + B²)`
consume **2**, el de Nyquist `(1 + B)` consume **1**.

Sobre `B_m11` del run 3, con **dos** frecuencias reformuladas (f=2 y f=3), son
**4 observaciones**, y Treadway lee los residuos **4 meses después** de las
fechas intervenidas.

## Impact — publica un VEREDICTO incorrecto

No es una etiqueta mal puesta: es la regla que decide si una intervención
funcionó. Publicado:

    2 de 4 pasan la regla de Treadway
    3/2022  +0.81  −0.29  **−2.91**  +0.09   ← NO absorbido
    9/2021  +1.09  +1.70                      ← NO absorbido

Los z reales, leídos del `.out` con su fecha:

    3–6/2022   −0.46  −0.70  −0.09  +0.74
    9–10/2021  −0.48  −0.15
    1–2/2021   +0.64  +1.10
    12/2021    +0.51

**Las cuatro pasan.** Y los publicados coinciden exactamente con `t+4`: el −2.91
es el residuo de **09/2022**, no el de 03/2022.

La consecuencia es la que el nodo entero existe para evitar: un vecino anómalo
falso es «evidencia de que la representación elegida es errónea», así que empuja
a cambiar la forma de una intervención que está bien puesta — o a añadir otra.

Es la familia de las fechas desplazadas en figuras (C-10, C-11c del run)
convertida en veredicto.

## Repro

Un modelo con `ifadf` activo en una o dos frecuencias y una intervención de
fecha conocida: los `fechas` que devuelve `check_intervention_fit` apuntan
`sum(consumo por ifadf)` observaciones más allá de la intervenida.

    consumo = Σ (2 si f interior, 1 si f == s/2)  sobre las f con ifadf[f] == 1

## No eran dos sitios: eran ONCE

«Conviene revisar los demás» se quedó corto. El censo del fuente encontró **once**
sitios haciendo la misma cuenta a mano, todos sin `ifadf`:

| sitio | qué desplazaba |
|---|---|
| `interventions.py` · Treadway | los residuos que juzgan la intervención |
| `mcp_server.py` · `suggest_intervention_form` | **DÓNDE se coloca la intervención pedida** |
| `mcp_server.py` · `guided_intervention` llamada 2 | la fecha del episodio |
| `mcp_server.py` · `guided_intervention` llamada 1 | las fechas de la tabla de calibración |
| `mcp_server.py` · `intervention_plot` | la fecha de la superposición |
| `mcp_server.py` · `residual_episodes` | el fechado de los episodios |
| `mcp_server.py` · escaneo y autoscan (×3) | las fechas de las distorsiones |
| `configuracion.py` | el arranque de cada configuración candidata |
| `escalera.py` | el arranque de los peldaños |

**Y el segundo no desplaza una etiqueta: desplaza el modelo.** Sobre
`ES_CPI_B_m11` —dos frecuencias reformuladas, consumo 4— una intervención pedida
para 03/2022 se colocaba en 07/2022.

## Fix

**Una sola función**, `identification.desfase_observaciones(model)`:

    d          cada diferencia regular consume 1
    D · s      cada diferencia estacional consume s
    ifadf[f]   cada raíz estacional consume el GRADO de su factor:
               2 en frecuencia interior (1 − 2cos(ω)B + B²), 1 en Nyquist (1 + B)

Verificada **contra el recuento real de residuos del motor**, no contra el
razonamiento, en siete combinaciones de `(d, D, ifadf)` y en los cuatro modelos
del run 3:

    B_m11  n=293  nres=288  ifadf=[2,3]  desfase 5  ✓
    B_m08  n=293  nres=290  ifadf=[2]    desfase 3  ✓
    A_m06  n=216  nres=213  ifadf=[3]    desfase 3  ✓
    B_m01  n=293  nres=292  ifadf=[]     desfase 1  ✓

Y Treadway sobre `B_m11`, que es el caso que lo destapó:

    step    03/2022  z [−0.50, −0.74, −0.09, +0.76]  ✓ absorbido
    step    09/2021  z [−0.47, −0.24]                ✓ absorbido
    step    12/2021  z [+0.56]                       ✓ absorbido
    impulse 01/2021  z [−0.39]                       ✓ absorbido

    4 de 4 pasan la regla     (el run publicó «2 de 4»)

Los z coinciden con los que el analista leyó a mano del `.out`.

**La prueba que importa no es ninguna de ésas**: es la que recorre el FUENTE y
falla si alguien vuelve a escribir `d + D·s` a mano. Escrita en once sitios era
una costumbre — basta que se añada un operador nuevo para que vuelva a divergir.

*(Nota de método: la primera versión de esa prueba usaba `re.S` sin acotar y
cruzaba líneas hasta una `D` lejana, marcando como defecto un `d_reg` que es otra
cosa. Una prueba sobre el fuente tiene que acotar su ventana o inventa
defectos.)*

## Validation

Con `ifadf` activo, los residuos que Treadway lee en una fecha intervenida tienen
que ser los de esa fecha — comprobado contra el `.out`, que los trae fechados. Y
sin `ifadf` nada cambia.
