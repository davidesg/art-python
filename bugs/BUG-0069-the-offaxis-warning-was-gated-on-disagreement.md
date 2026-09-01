---
id: BUG-0069
title: el aviso de «testigo fuera del eje f=0» vivía dentro de la rama de discrepancia, y estar fuera del eje no depende de que los dos lados discrepen — coincidir midiendo otra frecuencia es peor
status: fixed
severity: medium
component: describe
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-09-01
reporter: David / réplica TFM Bolivia — destapado al corregir BUG-0065
tags:
  - formal-tests
  - presentation
references:
  - src/art/describe.py (par confirmatorio en f=0)
  - bugs/BUG-0022-an-over-differencing-witness-that-drifts-negativ.md
  - bugs/BUG-0065-the-shin-fuller-null-was-not-shin-fullers.md
  - tests/test_bug_0022_offaxis_witness.py
---

## Summary

BUG-0022 estableció que un testigo de sobrediferenciación con θ̂ < 0 **mide la
frecuencia de Nyquist, no f=0**, y añadió el aviso correspondiente. Pero lo puso
**dentro de la rama de discrepancia** del par confirmatorio:

```python
if sf_says_enough != (not od_says_more):     # ← sólo si DISCREPAN
    if od_res.coef_free < 0.0:
        ...  "El testigo se salió del eje f=0"
```

Estar fuera del eje no depende de que los dos lados discrepen. Un testigo en
θ̂ = −0.57 mide Nyquist tanto si coinciden como si no — **y coincidir es peor**:
es un acuerdo que no significa lo que parece, porque uno de los dos está midiendo
otra frecuencia.

## Cómo se vio

Al corregir Shin-Fuller (BUG-0065). Sobre el caso sintético I(1) de BUG-0022, con
el lado AR diciendo ya lo correcto, los dos lados pasaron a **coincidir**, el
testigo siguió en θ̂ = −0.5702 y el aviso **desapareció**.

Es decir: arreglar un contraste apagó la advertencia de otro. El aviso estaba
enganchado a una condición que no era la suya.

## Fix

* El aviso se emite **siempre que θ̂ < 0**, dentro o fuera de la discrepancia, con
  la distancia con signo a la frontera θ=+1.
* Y cuando coinciden con el testigo fuera del eje, la conclusión deja de decir
  «✓ Los dos coinciden: el orden de integración no está en la banda ambigua» y
  pasa a decir que **coincidir no es confirmación**, porque queda el lado AR
  solo. Afirmar lo contrario contradecía el aviso impreso tres líneas antes —
  el noveno caso de esa misma familia en esta sesión.

## Nota sobre el test que lo defendía

`test_la_configuracion_es_la_que_dispara_el_bloque` exigía
`shin_fuller(m).stationary is True` sobre una serie **I(1) por construcción**. Ese
«estacionario» era el veredicto equivocado que corrigió BUG-0065, así que el test
estaba **defendiendo un error ajeno** como parte de su premisa.

Reescrito para fijar sólo lo suyo: que el testigo esté fuera del eje. Un test que
ata su premisa a un defecto de otro módulo impide arreglarlo.

## Nota de numeración

Este informe se escribió como BUG-0066 y se renumeró a BUG-0069: el número estaba ya tomado por un hallazgo del benchmark guiado de SF_MEG, escrito unas horas antes en este mismo repositorio. **Dos sesiones distintas comparten el contador de `bugs/` y no se ven entre sí**, así que la colisión no fue un descuido sino la consecuencia de no tener reserva de número. Ver la nota en `bugs/README.md`.
