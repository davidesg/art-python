---
id: BUG-0149
title: La superposición de la llamada 2 dibuja la hipótesis en el NIVEL sobre residuos en ∇ y en la fecha del episodio, no en la de la configuración
status: fixed
severity: high
component: figuras
found_in: 0.2.2
fixed_in: 0.2.1
reported: 2026-09-10
reporter: David — corrida guiada fase 1, ITCER
tags:
  - fase-1
  - figuras
references:
  - BUG-0135
  - BUG-0138
  - BUG-0140
---

## Summary

La figura de la llamada 2 de `guided_intervention` —la que existe para contestar
«¿qué forma se adapta a los datos?» (BUG-0138)— superpone la hipótesis de forma
sobre lo observado, y **las dos cosas que dibuja están mal**:

1. **La sombra.** Sobre ITCER (λ=0, d=1) con la configuración `Q2/2008×3`
   sombrea **2008Q4 → 2012Q4, 17 trimestres**, para un suceso de tres. En la
   llamada sobre `Q2/2009` sombrea 2009Q2 → 2013Q2.
2. **El escalón propuesto.** Sale como una línea casi plana rotulada
   `hypothesis × -0.0219` (y `× -0.00325` en 2009): la escala por mínimos
   cuadrados se hunde a cero, la forma no se parece a la que el texto propone y
   el panel de restos es, a efectos prácticos, el residuo sin intervenir.

Además la hipótesis se coloca en la fecha del EPISODIO (Q4/2008) y no en el
arranque de la configuración que rotula el título (Q2/2008): dos períodos tarde.

Lo vio el analista: «el gráfico que propone la intervención la solapa con los
datos; la sombra está mal y el escalón que se propone también».

## Impact

Es la figura que el analista usa para aceptar o discutir la forma antes de
construirla, y lo que enseña no es la hipótesis que se propone. Con la sombra
de 17 períodos y una línea plana, la figura no permite juzgar la forma; y un
analista que se fíe de ella concluiría que la hipótesis no explica nada
(R² = 0,01) cuando sobre el soporte correcto explica el 59 %.

Afecta a toda llamada 2 sin `escalera` sobre un modelo con d ≥ 1 y entrada
escalón — que es el caso por defecto del nodo.

## Reproduction

Residuos de ∇ln ITCER + μ (el m00 de la corrida), ω de la configuración
`Q2/2008×3` estimada por el propio nodo (convenio fue: −4,8225, 5,4453,
10,8961):

```python
import numpy as np, pandas as pd
from art.ltf import superpone
df = pd.read_csv("replica/datos_2004_2024.csv")
w = np.diff(100*np.log(df["ITCER"].values)); e = w - w.mean()
lab = [f"{a}{q}" for a, q in zip(df.ANIO, df.TRIMESTRE)][1:]
om = [-4.8225, 5.4453, 10.8961]
for d, fecha in [(0, "2008Q4"), (1, "2008Q4"), (1, "2008Q2")]:
    sp = superpone(e, lab.index(fecha) + 1, om, d=d, ventana=8)
    print(d, fecha, round(sp.escala, 4), sp.soporte, round(sp.r2, 3))
```

| llamada | escala | soporte (sombra) | R² |
|---|---|---|---|
| **como hoy**: `d=0`, `at` = episodio (Q4/2008) | **−0,0219** | **17** (2008Q4‥2012Q4) | 0,010 |
| `d=1`, `at` = episodio | −0,1122 | 3 (2008Q4‥2009Q2) | 0,008 |
| `d=1`, `at` = arranque de la configuración (Q2/2008) | **+0,9686** | **3** (2008Q2‥Q4) | **0,588** |

La primera fila reproduce al decimal la figura publicada (`× -0.0219`, sombra
hasta 2012Q4). La última es lo que debería verse: escala ≈ 1 —como corresponde
a unos ω que son los estimados— y la sombra sobre los tres trimestres del
suceso.

