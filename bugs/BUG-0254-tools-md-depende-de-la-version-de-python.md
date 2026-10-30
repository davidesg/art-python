---
id: BUG-0254
title: docs/TOOLS.md depende de la versión de Python — desde 3.13 el compilador quita la sangría de los docstrings y gen_tools_md la copia tal cual
status: open
severity: low
component: docs
found_in: 0.2.3
fixed_in:
reported: 2026-10-30
reporter: David / Claude — prueba de instalación limpia de atsw 2.1.0 en diez distribuciones
tags:
  - docs
  - python-3.13
references:
  - tools/gen_tools_md.py render (t.description sin normalizar)
  - tests/test_recuentos_que_no_envejecen.py::test_TOOLS_md_esta_regenerado
---

## Summary

`tools/gen_tools_md.py` escribe la descripción de cada herramienta tal como la
da el intérprete, y desde Python 3.13 el compilador quita la sangría común de
todos los docstrings. El mismo código da un `docs/TOOLS.md` distinto en 3.12 y
en 3.13+, así que `test_TOOLS_md_esta_regenerado` falla en todo intérprete
3.13+ contra el fichero generado en 3.12. En la prueba de instalación limpia de
atsw 2.1.0 (2026-10-30) falló en Debian 13, Fedora 41 y Arch: `-     candidate
seasonal AR_f factors.` contra `+ candidate seasonal AR_f factors.`.

## Impact

Bajo. La página dice lo mismo en los dos casos. Pero quien regenere TOOLS.md
en 3.13 reescribe todas sus líneas de continuación, y la prueba queda roja en
la mitad de los intérpretes que art admite.

## Reproduction

`bugs/BUG-0254-repro/repro.py` genera la página de una herramienta falsa con el
docstring como lo deja 3.12 y como lo deja 3.13. Sale con 1 mientras difieran.

    python3 bugs/BUG-0254-repro/repro.py

## Root cause

El generador no normaliza la descripción; depende de lo que haga el
compilador.

## Fix

Propuesto: `inspect.cleandoc(t.description)` en el generador (la forma de 3.13,
en todos los intérpretes), y regenerar `docs/TOOLS.md` una vez.

## Validation

El repro, y `test_TOOLS_md_esta_regenerado` en 3.12 y en 3.13.
