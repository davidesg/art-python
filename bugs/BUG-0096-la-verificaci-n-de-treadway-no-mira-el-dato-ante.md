---
id: BUG-0096
title: La verificación de Treadway no mira el dato antes y después de cada intervención — un vecino activo (1–2σ) se da por bueno y se pierde la cola del suceso
status: fixed
severity: high
component: interventions
found_in: 0.1.12
fixed_in: 0.2.0
reported: 2026-09-05
reporter: David / sesión SERV_UEM — escalera 11/2015
tags:
  - treadway
  - vecino
  - intervencion
  - escalera
references:
  - src/art/interventions.py:704-793 (InterventionFitCheck: vecino_anomalo solo marca si |z| > umbral_vecino; no hay lectura del tramo activo 1–2σ)
  - src/art/interventions.py:813-875 (check_intervention_fit: calcula z_antes/z_despues pero el veredicto funciona() los ignora salvo que superen 2σ)
  - src/art/escalera.py:344-360 (la escalera solo sube de peldaño por deja_vecino, que usa vecino_anomalo)
  - src/art/configuracion.py:37-47 (la marcha del incidente distingue umbral_activo — la verificación de la intervención no lo usa)

---

## Summary

`check_intervention_fit` calcula el residuo tipificado del vecino ANTES y
DESPUÉS de cada intervención (`z_antes`, `z_despues`), pero el veredicto
`funciona` los ignora salvo que superen el umbral de anómalo (2σ). Un vecino
en el tramo ACTIVO —entre 1σ y 2σ— no se marca ni se reporta, y la
intervención se da por buena (`vecino_anomalo=None`, `funciona=True`). Ese
tramo es justo donde cae la COLA sub-umbral del suceso: la parte que la forma
no modeliza y que se queda pegada al lado. La regla de Treadway dice "mira un
dato antes y uno después"; la implementación solo mira si es anómalo.

## Impact

La escalera de Ockham no sube de peldaño cuando debe. Medido en SERV_UEM
11/2015: el escalón simple dejaba el vecino «después» (12/2015) en −1.40σ
—activo, no anómalo— y la verificación lo daba por `funciona=True` con
`vecino_anomalo=None`. El analista no ve ninguna señal de que la forma se
queda corta, y la masa no modelizada reaparece como anómalos nuevos en los
noviembres siguientes (11/2016, 11/2017). La evidencia que habría justificado
subir de peldaño (BUG-0093) se pierde en el punto ciego 1–2σ.

## Reproduction

`bugs/BUG-0096-repro/repro.py` — sintético y determinista, sin datos ni
motor. Construye un `InterventionFitCheck` con la firma del caso SERV_UEM
11/2015: vecino «después» a −1.40σ (activo, <2σ), residuo en la fecha
absorbido. Muestra que `vecino_anomalo` devuelve `None` y `funciona=True`,
aunque el dato después está a 1.4 desviaciones — exactamente la cola que la
regla existe para ver.

## Root cause

`vecino_anomalo` (interventions.py:731-735) compara `abs(z_antes)` y
`abs(z_despues)` SOLO contra `umbral_vecino` (2.0). No existe el umbral
"activo" (1.0) en el veredicto: ese umbral vive en `arranques_candidatos`
(configuracion.py) para delimitar el episodio ANTES de intervenir, pero la
verificación de la intervención YA construida no lo consume. El tramo
[1σ, 2σ) —un vecino que no es anómalo pero tampoco es ruido— se trata como
"ninguno". La regla de Treadway («mira un dato antes y uno después») exige
leer ese dato y decidir; hoy se lee y se descarta.

## Fix

Añadir al veredicto una lectura del vecino ACTIVO: si `abs(z_vecino)` está en
[umbral_activo, umbral_vecino), marcarlo como «cola activa» (no `funciona`
limpio), y reportarlo en `describe_escalera` como razón para subir de peldaño.
El contraste correcto ya existe —es el residuo tipificado del vecino, que con
la forma bien especificada debe ser ≈0—; lo que falta es aplicar el umbral
activo en la verificación y no solo en la delimitación.

## Validation

`bugs/BUG-0096-repro/repro.py` sale 1 con el vecino a −1.40σ (bug presente:
se da por bueno). Tras el fix, debe salir 0: un vecino a 1.4σ marca «cola
activa» y `funciona=False`. Sobre SERV_UEM 11/2015, el escalón simple debe
dejar de darse por bueno y la escalera debe ofrecer subir de peldaño.

---

## Fix (aplicado, 2026-09-05) — con TRES restricciones que no estaban en el reporte

Decisión del analista, y cambia el alcance:

> *«tenemos claro que el umbral debería bajar con estructura ARMA, pero prefiero
> mantener en dos sigma aun cuando el modelo tenga estructura arma. Sin embargo
> un warning con un vecino a 1.5 sigma no está por demás si ya hay estructura
> arma… el peligro de sobre intervenir es real y un residuo contiguo de 1.5
> tiene alta probabilidad de ser producto de un proceso gaussiano.»*

Así que:

1. **La regla de Treadway se queda en 2σ**, con ARMA y sin él. `funciona` y
   `vecino_anomalo` **no cambian**. El reporte pedía que dejaran de ser limpios;
   no se hace.
2. **Sólo una NOTA, y sólo con ARMA.** Sin ARMA el residuo crudo del vecino ES
   el contraste exacto —el regresor filtrado es una ficticia— y un vecino
   sub-umbral es exactamente lo que dice ser. Con ARMA pierde potencia (47%
   frente al 77.5% del LR, BUG-0089) y ahí puede ser la cola.
3. **NO entra en `razones_para_subir`.** El reporte lo pedía. Eso convertiría en
   evidencia algo que bajo la nula pasa el 13% de las veces, y la
   sobre-intervención es el modo de fallo que no se detiene solo.

**Y la banda empieza en 1.5, no en el `UMBRAL_ACTIVO` = 1.0 del episodio.** Son
dos preguntas distintas y el número lo decide la nula gaussiana:

    |z| > 1.0  →  p = 0.317   uno de cada 3     ← eso es ruido
    |z| > 1.5  →  p = 0.134   uno de cada 7.5
    |z| > 2.0  →  p = 0.046   uno de cada 22    ← la regla

A 1.0 la nota saldría en un tercio de las intervenciones y no diría nada.

**Consecuencia asumida, y conviene que conste:** el caso que motivó este reporte
—SERV_UEM 11/2015, vecino a **−1.40σ**— queda POR DEBAJO de la banda y **no
produce nota**. Es decisión, no descuido: a 1.40 la nula da uno de cada seis.

El aviso trae la probabilidad, para que no se lea como un hallazgo:

```
nota: vecino después a 1.62σ — no llega a anómalo (2σ, la regla de Treadway)
pero tampoco es plano. Con ARMA el residuo crudo pierde potencia, así que puede
ser la COLA del suceso. Es una nota, no evidencia: bajo la nula un |z|>1.5 pasa
el 13% de las veces.
```

## Validation — resultado

El repro se reescribió para comprobar **la decisión y no la petición**, con las
tres restricciones y la banda, y con el caso de −1.40σ registrado como quedando
fuera a propósito. Sale 0. Hay una prueba que fija que la nota **no** alimenta
`razones_para_subir`.
