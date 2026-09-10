---
id: BUG-0145
title: Los años del eje temporal se solapan en series trimestrales largas — pyfug fija el paso en dos años y encoge la figura
status: open
severity: medium
component: figuras
found_in: 0.2.0
fixed_in:
reported: 2026-09-10
reporter: David
tags:
  - figuras
  - pyfug
references: []
---

## Summary

En la figura de identificación (serie estandarizada + acf/pacf) **los rótulos de
año del eje temporal se pisan entre sí y no se leen** cuando la serie es
trimestral y cubre más de unos 20 años. Apareció con el PIB de la eurozona
(`PIB_EZ19`, 1995T1–2019T4, 100 obs.): los 13 rótulos, de 1994 a 2018, forman
una tira continua de dígitos.

Las mensuales de longitud parecida no lo sufren. El WTI 2002-2019 (18 años) y
2002-2023 (22 años) se leen bien.

La figura no la dibuja `art` sino **`pyfug`**: `describe_identification`
(`describe.py:752`) llama a `_pyfug_combined`, que es
`pyfug.graphics.combined.plot_combined`. El arreglo va en `pyfug`; se registra
aquí porque es donde el analista lo ve, en las figuras que devuelven
`identification_analysis` y `guided_identification`.

## Impact

- Toda serie trimestral de más de ~20 años sale con el eje ilegible, y a partir
  de ahí va a peor: con 40 años se solapan los 20 pares de rótulos.
- Afecta a las figuras que se proyectan en clase y a las que se copian a los
  informes. Es lo primero que ve el alumno del gráfico estándar de la escuela.
- Menor: `first_yr` redondea hacia abajo al año par, así que una serie que
  empieza en 1995 lleva rótulo y divisoria en 1994, antes del primer dato.

## Reproduction

Llama a la misma función que la herramienta MCP, intercepta la figura en
`savefig` y mide los rótulos con el renderer real (sin mirar la imagen):

```python
import warnings; warnings.filterwarnings("ignore")
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.figure as mfig
from fue import TimeSeries
from art.describe import describe_identification

cap = []; _orig = mfig.Figure.savefig
mfig.Figure.savefig = lambda s, *a, **k: (cap.append(s), _orig(s, *a, **k))[1]

def solapes(freq, n, y0):
    rng = np.random.default_rng(0)
    y = 100 * np.exp(np.cumsum(0.004 + 0.006 * rng.standard_normal(n)))
    cap.clear()
    describe_identification(TimeSeries(y, freq=freq, start=(y0, 1), name="S"),
                            d=1, D=0, lam=0.0)
    fig = cap[-1]; fig.canvas.draw(); r = fig.canvas.get_renderer()
    ax = max(fig.axes, key=lambda a: a.get_position().width)   # panel de la serie
    bb = [t.get_window_extent(r) for t in ax.get_xticklabels() if t.get_text()]
    return len(bb), sum(a.x1 > b.x0 for a, b in zip(bb, bb[1:]))

for freq, n, y0 in [(4, 100, 1995), (12, 216, 2002), (12, 263, 2002), (4, 160, 1980)]:
    print(freq, n, y0, "rótulos=%d solapados=%d" % solapes(freq, n, y0))
```

Resultado (pyfug 2.0.0):

| Serie | Rótulos | Pares solapados |
|---|---|---|
| trimestral, 100 obs. (25 años) | 14 | **13** |
| mensual, 216 obs. (18 años) | 10 | 0 |
| mensual, 263 obs. (22 años) | 11 | 0 |
| trimestral, 160 obs. (40 años) | 21 | **20** |

Medidas en el caso trimestral: figura de 12,0 × 5,5 in a 150 dpi; panel de la
serie de 1.092 px; rótulo de año de 17,2 pt, 91 px de ancho; separación
disponible, unos 80 px por rótulo. En el mensual de 22 años: figura de 15,0 in,
panel de 1.403 px, 128 px por rótulo.

## Root cause

`pyfug/graphics/combined.py`, `plot_combined`. Tres decisiones fijas que se
combinan:

1. **El ancho de la figura depende de los retardos, no del eje temporal:**
   `figw = 15.0 if size == 2 else 12.0`. Una trimestral lleva menos retardos
   (`size == 1`) y sale un 20 % más estrecha justo cuando tiene más años por
   pulgada.
2. **El rótulo de año tiene tamaño fijo:** `JT_FONT_YEAR = 17.2`
   (`graphics/base.py:31`), heredado de FUG en C.
3. **El paso entre rótulos es fijo:** `step = 2 if (x1 - x0) > 5 else 1`. No
   mira ni cuántos años hay ni cuánto mide el panel. Y
   `first_yr = (int(x0) // step) * step` redondea hacia abajo al año par,
   que es lo que produce el rótulo de 1994 en una serie que empieza en 1995.

## Fix

En `plot_combined`, elegir el paso del eje temporal según el espacio disponible,
no fijo:

- después de crear el eje, estimar el ancho de un rótulo de cuatro cifras a
  `JT_FONT_YEAR` y el ancho del panel en píxeles;
- tomar el menor paso de {1, 2, 5, 10} que deje sitio entre rótulos;
- mantener las divisorias verticales en los años rotulados;
- empezar en el primer múltiplo del paso **dentro** de la muestra
  (`ceil(x0 / step) * step`), no antes.

Así no se toca la estética heredada de FUG (tamaño de letra, proporciones de
los paneles), que es la razón de que esos valores sean fijos.

## Validation

- El repro de arriba debe dar 0 pares solapados en los cuatro casos.
- Añadir el caso trimestral de 25 años a la batería de figuras.
- Comprobar que el mensual de 18 años conserva el paso de 2 años, para no
  cambiar las figuras que ya se ven bien.
