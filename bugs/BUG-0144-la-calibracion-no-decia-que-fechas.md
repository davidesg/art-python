---
id: BUG-0144
title: La calibración decía «retardo 4, +0,067» y no decía qué fechas — el `.out` lo lleva desde siempre y art no lo referenciaba
status: fixed
severity: medium
component: calibracion
found_in: 0.2.2
fixed_in: 0.2.2
reported: 2026-09-10
reporter: David
tags:
  - calibracion
  - homologacion
references:
  - BUG-0142
  - BUG-0143
  - BUG-0140
---

## Summary

Observación del analista mirando el panel de la ACF, después de arreglar el
reparto de dos canales:

> *«Pero no dice a qué retardo distorsiona. Mira las calibraciones en los .out
> y no sé si tiene sentido, o estamos discutiendo otra cosa.»*

Era otra cosa, y el diagnóstico correcto es más incómodo que el defecto:
**estábamos repartiendo por la unidad equivocada.**

`art` reparte la distorsión **por OBSERVACIÓN** —cuánto pone cada anómalo—, y
para que esa cuenta cierre hacen falta dos términos de corrección: el canal de
la varianza y un resto para los pares de anómalos (BUG-0143). `fue` reparte
**por PAR (t, t+k)**, que es la unidad natural del estimador de Bartlett:

    r(k) = Σₜ (xₜ−μ̂)(xₜ₊ₖ−μ̂) / (n·σ̂²)

Los sumandos SON los pares, y suman r(k) **sin residuo**. Ni canal de varianza
que separar, ni pares de anómalos que sobren, ni necesidad de declarar nada
anómalo primero. Y nombra las dos fechas.

Está en **cada `.out`** desde siempre, bajo «Calibration of distortions of the
ACF» —puerto de `PlotCalibACF` de `diagnose.c`, en `fue/report.py:918`—. `art`
no lo referenciaba en ningún sitio: cero apariciones de esa cadena en `src/`.
Llegaba al analista sólo si pedía el `.out` entero con `get_out_report`.

El `resto` que BUG-0143 «descubrió» en los retardos 4, 7 y 11 —las distancias
entre las obs. 64, 71 y 75— es exactamente lo que este bloque lleva listando por
retardo con fechas. Que la atribución por observación necesitara un término
residual era la señal de que la unidad no era la correcta.

## Lo que se ve al ponerlas al lado

Sobre ∇ln RATIO, retardo 4:

```
r(4) = +0.903
     Q1/2022 - Q1/2023   +0.053
     Q1/2023 - Q1/2024   +0.045
     Q1/2021 - Q1/2022   +0.042
  ── art hoy: barra roja +0.067   (r_cal = +0.836)
```

Los pares dominantes son **primeros trimestres a un año de distancia**: la
estacionalidad misma, no los anómalos. La barra roja dice «los anómalos ponen el
7% de este retardo», que es cierto y es otra pregunta.

## Decisión

Las dos, y por decisión del analista:

> *«Son útiles para calibrar distorsiones. La del `.out` es más específica.»*

| | pregunta | papel |
|---|---|---|
| `r_obs(k) − r_cal(k)` | ¿cuánto se movería si intervengo? | **decide** |
| pares dominantes | ¿qué fechas hacen este retardo? | **explica** |

Y para la PACF el reparto por pares **no existe**: Durbin-Levinson no es lineal,
así que ahí la diferencia contra la calibrada es la única vía. Por eso la barra
roja se queda en los dos paneles.

## Fix

- `calibracion._pares_dominantes(x, K, top)` — la descomposición exacta, con el
  **criterio de selección de `fue`**: los pares que HACEN el retardo (los más
  positivos si r(k)>0, los más negativos si r(k)<0), no los mayores en valor
  absoluto, y con la deduplicación `THRESH = 0.9999` de `PlotCalibACF`. Un par
  que compensa no explica el retardo, lo disimula.
- `Distorsion.pares` — por retardo, con `default` y al final del dataclass.
- `calibra_correlograma(..., top_pares=4, freq=, start=, desfase=)` — el
  calendario, el mismo triplete de BUG-0140, porque `residuals` llega como lista
  pelada y unos pares sin fecha no dicen nada. `CalibracionCorrelograma.fecha()`
  los resuelve, con el desfase `d + D·s` de BUG-0067.
- `describe_calibracion` — una sección nueva, «Qué fechas hacen cada retardo»,
  para los retardos que cambian de veredicto (o los de mayor |ACF| fuera de
  banda si no cambia ninguno), acotada a cuatro.
- Los **tres** sitios del servidor que llaman a `calibra_correlograma` pasan el
  calendario.
- `describe_prelim_scan` — la **ruta de pre-identificación** era el único sitio
  donde la figura de calibración de distorsiones salía sin tabla de pares: la
  serie aún no tiene modelo, así que no hay `describe_calibracion` que la
  acompañe. Y es donde más falta hace, porque es donde se eligen p y q. Va
  acotada a los retardos que esa misma sección ya marca como afectados.

### El guardián, que tiene lectura

La tabla **no se dibuja siempre**, y el criterio no es de gusto. Medido:

    residuos de RATIO_m10, donde un anómalo domina   el par mayor: 46 – 116%
    ∇ln RATIO, estacionalidad repartida              el par mayor:  5 –  10%

Dos regímenes que no se solapan. Si el par mayor se lleva el 5% de r(k), ese
retardo lo hacen treinta pares parecidos: es **estructura repartida por la
muestra**, y nombrarle dos fechas engaña. Sólo se listan los retardos donde el
par mayor se lleva al menos el **25%** — y ahí la tabla dice algo más fuerte que
«estas son las fechas»: dice que **ese retardo es un artefacto de esas fechas**.

Sobre los residuos de `RATIO_m10` el guardián deja pasar el retardo 6 —par mayor
46%— y descarta el 11, que se quedaba en el 16%. Y el 6 es justo el que hace
saltar la PACF de banda, o sea **el que cambia el orden AR**. Las fechas que lo
hacen: **Q4/2008 – Q2/2010**, el episodio de la crisis.

Y de paso quedan corregidos dos comentarios que habían quedado describiendo el
estimador anterior tras BUG-0142: el docstring de `calibra_correlograma` («los
extremos se sustituyen por la media…») y el de la red de Durbin-Levinson.

## Test

`tests/test_bug_0144_pares_de_fechas.py`. La prueba que importa es la
**homologación**: sobre `bugs/BUG-0126-repro/caso/RATIO_m10`, los pares que
calcula `art` se comparan con el bloque parseado del `.out` de ese mismo caso —
**15 de 15 retardos coinciden exacto**, mismos pares, mismas fechas, mismas
cifras a tres decimales.

No es cosmético: si `art` va a publicar este objeto tiene que ser EL objeto que
el analista ya lee en el `.out`, no una segunda versión parecida. Dos
calibraciones de pares que discrepasen en la tercera cifra serían exactamente la
enfermedad que BUG-0142 acaba de quitar del correlograma.

Más: que los pares sumen r(k) sin residuo (< 1e-12 sobre seis series), que el
criterio de selección sea el de signo y no el de |·| —con un caso construido que
tiene un par grande de cada signo en el mismo retardo—, el desfase en la fecha,
el caso sin calendario, y que la tabla llegue al analista.
