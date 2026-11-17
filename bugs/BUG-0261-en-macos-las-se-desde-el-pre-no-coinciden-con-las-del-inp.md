---
id: BUG-0261
title: En macOS, estimar el mismo modelo desde su .pre no da los errores típicos que da desde su .inp — una prueba roja «conocida» desde atsw 2.1.1
status: open
severity: low
component: tests
found_in: 0.2.4
fixed_in:
reported: 2026-11-17
reporter: David / Claude — preflights de atsw 2.1.1 y 2.1.3 con las suites
tags:
  - tests
  - platform
  - standard-errors
references:
  - tests/test_fue_bug_0015_metodo_de_las_se.py::test_estimar_acepta_el_pre_y_las_se_coinciden
  - preflight-atsw.yml, runs 43094293797 (atsw 2.1.1) y 44154374179 (atsw 2.1.3), «Suite art — macos-15» y «— macos-15-intel»
  - fue BUG-0015, art BUG-0090
  - bugs/BUG-0261-repro/repro.py
---

## Resumen

La prueba falla en macOS (arm64 e Intel) y en ningún otro sitio, en los dos
preflights con las suites, desde atsw 2.1.1. Usa el modelo de BUG-0090 —un
paseo aleatorio en torno a 100 con un escalón en 80, d = 1, AR(1), refactor
100—, estimado desde el `.inp` y desde su `.pre`. Pide cuatro cosas:

1. que los dos tengan sus errores típicos del hessiano por diferencias;
2. que el segundo sepa que viene de un `.pre`;
3. que los errores típicos coincidan con rtol 1e-3;
4. que no salte el aviso.

El registro de la CI no dice cuál falla.

En Linux pasa, pero por poco: el segundo error típico difiere en 7.8·10⁻⁴
relativos (36.0079 frente a 36.0360), con una tolerancia de 10⁻³. Lo probable
es que en macOS la diferencia pase de 10⁻³ (otra libm, otro punto de parada).

## Impacto

Bajo en lo numérico. Pero es una prueba roja que se da por conocida, y un
rojo «conocido» acaba tapando los rojos nuevos.

## Reproducción

`bugs/BUG-0261-repro/repro.py`: corre las cuatro comprobaciones por separado
y dice cuál falla. Sale 1 si alguna falla; 0 si todas se cumplen en macOS; 2 si
se cumplen en otra plataforma. Aquí (Linux x86_64) sale 2: hay que correrlo en
un Mac.

## Por estudiar

Correr el repro en un Mac para saber cuál de las cuatro falla. Si es la (3),
decidir si la tolerancia de fuera de Linux debe ser otra o si el `.pre` debe
reproducir el punto del `.inp` más de cerca.
