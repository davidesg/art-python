---
id: BUG-0107
title: export_guion revienta con AttributeError en cuanto el guion tiene un NODO de decisión: recorre todas las entradas y desreferencia stats.aic, que en un nodo es None
status: fixed
severity: high
component: guion
found_in: 0.2.0.dev0
fixed_in: 0.2.0.dev0
reported: 2026-09-06
reporter: David / sesión UEM_HCPI_0219 — export del guion con 4 nodos de decisión
tags:
  - guion
  - export
  - guion_node
references:
  - src/art/guion.py:1190-1192 (export_guion_html: `s = e.stats` y acto seguido `s.aic`)
  - src/art/mcp_server.py (guion_node — escribe entradas kind="node" sin stats)
  - src/art/guion.py (guion_map sí distingue el tipo de entrada: es el exportador el que no)
  - bugs/BUG-0107-repro/repro.py
---

## Summary

`export_guion_html` construye la tabla resumen recorriendo **todas** las
entradas del guion y desreferenciando `e.stats.aic` sin mirar de qué tipo son.
Una entrada `kind="node"` —las que escribe `guion_node`— no tiene `stats`: vale
`None`. El export muere con

    AttributeError: 'NoneType' object has no attribute 'aic'

y no produce fichero alguno. Basta **un** nodo de decisión en el guion para que
el informe navegable sea inalcanzable.

## Impact

Alto, y con una ironía que conviene nombrar. El docstring de `guion_node` dice
que existe porque «un guion que registra sólo MODELOS empieza la historia
tarde»: λ, d, la ruta estacional y los órdenes se deciden antes de que exista
el primer modelo, y sin nodos nada de eso deja rastro. El exportador **no puede
renderizar exactamente los guiones que la suite anima a construir**. Cuanto
mejor documentado está un análisis, más seguro es que su informe no se genera.

Y el fallo llega en el peor momento: al final, cuando el análisis está cerrado
y lo que se quiere es el entregable. En la sesión UEM_HCPI_0219 el guion tenía
22 entradas, 18 modelos y **4 nodos** (n4, n12, n20, n22) que documentan la
corrección de un error de especificación, dos barridos MEG y el experimento que
cerró el caso. Ninguno de los 18 modelos se pudo exportar por culpa de los 4
nodos.

`guion_map` sí distingue el tipo de entrada y dibuja los nodos sin problema, de
modo que el exportador es el único componente que ignora que existen.

## Reproduction

    cd art-python && python3 bugs/BUG-0107-repro/repro.py

    == guion cargado: 2 entradas (1 model + 1 node)
       stats del nodo: None
       export_guion_html: AttributeError -> 'NoneType' object has no attribute 'aic'

Guion mínimo: una entrada `kind="model"` con stats y una `kind="node"` sin
ellos. También se reproduce con cualquier guion real que haya pasado por
`guion_node`, p. ej.
`cases/UEM_HCPI_0219/work/UEM_HCPI_0219_guion.json`.

## Root cause

`src/art/guion.py:1190-1192`:

    for e in guion.entries:
        s = e.stats
        aic_str = f"{s.aic:.1f}" if s.aic is not None else "—"

La guarda comprueba `s.aic is not None` pero no `s is not None`: protege contra
un modelo sin AIC y no contra una entrada sin stats. El bucle no filtra por
`e.kind`, y el resto de la fila (`s.loglik`, `s.sigma_a`, …) tiene el mismo
problema.

## Fix

Distinguir el tipo de entrada, como ya hace `guion_map`:

- las entradas `kind="node"` van a la tabla como **fila de decisión** —versión,
  nodo, lo decidido y por quién— con las columnas de ajuste en «—», o en una
  sección propia intercalada en el orden en que ocurrieron, que es lo que las
  hace informativas (un nodo posterior a un modelo es una reformulación, y eso
  sólo se ve si van entrelazados);
- y una guarda `s is None` antes de tocar cualquier campo de stats, para que
  una entrada incompleta no vuelva a tumbar el informe entero.

Conviene además que el export no sea una operación todo-o-nada: una entrada que
no se puede renderizar debería salir degradada y con aviso, no impedir las
otras veintiuna.

## Validation

`bugs/BUG-0107-repro/repro.py` sale con código 1 mientras `export_guion_html`
lance AttributeError sobre un guion con un nodo, y vuelve a 0 cuando devuelva
HTML. Añadir a la suite un guion de prueba que mezcle modelos y nodos, que es
la forma normal de un guion bien llevado.

---

## Cierre (2026-09-07)

Reproducido: `AttributeError: 'NoneType' object has no attribute 'aic'` con un
solo nodo en el guion. Eran **tres** desreferencias, no una: la tabla resumen, la
cabecera del detalle y la tabla de ajuste de cada entrada.

El nodo **no se omite**: se dibuja como lo que es —una decisión, con su
evidencia, sus alternativas descartadas y quién la tomó— y sin columnas de
ajuste. Omitirlo sería peor: el recorrido cuenta la historia y los nodos son la
mitad que explica POR QUÉ, que es justo lo que BUG-0101 arregló en el mapa.

Misma familia que BUG-0102: una cifra que no consta, desreferenciada sin mirar.
