---
id: BUG-0105
title: Un solo residuo |z|>3 declara NO SOSTENIBLE un modelo que el mismo informe acaba de aprobar — y con n=215 la mediana del máximo |z| bajo especificación correcta es 2.95
status: fixed
severity: high
component: diagnosis
found_in: 0.2.0.dev0
fixed_in: 0.2.0.dev0
reported: 2026-09-06
reporter: David / sesión UEM_HCPI_0219 — m09 con la Q y el JB aprobados
tags:
  - diagnosis
  - anomalos
  - calibracion
  - contradiccion
references:
  - src/art/mcp_server.py:1078-1082 (_conclusiones_desde — n_extreme entra en `fallos` sin mirar jb_pass)
  - src/art/mcp_server.py:1054-1057 (_reformulacion_desde — el mismo criterio, misma consecuencia)
  - src/art/diagnosis.py:774 y src/art/describe.py:1689 (el veredicto APROBADO ✓ / REVISAR ✗ sale de result.clean)
  - bugs/BUG-0036-... (dos veredictos de adecuación con el mismo nombre y ninguna regla)
  - bugs/BUG-0089-... (falencia sobre la regla de Treadway: mismo terreno, anómalos y adecuación)
  - bugs/BUG-0105-repro/repro.py
---

## Summary

El recuento de residuos extremos (`n_extreme`, |z|>3) entra en la lista de
FALLOS del bloque de conclusiones **sin calibrar por n y sin mirar si el
Jarque-Bera pasó**. El resultado es un informe que se contradice a sí mismo en
diez líneas:

    ## Diagnosis — UEM_HCPI
    - Veredicto: **APROBADO ✓**
    - Ruido blanco (Q): ✓  OK
    - Normalidad (JB): ✓  JB=4.413, p=0.1101
    - Residuos extremos (|z|>3): 1 — obs 12 (z=+3.08)
    ...
    ## 3 · CONCLUSIONES
    **El modelo NO se sostiene:** quedan 1 residuo(s) extremo(s).

Y a continuación ofrece como opción A intervenir esa observación.

Son dos defectos que se refuerzan.

**(1) El umbral no está calibrado por n.** Bajo especificación correcta,
|z|>3 no es un suceso raro con los tamaños muestrales habituales: es lo normal.

| n | esperados \|z\|>3 | P(al menos uno) |
|---|---|---|
| 100 | 0.27 | 0.237 |
| 215 | 0.58 | **0.441** |
| 400 | 1.08 | 0.661 |

Con n=215 —serie mensual de 18 años, el caso corriente— **la mediana del
máximo \|z\| simulado es 2.95** y el percentil 90 es 3.49. Es decir: el umbral
de 3 cae por debajo de la mediana del estadístico que evalúa, y marca a más de
la mitad de los modelos bien especificados.

**(2) Contradice al contraste que acaba de aprobar el modelo.** El Jarque-Bera
ES el contraste de las colas. Si no rechaza, ya ha dictaminado que las colas
son compatibles con la normal. Señalar entonces una observación de la cola como
prueba de inadecuación no añade información: la niega. Un anómalo es
diagnóstico **cuando el JB rechaza** —ahí dice DÓNDE está la no-normalidad, que
es justamente lo que el JB no dice—; con el JB aprobado, es la cola haciendo lo
que le toca.

## Impact

Alto. No es cosmético: cambia lo que el analista hace a continuación.

En la sesión UEM_HCPI_0219, m09 (Q aprobada en todos los retardos, JB p=0.110,
un solo residuo en z=+3.08) fue declarado «NO se sostiene» y el informe ofreció
como **opción A** intervenir 01/2003. Seguir esa indicación habría añadido una
intervención a un modelo adecuado — y encima una ya explorada y abandonada como
callejón en la misma sesión (v8), donde resultó significativa, pasó Treadway,
dio el mejor BIC y **empeoró la Q**.

El daño es sistemático y va en la dirección peor: con un falso positivo del 44 %
a n=215, casi la mitad de los modelos correctos reciben la instrucción de
intervenir. Y cada intervención encoge σ̂ y promueve al siguiente anómalo, que
es la escalada que el propio nodo de intervención advierte en
`guided_intervention` («cada intervención encoge σ̂ y promueve al siguiente
anómalo, así que la escalada no para sola»). La herramienta que avisa de la
espiral es la que la alimenta desde el otro extremo.

## Reproduction

    cd art-python && python3 bugs/BUG-0105-repro/repro.py

Salida:

    n=215 : esperados 0.58   P(al menos uno)=0.441
    n=215 : maximo |z| simulado -> mediana=2.95  p90=3.49  P(max>3.08)=0.360
    -> la MEDIANA del maximo (2.95) esta por debajo del umbral 3.0

    diagnosis: white_noise=True  normal=True  n_extreme=1
    conclusiones -> **El modelo NO se sostiene:** quedan 1 residuo(s) extremo(s).

