---
id: BUG-0091
title: `get_out_report` no lee el `.out` — lo vuelve a fabricar estimando, y su docstring invita a pasarle un `.pre`, con lo que devuelve un informe 247% desviado del que está en disco
status: fixed
severity: high
component: mcp-tools
found_in: 0.1.12
fixed_in: 0.1.12
reported: 2026-09-05
reporter: David / Claude — estudio del contrato de ficheros
tags: [contrato, out, covarianza, arquitectura]
references:
  - docs/ESTUDIO-contrato-de-ficheros-y-semillas.md §4-V2 y §4-V3
  - src/art/mcp_server.py:7292 (get_out_report)
  - src/art/diagnosis.py:216 (AVISO_COV_CASI_SEMILLA — apunta al `.out`)
  - BUG-0090 (la misma raíz)
---

## Summary

`get_out_report` es la única herramienta cuyo propósito declarado es devolver el
registro de la estimación. **No lo lee**: lo vuelve a fabricar.

```python
ts, m = _load_ts_model(inp_path)
m.fit()                      # ← reestima
out_text = m.write_out()     # ← y genera el informe otra vez
```

Y su docstring dice: *«inp_path : path to the .inp or **.pre** file»* — invita al
camino equivocado justo donde más duele.

## Impact

Medido contra el `.out` que está en el mismo directorio:

```
get_out_report(.inp)  vs el .out en disco  →  desviación   0.0%
get_out_report(.pre)  vs el .out en disco  →  desviación 247.3%
```

Y hay una consecuencia de segundo orden, más grave que la primera. El `.out` es
**la única constancia fiel de la covarianza** —la curvatura no es recuperable de
un fichero que sólo guarda el óptimo (BUG-0090)— y art lo sabe: su propio
`AVISO_COV_CASI_SEMILLA` le dice al analista

> *«el `.out` del modelo trae la covarianza completa»*

pero **no existe ninguna herramienta que la lea**. El aviso da una instrucción
que la herramienta no puede ejecutar, así que la ejecuta el LLM parseando texto
a mano, o no se ejecuta.

## Fix (propuesto)

Un lector del `.out` —`art.outfile`— que devuelva parámetros, covarianza y
diagnosis. Con él:

- `get_out_report` lee el fichero si existe, y sólo reestima si falta,
  diciéndolo;
- la ecuación con SE se rinde **sin estimar nada** (verificado: out/inp = 1.000
  en los 15 parámetros);
- el aviso de la covarianza pasa a ser ejecutable;
- y la herramienta de evidencia del guion —volver a un nodo y ver el último
  modelo con su diagnosis— deja de necesitar una reestimación dirigida por el
  LLM, que es lo que la hacía cara en tokens.

## Validation

Que `get_out_report` sobre un `.inp` con `.out` hermano devuelva **byte a byte**
lo que hay en disco, y que sobre un modelo sin `.out` reestime **diciendo que lo
hace**. Y que la covarianza leída coincida con la estimada (out/inp = 1.000).

---

## Fix (aplicado, 2026-09-05)

**1. `art/outfile.py` — el lector que faltaba.** `lee_out(path)` devuelve una
`LecturaOut` con parámetros (valor, SE, índice, bloque), matriz de covarianzas,
sigma²/sigma/ℓ, criterios de selección, la especificación (λ, d, D, s),
convergencia (iteraciones, norma del gradiente) y las estadísticas de residuos
(media, JB, asimetría, curtosis, mínimo y máximo con su fecha).

Dos decisiones que valen la pena:

- **Acepta cualquier hermano de la terna.** `lee_out("X.inp")` encuentra
  `X.out`. Exigir la extensión exacta trasladaría al llamante una regla que este
  módulo ya conoce.
- **Lectura defensiva.** Un `.out` de otra versión del motor, truncado o con una
  sección ausente devuelve esa sección a `None` y el resto poblado; sólo levanta
  si el fichero no existe. Hay una prueba con un `.out` cortado a 20 líneas.

Y el `.out` resultó más rico de lo que el reporte suponía: cada parámetro viene
ya como `valor (SE) [índice]`, así que las desviaciones típicas no hay ni que
derivarlas de la covarianza. Se leen las dos y **coinciden**: hay una prueba que
comprueba `SE == sqrt(diag(cov))` en todos los parámetros, porque si las dos vías
del mismo fichero no cuadran, una está mal leída.

**2. `get_out_report` lee el fichero.** Si hay `.out` hermano, lo devuelve tal
cual y dice que lo está leyendo. Si no lo hay, estima **y lo dice**: «este informe
se ha REESTIMADO ahora — no es el registro de la estimación original», más el
aviso de BUG-0090 si además vino de un `.pre`.

Verificado sobre el corpus: las tres extensiones de la terna devuelven ahora el
mismo registro byte a byte — **incluido el `.pre`**, que antes daba 247% de
desviación.

## Un fallo del lector que la comprobación cruzada cazó

La primera versión devolvía `sigma2 = 2.0`. El `_num` buscaba el primer número de
la línea y se comía **el dígito de la etiqueta** (`sigma2:`). Las etiquetas del
`.out` llevan número —`sigma2`, `x[ 1]`, `AR factor 1`— así que hay que cortar
por los dos puntos. Lo delató comparar `sigma2` con `sigma²`; hay una prueba que
fija exactamente eso.

## Validation — resultado

`bugs/BUG-0091-repro/repro.py` — autónomo, construye su propia terna. Sale 0:

```
== A. Se LEE el registro, venga por donde venga de la terna
   R91.inp / R91.pre / R91.out  →  devuelve el .out en disco: True
== B. Sin `.out`, se reestima Y SE DICE: True
== C. SE == sqrt(diag(covarianza)): True
== D. Un `.out` truncado no revienta: completo=False, sin excepción
```

`tests/test_bug_0091_lector_del_out.py`, 13 pruebas.

## Lo que esto desbloquea

Con el lector puesto, y sin escribir nada más:

- el aviso de `AVISO_COV_CASI_SEMILLA` pasa a ser **ejecutable**: ya se puede ir
  al `.out` a por la covarianza que recomienda;
- la **ecuación con SE se rinde sin estimar nada** (out/inp = 1.000 en los 15
  parámetros, verificado);
- y la herramienta de evidencia del guion —volver a un nodo y ver el último
  modelo con su diagnosis— deja de necesitar una reestimación dirigida por el
  LLM, que es el coste que abrió toda esta línea de trabajo.
