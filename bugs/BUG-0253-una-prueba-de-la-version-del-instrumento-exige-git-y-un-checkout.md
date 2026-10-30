---
id: BUG-0253
title: test_avisa_si_el_arbol_tiene_cambios_sin_commitear exige git y un checkout; con art instalado y sin git, falla en vez de saltarse
status: open
severity: low
component: tests
found_in: 0.2.3
fixed_in:
reported: 2026-10-30
reporter: David / Claude — prueba de instalación limpia de atsw 2.1.0 en diez distribuciones
tags:
  - tests
  - instalacion-limpia
references:
  - tests/test_guion_instrumento.py::test_avisa_si_el_arbol_tiene_cambios_sin_commitear
  - docs/PUBLISHING.md §5 (las suites contra lo instalado)
---

## Summary

La prueba ejecuta `git status` en el directorio que está tres niveles por
encima de `art/__init__.py`, dando por hecho que art es un checkout y que git
está instalado. Con art instalado desde una rueda ese directorio es el `lib/`
del entorno, y en una máquina sin git la prueba no se salta: muere con
`FileNotFoundError: 'git'`. En la prueba de instalación limpia de atsw 2.1.0
(2026-10-30, diez distribuciones en podman, art 0.2.3 de PyPI, imágenes sin
git) falló en las diez.

## Impact

Bajo: es la prueba. Pero PUBLISHING.md §5 pide pasar las suites contra lo
instalado, y ahí esta prueba queda siempre roja.

## Reproduction

`bugs/BUG-0253-repro/repro.py` corre la prueba con un PATH que tiene python y
no git. Sale con 1 mientras falle.

    python3 bugs/BUG-0253-repro/repro.py

## Root cause

La prueba supone el entorno de desarrollo: un checkout y git en el PATH.

## Fix

Propuesto: saltarla cuando git no está (`shutil.which("git")`) o cuando la raíz
no es un checkout (`git rev-parse` falla). Lo que comprueba —el «+sucio» del
SHA— sólo tiene sentido en un checkout.

## Validation

El repro, y la suite de art contra una instalación limpia sin git.