## Root cause

`mcp_server.py`, llamada 2 de `guided_intervention` (≈ l. 7364):

```python
_fig2 = describe_superposicion(
    m._result.residuals, at=int(ep.inicio),
    omega=_om, entrada=_ent, ...)
```

**a) Falta `d=`.** `describe_superposicion` / `superpone` toman `d=0` por
omisión, así que `respuesta_flt` simula la respuesta al escalón **en el
nivel** (`srf` acumulada), mientras que lo observado son **residuos en ∇**. Un
escalón permanente en el nivel no vuelve nunca a cero, y el «soporte efectivo»
de `superpone` se define como el último índice con respuesta ≠ 0
(`nz[-1]`), así que el soporte es toda la ventana simulada,
`K = max(s + ventana, 2·ventana) = 16` → 17 períodos de sombra. Y la escala por
el origen divide la suma de 17 residuos ∇ (≈ 0) por 17·ω(1)² → ≈ 0: la línea
plana. El eje, de paso, dice `level` porque también lo decide `d`.

`superpone` documenta que «`observado` está diferenciado, así que la respuesta
hay que diferenciarla igual»; el llamador no le pasa con qué.

**b) `at=int(ep.inicio)`** es la fecha del extremo que abrió el episodio, no
el arranque de la configuración que se dibuja (`mejor.fecha`). Para
`Q2/2008×3` son dos períodos de diferencia, y la hipótesis cae desplazada
sobre datos que no le corresponden.

## Fix

En la llamada: `d=int(m.d)` (con D·s si D>0 — hoy `respuesta_flt` sólo cubre
d∈{0,1}, que debe decirse en vez de dibujar mal), y `at` = posición en el
índice de los residuos del arranque de `mejor` (`mejor.fecha` menos el desfase
`d + D·s`, con el mismo convenio de BUG-0067/0140).

Y en `superpone`, cinturón: si `observado` son residuos de un modelo
diferenciado y llega `d=0`, que lo diga; el soporte para la sombra es el de la
hipótesis en el espacio de lo observado, no «hasta que la respuesta sea cero»,
que en el nivel es infinito.

## Fix aplicado (11-sep-2026), y una corrección al diagnóstico

**De las dos causas, sólo una explica el síntoma.** Al arreglarlo se midió:
con el soporte acotado al operador, pasar `d=0` sobre datos en ∇ da escala
0,979 frente a 0,979/1,029 con `d=1`. **El desplome a ×−0,0219 lo producía
enteramente el soporte**, no el `d` que faltaba. Contar mal la causa es cómo se
arregla el síntoma y se deja el mecanismo, así que queda dicho.

El arreglo de fondo, en `superpone`:

```python
fin_sop = min(_fin_resp, max(0, len(omega) - 1 + int(b)))
```

El soporte de una intervención es el de su OPERADOR —tantos períodos como
coeficientes ω—, que vale en los dos espacios y no depende de que la respuesta
decaiga. El criterio anterior, «hasta que la respuesta sea cero», sólo funciona
en ∇.

Los dos argumentos que faltaban se pasan igual, porque son defectos reales: `d`
gobierna el rótulo del eje y la forma simulada, y `at` desplazaba la hipótesis
dos períodos sobre datos que no le corresponden. Y `superpone` rechaza ahora
`d=2` diciéndolo, en vez de dibujar una rampa como si fuera un escalón.

Verificado sobre el caso del analista:

```
                    antes            ahora
sombra              17 trimestres    3
escala              ×−0,0219         ×0,979
R² en el soporte    —                0,980
eje                 level            ∇
```

## Validation

Prueba con la tabla de arriba: la llamada 2 sobre ITCER m00 en Q4/2008 debe
producir escala ∈ (0,9; 1,1), soporte 3 y sombra con arranque en 2008Q2. Y una
de frontera, como la de BUG-0147: la figura que devuelve la herramienta, no la
función suelta.
