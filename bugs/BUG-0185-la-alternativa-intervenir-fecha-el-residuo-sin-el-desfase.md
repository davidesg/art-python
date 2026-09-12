---
id: BUG-0185
title: La alternativa «Intervenir <fecha>» fecha el residuo extremo sin el desfase — sexto sitio de BUG-0172; en un modelo con raíz estacional propone intervenir el mes equivocado
status: fixed
severity: high
component: mcp_server
found_in: 0.2.1 @da5c6ad
fixed_in: 0.2.1
reported: 2026-09-12
reporter: Claude — run 8 de IPC_ES en Windows, carril guiado
tags:
  - fechas
  - desfase
  - intervenciones
  - regresion
references:
  - BUG-0172
  - BUG-0067
  - BUG-0105
---

## Summary

La 4ª sección de la iteración («DECISIÓN — alternativas») abre con
**«Intervenir <fecha>»** para el residuo más extremo. Esa fecha la calcula
`_fecha` dentro de `_alternativas_desde` (`mcp_server.py:1967`):

    _at_to_date(int(obs), start_year, start_per, freq)

`obs` es el índice **1-based sobre los residuos** (`diagnosis.py:756`,
`extreme = [(i + 1, z) ...]`), y `_at_to_date` espera un índice **0-based sobre
la serie**. Falta `− 1 + desfase_observaciones(model)`.

Con `d=1` y sin raíces estacionales el desfase es 1 y los dos errores se
cancelan: por eso no se había visto. En cualquier otro modelo la fecha sale
desplazada `desfase − 1` períodos:

| modelo | desfase | error de `_fecha` |
|---|---|---|
| d=0 | 0 | 1 período **tarde** |
| d=1 | 1 | ninguno (por casualidad) |
| d=1 + ifadf interior (B1 reformulado por el MEG) | 3 | 2 períodos **pronto** |
| d=1, D=1, s=12 (B2) | 13 | **12 meses** pronto |

Es el mismo defecto que BUG-0172 arregló en cinco sitios; éste es un sexto que
no calculaba el desfase **en absoluto**, así que el test de guardia de BUG-0172
(`test_ningun_sitio_vuelve_a_escribir_la_cuenta_a_mano`, que busca la cuenta
escrita a mano) no podía verlo.

## Reproduction

Run 8, IPC_ES 1/2002–11/2023, modelo `m11`: λ=0, d=1, **f=2 estocástica**
(`ifadf[2]=1`, consume 2), AR(1), μ, tres escalones. Residuos: 260 de 263,
**desde 4/2002**.

    estimate_and_diagnose(inp_path="IPC_ES_m10p.inp", output_path="IPC_ES_m11.inp")

- Diagnosis: `Residuos extremos (|z|>3): 3 — obs 237 (z=+3.76), …`
- Alternativa A: **«Intervenir 10/2021** (|z| = 3.76 …)
  `suggest_intervention_form(…, date="10/2021")`»
- El `.out` del mismo modelo: `Maximum: 1.158739 at 12/2021 (observation 237)`.

Sin MCP, con los ficheros de `bugs/BUG-0185-repro/`:

    PYTHONPATH=src python bugs/BUG-0185-repro/repro.py

    nobs=263  residuos=260  desfase=3
    residuo mayor: obs 237  z=+3.76
      _alternativas_desde._fecha : 10/2021
      con desfase_observaciones  : 12/2021   (el .out dice 12/2021)
    REPRODUCIDO

## Impact

No es una etiqueta: la alternativa trae **la llamada lista para ejecutar**,
`suggest_intervention_form(date="10/2021")`, y esa herramienta coloca la
intervención bien en la fecha que se le pide. Seguir la sugerencia —que en el
carril autónomo es lo que hace el LLM— **mete una intervención en un mes sin
suceso** y deja el anómalo real sin tratar. Treadway la juzgaría después sobre
ese mes, así que el error no se delata solo.

Afecta justo a los modelos que salen del MEG (B1 con una frecuencia pasada a
estocástica) y a toda la ruta B2, que es donde más intervenciones se piden. En
el run 8 no se siguió porque el analista comparó con el `.out`.

## Causa

`_alternativas_desde` se escribió antes de BUG-0172 y no pasó por su arreglo.
BUG-0172 centralizó la cuenta en `identification.desfase_observaciones` y
cambió los sitios que la escribían a mano; éste no la escribía de ninguna
manera.

## Fix propuesto

En `_fecha` de `_alternativas_desde`:

    from art.identification import desfase_observaciones
    return _at_to_date(int(obs) - 1 + desfase_observaciones(model), …)