La parte B llama directamente a `mcp_server._conclusiones_desde` con
`white_noise=True`, `normal=True`, `n_extreme=1`.

Caso real: `cases/UEM_HCPI_0219/work/UEM_HCPI_0219_m09_ffix.inp` (n=216, máx
|z| = 3.08).

## Root cause

`src/art/mcp_server.py:1078-1082`, en `_conclusiones_desde`:

    n_ext = int(d.get("n_extreme") or 0)
    if n_ext:
        fallos.append(f"quedan {n_ext} residuo(s) extremo(s)")

`n_extreme` se añade a `fallos` incondicionalmente: ni se compara con lo
esperado bajo H₀ para esa n, ni se condiciona a `d["normal"]`. El mismo patrón
está en `_reformulacion_desde` (1054-1057). El veredicto `APROBADO ✓` de la
cabecera, en cambio, sale de `result.clean` (`diagnosis.py:774`), que no lo
incluye — de ahí que los dos bloques discrepen. Es la misma familia que
BUG-0036: dos predicados de adecuación conviviendo sin una regla que los
ordene.

## Fix

1. **Quitar `n_extreme` de la lista de fallos de adecuación.** La adecuación la
   dictan la Q y el Jarque-Bera. Es lo que ya hace `result.clean`, así que el
   arreglo alinea las conclusiones con el veredicto en lugar de introducir un
   criterio nuevo.

2. **Reubicar el anómalo donde SÍ informa**: cuando el JB rechaza, listar los
   extremos como *dónde* está la no-normalidad. Ahí el dato es diagnóstico y
   dirige la reformulación; incluso ahí conviene recordar que una JB que falla
   sin anómalos apunta a λ y no a intervenciones (BUG-0043).

3. **Si se conserva alguna mención con el JB aprobado**, que sea informativa y
   calibrada, no un fallo: «1 residuo \|z\|>3; bajo especificación correcta se
   esperan 0.58 con n=215 (P(≥1)=0.44)». Y con umbral dependiente de n
   —p. ej. el cuantil del máximo, ≈3.5 para n=215 al 90 %— en vez de un 3 fijo.

4. Alinear `_reformulacion_desde` con el mismo criterio.

## Validation

`bugs/BUG-0105-repro/repro.py` sale con código 1 mientras
`_conclusiones_desde` devuelva «NO se sostiene» con `white_noise=True`,
`normal=True` y `n_extreme=1`, y vuelve a 0 cuando el veredicto de las
conclusiones coincida con `result.clean`. La parte A es aritmética de la normal
y sirve de test del enunciado calibrado.

---

## Cierre (2026-09-07)

La tabla del informe verificada por simulación (10.000 réplicas), y con un dato
que el informe no daba y que refuerza su tesis:

    n=100   mediana máx|z| = 2.70   P(≥1 con |z|>3) = 0.24
    n=215   mediana máx|z| = 2.95                     0.44
    n=300   mediana máx|z| = 3.05                     0.56
    n=500                                             0.74

**Con n=500, tres de cada cuatro** modelos correctamente especificados tendrían
un «residuo extremo». No es que el 3 esté mal calibrado: a partir de cierto n el
criterio se invierte y marca lo normal.

Aplicado lo que el informe propone, en sus cuatro puntos:

1. `n_extreme` **fuera** de la lista de fallos: la adecuación la deciden la Q y
   el Jarque-Bera, que es lo que ya dice `result.clean`.
2. Con el JB rechazando, los extremos se listan como **dónde** mirar la
   no-normalidad, con el recordatorio de BUG-0043 (un JB que falla sin anómalos
   apunta a λ, no a intervenciones).
3. Con el JB aprobado, la mención va **calibrada por n**: «1 residuo con |z|>3,
   que con n=215 es lo esperable — el umbral calibrado sería 3.49».
   `umbral_extremo(n)` es el cuantil 90 del máximo: P(máx|z| < c) = (2Φ(c)−1)ⁿ.
4. `_reformulacion_desde` alineado — ahora delega en `_conclusiones_desde`
   (BUG-0106), así que el criterio es uno solo por construcción.

**Y una quinta cosa que el informe no pedía y hacía falta:** las ALTERNATIVAS
ofrecían «intervenir» como opción A sobre ese mismo modelo aprobado. Ofrecer una
intervención sobre un anómalo esperable es invitar a sobre-intervenir, que es el
peligro que el analista lleva toda la sesión señalando. Ahora la opción sólo
aparece si el |z| supera el umbral calibrado **o** si algo más falla.

`describe_diagnosis` publica `nobs`, sin lo cual la calibración no era posible:
«1 residuo |z|>3» no se puede juzgar sin saber sobre cuántos.
