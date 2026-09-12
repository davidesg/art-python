---
id: BUG-0177
title: El guion guarda ℓ, AIC y BIC y no sobre qué muestra — desde `extend_sample` dos entradas del mismo árbol pueden estar en muestras distintas, y el mapa las dibuja como una mejora
status: fixed
severity: high
component: guion
found_in: 0.2.1
fixed_in: 0.2.1
reported: 2026-09-12
reporter: David — run 4 de IPC_ES, muestra extendida
tags:
  - guion
  - comparabilidad
  - muestra
references:
  - BUG-0085
  - BUG-0173
  - BUG-0176
---

## Summary

`GuionStats` guardaba `loglik, aic, bic, sigma_a, q_pass, jb_pass, n_extreme,
extreme, q_lags, q_pvalues, jb_pvalue, npar, refactor` — y **no la n**.

ℓ, AIC y BIC son sumas sobre las observaciones. Entre muestras distintas no miden
lo mismo y su diferencia no es una mejora de ajuste. El mapa las pone una debajo
de otra, en la misma columna, que es una invitación a leerlas en vertical.

Hasta ahora eso era casi imposible de provocar: todas las entradas de un guion
salían de la misma serie. **`extend_sample` (BUG-0173) lo convirtió en normal.**
Un defecto que entrega una capacidad nueva y deja sin guardia a la que había.

## Reproduction

Run 4 de IPC_ES. Comprobado en los `.inp`:

    IPC_ES_m03z.inp  →  216 1 2002 IPC_ES
    IPC_ES_m07.inp   →  263 1 2002 IPC_ES
    IPC_ES_m12.inp   →  263 1 2002 IPC_ES

Y el mapa dibujó, como padre→hijo:

    v19 m12          logL=-41.90    (n=263)
       └─ v20 FINAL  logL= -3.45    (n=216)

Leído de arriba abajo, el último paso parece un salto de ajuste. Es otra muestra.
El analista SÍ registró el cambio —nodo `n12: muestra = muestra extendida +47
obs → n=263`— pero el nodo vive en otra rama y no alcanza a la comparación.

Sintético, en la suite: dos entradas con `nobs` 216 y 263 unidas por `parent`.

## Impact

Las tres cifras con las que se elige un modelo, presentadas como comparables
cuando no lo son, sin una palabra. *Publica un número incorrecto y calla*: el
analista lo confirma como ENTRA.

Y el precedente está en el campo de al lado. `refactor` se guarda **por este
mismo argumento** —ℓ/AIC difieren en n·ln(factor) y no son comparables,
BUG-0085—. La n es la otra mitad de la misma condición y faltaba.

## Root cause

`src/art/guion.py`: `GuionStats` no tenía el campo, y `_extract_stats` ya
calculaba `n_orig = len(model.series.data)` para otra cosa —el desplazamiento de
los residuos— y lo tiraba.

## Fix

1. `GuionStats.nobs`, rellenado con `n_orig` en `_extract_stats`.
2. `comparaciones_entre_muestras(guion)` — los enlaces padre→hijo con `nobs`
   distinto. **Sólo el enlace padre→hijo**, no todos los pares: es el único
   sitio donde el mapa invita a comparar.
3. `guion_map` pone la n en la línea de cada modelo, junto a su ℓ —si el ajuste
   se lee en columna, su denominador tiene que estar en la misma línea— y añade
   el bloque que dice dónde deja de valer esa lectura.

`nobs` vacío no se denuncia: **no consta no es lo mismo que difiere**, y los
guiones anteriores al campo no se acusan de algo que no se sabe. El del run 4 se
queda mudo, que es lo correcto; lo que el arreglo evita es el próximo.

## Validation

`tests/test_bugs_0176_0177_el_arbol_y_la_muestra.py`:

- un guion real: las tres entradas registran `nobs=120`;
- 216 → 263 unidos por `parent` se detecta; la misma n no se denuncia; sin n
  registrada tampoco;
- el mapa avisa con las dos n a la vista y dice por qué —«la diferencia no es
  ajuste, es tamaño»—;
- la n aparece junto al ℓ en la línea del modelo.
