---
id: BUG-0058
title: la cascada de abandono sobrescribía las razones ya escritas y barría ramas que habían dejado de descender del callejón
status: fixed
severity: high
component: guion
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-29
reporter: carril Claude del RUN 3 — defecto (1) de su informe
tags:
  - guion
  - data-loss
  - lineage
references:
  - src/art/guion.py (abandon)
  - bugs/BUG-0037-abandon-sweeps-the-node-that-condemns-the-branch.md
  - tests/test_bug_0058_cascada_de_abandono.py
  - bugs/BUG-0058-repro/repro.py
---

## Summary

Dos fallos en `abandon`, los dos observados sobre RATIO en el RUN 3.

### (a) Las razones se pisaban

```python
e.status = "dead-end"
e.why_abandoned = why.strip()      # para TODA versión alcanzada
```

Se ejecutaba para cada versión de la cascada, estuviera ya marcada o no. Abandonar
una versión **sobrescribía la razón de cualquier callejón anterior** que la
cascada volviera a tocar. El analista lo verificó en el JSON: cuatro versiones
con literalmente el mismo texto, y la suya perdida.

Es el fallo que más duele porque contradice la razón de ser de la función. Su
propia docstring:

> *«`why` no es opcional por diseño: un callejón sin razón anotada no evita que
> se vuelva a entrar en él, que es la única cosa para la que sirve marcarlo.»*

La función exige una razón en la entrada y la destruye por el costado.

Y copiar la razón del ancestro al descendiente era además **falso**: un
descendiente no cae por lo que dice el texto del ancestro, cae porque su ancestro
cayó. Son dos afirmaciones distintas.

### (b) Se barrían ramas que ya no descendían del callejón

BUG-0037 estableció que un **nodo** de decisión alcanzado por la cascada se
*recoloca* al tronco en vez de abandonarse — porque el argumento que suele venir
detrás de un modelo fallido es precisamente el que lo condena, y pertenece al
tronco que sobrevive.

Pero `alcanzadas` se calculaba **una vez, antes** de recolocar. Los descendientes
de ese nodo seguían en la lista y se abandonaban igual, aunque tras la
recolocación colgaran de una versión viva. El analista lo describió exactamente:
*«v15 tiene `parent=14` (un nodo, no v12), así que la cascada alcanzó una rama que
no desciende de la abandonada»*.

## Repro

```
Se abandona v2. El arbol era  v1 → v2 → {v5 (ya callejon), v3 NODO → v4}

  abandonadas: [2, 5]     recolocadas: [3]

  v1 [model] parent=None status=exploring
  v2 [model] parent=1    status=dead-end
        v2 no blanquea: Q p=0.001
  v3 [node ] parent=1    status=exploring
  v4 [model] parent=3    status=exploring
  v5 [model] parent=2    status=dead-end
        RAZON PROPIA DE v5: el MA(2) no se sostiene, t=1.2
        [Además: Arrastrado por el callejón de v2: v2 no blanquea: Q p=0.001]
```

## Fix

* **(a)** Una razón escrita no se pisa. La versión abandonada directamente lleva
  la suya; un descendiente recibe `«Arrastrado por el callejón de vN: …»`, y si ya
  tenía razón propia se conservan **las dos**.
* **(b)** Antes de marcar nada, se podan del conjunto los subárboles de los nodos
  que van a recolocarse: tras la recolocación cuelgan del tronco vivo y no hay
  nada que los condene.

Lo que sí sigue barriéndose es lo que de verdad desciende del fallo — el test lo
fija en las dos direcciones, porque una poda demasiado ancha sería el error
opuesto.