(`model` ya llega como argumento; si es `None`, caer a `obs {obs}` antes que
fechar mal.)

Mismo patrón que `ltf.py:599`, que ya lo hace bien:
`_at_to_date(int(at) - 1 + int(desfase), …)`.

## Del mismo linaje, sin reproducir

Dos sitios siguen escribiendo la cuenta a mano **sin `ifadf`**, y el test de
guardia de BUG-0172 no los caza:

- `escalera.py:536` — `_desf = d + D·s` para el eje de fechas de la figura de la
  escalera. Partido en dos líneas con `\` y con `vivos[0].model` como objeto: la
  expresión regular del test exige `(\w+)` y una sola línea.
- `describe.py:3567` — `_desf = int(d) + int(D) * int(freq)` en la tabla de
  pares del escaneo pre-identificación. `describe.py` no está en la lista de
  ficheros que el test recorre. Sobre una serie sin modelo es correcto; la
  sección aparece también sobre residuos de modelos («Escaneo pre-identificación
  — Resid …»), y ahí, con `ifadf`, fecharía mal los pares.

Los dos son de etiqueta (no mueven el modelo), pero son la misma duplicación que
BUG-0172 quería impedir.

Observado en el mismo run, sin localizar en el código: en la **figura de
diagnosis** de los modelos con `ifadf` el eje de fechas parece empezar donde
empieza la serie y no donde empiezan los residuos. En `IPC_FR_m03` (dos raíces,
consumo 5) el último residuo se dibuja hacia 8/2019 cuando es 12/2019, y en
`IPC_ES_m04`/`m05` el extremo de 1/2016 aparece a la izquierda de la rejilla de
2016. Mismo síntoma que el de `_fecha`: un desfase que no cuenta las raíces
estacionales.

## Validation propuesta

- Test sobre el camino real: modelo con `ifadf` interior, residuo extremo
  plantado; la alternativa A debe nombrar la fecha del `.out`. Parametrizar con
  d=0, d=1, d=1+ifadf, D=1 — la tabla de arriba.
- Ampliar la guardia de BUG-0172: que `_alternativas_desde` importe
  `desfase_observaciones`, y añadir `describe.py` a la lista y la forma
  multilínea al patrón.

## Resolución (0.2.1)

Decisión del analista: entra en 0.2.1. *Publica un número incorrecto y calla* —la
fecha—, y la alternativa trae la llamada lista para ejecutar, que en el carril
autónomo el LLM sigue. Reproducido también en Linux con `repro.py`.

**Tres sitios, la misma cuenta.** Todos pasan a `desfase_observaciones`:

1. `_alternativas_desde._fecha` — el del informe: `obs − 1 + desfase`. Sin
   modelo no se sabe el desfase y se devuelve `obs N` antes que una fecha falsa.
2. **`describe._resid_start`** — el síntoma del eje que el informe dejó *«sin
   localizar en el código»*. Contaba `d + D·freq`, sin las raíces de `ifadf`, y
   alimenta cinco sitios: la figura de diagnosis, la de identificación sobre
   residuos y los escaneos de residuos. Cuadra al mes con lo observado: IPC_FR
   m03 consume 5 y se contaba 1, así que el último residuo se dibujaba 4 meses
   antes, en 8/2019 en vez de 12/2019.
3. `escalera.py:536` — la forma partida en dos líneas.

`describe.py:3141/3410/3567` **no se tocan**, y es deliberado: son el `d`/`D` del
propio escaneo, no los de un modelo. Sobre la serie original no hay `ifadf`, y
sobre residuos se llaman con `d=0, D=0` y una serie cuyo arranque ya da
`_resid_start`, que es donde estaba el error.

Verificado en el camino real: `estimate_and_diagnose` sobre `IPC_ES_m10p.inp`
propone ahora **«Intervenir 12/2021»**, lo mismo que el `.out`.

**Tests** — `tests/test_bug_0185_la_fecha_de_la_alternativa.py`:

- el caso del run 8 con los ficheros de `BUG-0185-repro/`: la alternativa y el
  `.out` dicen 12/2021;
- `_resid_start` con d=0, d=1, d=1+ifadf y D=1, contra una verdad
  **independiente**: alinear por la cola —el último residuo es la última
  observación—, no la propia `desfase_observaciones`;
- sin modelo no se fecha;
- la guardia de BUG-0172, ampliada a `describe.py`, a objetos con punto o
  índice y a la forma partida con `\`; con un caso que comprueba que caza la
  línea vieja de `escalera.py`.

Sin el arreglo fallan 5 de los 10 casos, entre ellos el del run 8.

