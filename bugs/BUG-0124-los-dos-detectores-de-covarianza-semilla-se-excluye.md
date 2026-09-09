---
id: BUG-0124
title: Los dos detectores de covarianza-semilla se excluyen mutuamente — con degeneración PARCIAL el aviso cuenta sólo las coincidencias exactas y calla las que están a 0,02 % de la semilla
status: open
severity: high
component: diagnosis
found_in: 0.2.1
fixed_in:
reported: 2026-09-09
reporter: David
tags:
  - covarianza
  - errores-tipicos
  - bfgs
references:
  - BUG-0027
  - BUG-0041
---

## Summary

`_equation_for_prompt` avisa de los errores típicos que son la semilla del BFGS
y no el hessiano. Tiene **dos** detectores y los usa en `if`/`else`:

```python
if covariance_is_degenerate(r):
    idx = degenerate_variance_indices(r)      # coincidencia EXACTA (tol 1e-5)
    aviso = f"{len(idx)} de los {npar} …"
else:
    …near_seed_variance_indices(r)…           # BUG-0041: CERCA de la semilla
```

En cuanto **una sola** varianza coincide exactamente con la semilla, se toma la
rama del `if` y el detector de proximidad **no llega a ejecutarse nunca**. El
aviso cuenta las exactas y calla las que están a una diezmilésima.

Y es justo el caso que el docstring de `degenerate_variance_indices` describe
como «el caso peligroso»:

> *«La degeneración puede ser PARCIAL, y ése es el caso peligroso. Con niter = 0
> no se actualiza nada y toda la covarianza es la semilla; pero con niter = 1 el
> BFGS actualiza UNA dirección y deja el resto intacto […] Unos errores típicos
> válidos y otros no, sin nada que los distinga en la salida.»*

El concepto está escrito. Lo que falla es que «seguir siendo la semilla» no es
bit-exacto: el BFGS toca todas las direcciones un poco, y a las que no aprendió
nada las deja a una parte en diez mil, no en el mismo bit.

## Impact

**Alto, y en la dirección mala: INFRA-avisa.** El analista lee «1 de los 6 no
son válidos» y da por buenos los otros cinco. Los errores típicos de la semilla
son pequeños y creíbles, y los t que salen de ellos son enormes y falsos — que
es literalmente el daño que el BUG-0027 vino a evitar.

Medido sobre `RATIO_m50` (réplica de Bolivia, `run5_guiado`, 9-sep), modelo
híbrido del MEG, `niter=1`, `npar=6`, semilla var = 0,02469136:

| i | var | se | \|dif\|/semilla | ¿exacta? |
|---|---|---|---|---|
| 0 | 0,02469424 | 0,157144 | 1,17e−04 | no |
| 1 | 0,02469155 | 0,157135 | 7,58e−06 | **sí** |
| 2 | 0,02469575 | 0,157149 | 1,78e−04 | no |
| 3 | 0,02469722 | 0,157153 | 2,37e−04 | no |
| 4 | 0,02265081 | 0,150502 | 8,26e−02 | no |
| 5 | 0,00391465 | 0,062567 | 8,41e−01 | no |

    degenerate_variance_indices  -> [1]
    near_seed_variance_indices   -> [0, 2, 3, 4]
    covariance_is_degenerate     -> True

Cuatro varianzas están a menos del 0,03 % de la semilla y el aviso reporta una.
Los únicos dos errores típicos con información del hessiano son el 4 y el 5
—el AR estacional y el testigo MA_f—, o sea que **los cuatro deterministas del
modelo se presentaron con error típico inventado y sólo uno llevaba la marca ✗**.

Agravante de presentación: la ecuación marcaba con ✗ tres coeficientes y el
texto decía «1 de los 6». Las dos cifras salen de sitios distintos y ninguna era
correcta.

## Reproduction

*(pendiente de escribir como repro sintético)* Fabricar un `result` con
`niter=1`, `npar=6` y una diagonal de covarianza con una varianza igual a la
semilla y tres a `semilla·(1+2e-4)`. Antes del arreglo el aviso dice «1 de los
6»; debe decir 4.

## Root cause

`mcp_server.py:975-995`. Los dos detectores contestan preguntas distintas —«¿es
exactamente la semilla?» y «¿está sospechosamente cerca?»— y están cableados
como si fueran la misma pregunta con dos respuestas excluyentes. El `else` los
convierte en alternativas cuando son **complementarios**.

## Fix

*(propuesto, no aplicado)*

1. Unir los dos conjuntos: `set(degenerate) | set(near_seed)`, y contar sobre la
   unión. El `if`/`else` desaparece; lo que cambia según el caso es el texto del
   aviso, no qué índices se buscan.
2. Que la marca ✗ de la ecuación y el recuento del texto salgan de **la misma
   lista**. Hoy salen de sitios distintos y discrepan.
3. Revisar el umbral exacto de 1e-5: con `niter` bajo, «no aprendió nada» no
   produce igualdad bit a bit.

## Validation

*(pendiente)* Repro sintético con degeneración parcial; y una prueba que exija
que el número del texto coincida con el número de ✗ de la ecuación, que es la
discrepancia observada.
