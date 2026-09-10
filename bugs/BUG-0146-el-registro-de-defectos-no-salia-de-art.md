---
id: BUG-0146
title: El registro de defectos no salía de art — la biblioteca aceptaba cualquier directorio, el CLI no, y el índice se firmaba como ART fuera donde fuera
status: fixed
severity: medium
component: bugs
found_in: 0.2.2
fixed_in: 0.2.2
reported: 2026-09-10
reporter: David
tags:
  - bugs
  - escalera
references:
  - pyfug BUG-0001
  - art BUG-0145 (el eje temporal, movido a pyfug al montarle registro)
---

## Summary

De los cinco programas de la escalera —`art`, `fue`, `pyfug`, `drvec`,
`drtran`/`drvarma`— sólo dos tenían registro de defectos en el repositorio.
`drvec` lleva el suyo a mano en `docs/BUGS.md`; **`pyfug` no tenía ninguno**, y
es el que dibuja la primera figura que ve el alumno.

Al ir a darle uno salieron dos defectos en el registro de `art`, los dos de la
misma familia:

**1 · La capacidad existía y le faltaba la puerta.** `art.bugs` acepta
`bugs_dir=` en **todas** sus funciones —`list_bugs`, `validate_all`,
`next_id`, `render_index`, `write_index`, `new_bug`—. El CLI no lo exponía en
ninguna: siempre llamaba a `find_bugs_dir()`. Así que llevar el registro a otro
repositorio exigía **copiar el módulo**, que es exactamente la enfermedad
—la misma capacidad en N sitios— contra la que está escrito el resto del plan.

**2 · Y `find_bugs_dir` es un cepo fuera de `art`.** Sube desde el directorio
actual y, si no encuentra nada, **se cae a la ubicación del paquete**:

```python
seeds = [Path(start).resolve() if start else Path.cwd()]
seeds.append(Path(__file__).resolve().parent)   # inside the installed pkg
```

Cómodo dentro de `art` —funciona desde cualquier subdirectorio— y silenciosamente
equivocado fuera: `art-bug index` desde un repositorio con `bugs/` aún vacío
escribe el índice **de `art`**, en el sitio de `art`, sin decir nada.

**3 · El índice se firmaba como ART.** `render_index` llevaba el nombre del
proyecto clavado en la cadena:

```python
"In-repo bug tracker for **ART** (art-tseries).  One Markdown file per bug…"
```

El primer índice generado para `pyfug` salió diciendo que era el de ART. Una
propiedad **del sitio**, escrita en el código que la usa: el mismo patrón que
el censo de figuras encontró diecinueve veces.

## Fix

- `art-bug --dir BUGS_DIR` en el analizador principal, aplicable a los cinco
  subcomandos (`list`, `show`, `new`, `index`, `check`). Seis líneas: la
  biblioteca ya estaba preparada.
- `bugs.project_name(bugs_dir)` — el nombre sale del sitio, en este orden:
  `bugs/PROJECT` si el repositorio quiere decirlo él, y si no el nombre del
  directorio que contiene `bugs/`. `render_index` lo usa.
- `bugs/PROJECT` en `art` («ART (art-tseries)») y en `pyfug`.

No se toca `find_bugs_dir`: su respaldo a la ubicación del paquete es correcto
**dentro** de `art`, y `--dir` es la forma de no depender de él fuera. El
docstring del CLI dice ahora por qué.

## Validation

`tests/test_bug_0145_el_registro_sale_de_art.py`: que `--dir` opere sobre un
registro ajeno sin tocar el de `art`, que el nombre del proyecto salga del
`PROJECT` y del directorio, y —la que habría cazado el cepo— que un `--dir`
apuntando a un directorio **vacío** falle en vez de indexar los defectos de
`art` en otro sitio.

El primer usuario es `pyfug`, cuyo BUG-0001 es el eje temporal que se levantó
desde `art` cuando no había dónde ponerlo.
