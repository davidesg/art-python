---
id: BUG-0020
title: art now picks lambda=0 for IPC_ES where on 2026-08-07 it picked lambda=1 — the first rung of the identification moved
status: open
severity: high
component: identification
found_in: working copy (posterior a art-tseries 0.1.11)
reported: 2026-08-15
reporter: la batería de extremo a extremo de drtran-python
tags:
  - identification
  - box-cox
  - regression
references:
  - bugs/BUG-0020-repro/repro.py
  - drtran-python/tests/test_end_to_end_passthrough.py (los 5 fallos)
  - drtran-python/docs/STUDY_efficiency_vs_c.md §7
---

## Resumen

`art` decide hoy **λ=0** (logaritmos) para la serie IPC_ES donde el 2026-08-07
decidía **λ=1** (nivel). La diferenciación no se ha movido (d=1, D=0) y los 11
deterministas siguen siendo 11. WTI queda intacta: λ=0, d=1, D=0, 3 deterministas.

```
lambda / d / D que art escribe para IPC_ES
  sola en el lote      : 0.00  1  0
  en lote con WTI      : 0.00  1  0
  fijado el 2026-08-07 : 1.00  1  0
```

## Por qué importa más de lo que parece

λ es el **primer escalón** del orden de identificación (λ → d → estacionalidad).
Con otra λ la serie es otra, así que todo lo de aguas abajo deja de ser comparable.
Se ve en la batería de `drtran-python`: **cinco pruebas fallan y son un solo
defecto con cuatro consecuencias** — la identificación fijada, las verosimilitudes
univariantes, la función de transferencia a la que aterriza `mtram`, la ganancia,
y la puerta diagonal. Ninguna de las cuatro últimas es un defecto propio.

## Reproducción

```bash
python3 bugs/BUG-0020-repro/repro.py
```

Necesita las series en nivel del proyecto de pass-through
(`passthrough_multiart/data/levels_2002_2019.csv`), que viven fuera del
repositorio; el guion avisa si faltan. Lee la decisión donde `art` la escribe: la
línea siguiente a `** Box-Cox lambda, regular differences and complete annual
differences:` del `.inp` que produce.

## Lo que ya está descartado

* **No lo causa el estudio de eficiencia de drtran.** Las cinco fallan igual
  contra el árbol limpio, sin ninguno de aquellos cambios.
* **No es contaminación de lote.** La hipótesis natural era que procesar IPC_ES
  junto a WTI moviera su identificación; el repro la comprueba y la descarta:
  sola y acompañada da lo mismo.
* **No es la diferenciación.** d=1, D=0 en los dos casos, como estaba fijado.

## Lo que falta: la causa

Tres candidatos, ninguno comprobado:

1. **El commit `f8ee98e`** de art, «cierra siete defectos del camino guiado y abre
   el dominio en la política» — el que más superficie mueve. Nota: la búsqueda por
   contenido (`git log -S"boxlam"`) **no** encuentra ningún commit posterior al
   6-ago que toque la decisión, así que si es éste, la mueve indirectamente.
2. **El cambio a instalaciones editables.** El 7-ago la batería corría contra
   `site-packages`; desde que el MCP se enlazó a las copias de trabajo, corre
   contra otro código. Si λ se decidía al filo, el pin estaría registrando eso.
3. **Un cambio de entorno por debajo** (statsmodels/numpy) en un contraste que
   decide al borde. El aviso de `describe.py:225` —el estadístico KPSS fuera del
   rango de la tabla— es un recordatorio de que aquí se opera cerca de los bordes.

## Siguiente paso

Bisecar entre `e257f6d` (art-tseries 0.1.10, anterior al pin) y HEAD ejecutando
sólo `test_regression_art_still_identifies_the_same_two_models` de
`drtran-python`: 32 s por punto.

**Antes de decidir el arreglo hay que medir el margen**: si λ se decide por un 1 %,
el hallazgo es que el pin es frágil y la serie está en la frontera, y entonces lo
que hay que corregir es el pin —o la regla— y no el código. Si el margen es amplio,
hay un defecto de verdad. **Cuál de las dos λ es la correcta para IPC_ES es una
decisión sobre los datos, no sobre el código.**
