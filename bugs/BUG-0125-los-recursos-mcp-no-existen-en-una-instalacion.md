---
id: BUG-0125
title: Los recursos MCP no existen en una instalación — la rueda no empaqueta bugs/ ni docs/, así que el arreglo del BUG-0116 sólo funciona en el árbol de desarrollo
status: fixed
severity: high
component: packaging
found_in: 0.2.0
fixed_in: 0.2.1
reported: 2026-09-09
reporter: revisión de arquitectura
tags:
  - empaquetado
  - recursos
  - mcp
references:
  - BUG-0116
---

## Summary

Los cinco `@mcp.resource` de `recursos.py` sirven los 125 informes de defecto y
la documentación bajo demanda. Es la respuesta al BUG-0116: lo que no cabe en las
descripciones —que se empujan en cada llamada y el cliente trunca— se pide por
`art://defectos`, `art://defecto/{id}`, `art://docs`, `art://doc/{nombre}`.

**No funcionan en ninguna instalación.** `recursos.py` localiza el material tres
directorios por encima del módulo:

```python
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

que en el árbol de trabajo es la raíz del repositorio, y en una instalación es un
directorio cualquiera dentro del entorno. Y sobre todo: **el material no está
ahí**, porque `pyproject.toml` empaqueta sólo el código:

```toml
[tool.setuptools.packages.find]
where = ["src"]
```

sin `package-data`, sin `include-package-data`, sin `MANIFEST.in`.

## Impact

**Alto, y silencioso.** Comprobado sobre el artefacto publicado, no sobre la
configuración:

```
$ pip download art-tseries==0.2.0 --no-deps
art_tseries-0.2.0-py3-none-any.whl
  ficheros en la rueda : 27      (art/*.py y los metadatos)
  ficheros de bugs/    : 0
  ficheros de docs/    : 0
```

Consecuencias:

* **El arreglo del BUG-0116 sólo existe en la máquina donde se escribió.** Quien
  instala `atsw` desde PyPI —la sesión de Windows del 8-sep, por ejemplo—
  obtiene «no hay registro en esta instalación» en los cuatro recursos de
  contenido.
* Es la peor forma de fallar: **el servidor anuncia los recursos en
  `resources/list`**, así que existen, se pueden pedir, y contestan que no hay
  nada. No hay error, hay ausencia.
* Y afecta justo a la parte del programa cuyo argumento es *aplicar a `art` lo
  que `art` aplica al análisis*: el registro de defectos como material de
  consulta en caliente.

Nadie lo detectó en la sesión de Windows porque **nadie llamó a un recurso**: su
uso medido es cero, que era precisamente el problema que el 0116 venía a
resolver.

## Reproduction

```sh
pip download art-tseries==0.2.0 --no-deps -d /tmp/w
python3 -c "import zipfile,glob; n=zipfile.ZipFile(glob.glob('/tmp/w/*.whl')[0]).namelist(); \
print(len(n), sum('bugs/' in x for x in n), sum('docs/' in x for x in n))"
# -> 27 0 0
```

O, en un entorno limpio con el paquete instalado, pedir `art://defectos`.

## Root cause

Dos decisiones que por separado son razonables y juntas dejan el hueco:

1. `recursos.py` supone la **disposición del repositorio** (`<raíz>/bugs`,
   `<raíz>/docs`) en vez de una disposición del **paquete**.
2. `pyproject.toml` empaqueta sólo `src/`, que es lo correcto para código y lo
   equivocado para material que el programa sirve en ejecución.

Ninguna prueba lo cubre porque **ninguna prueba cruza una instalación**: la suite
corre siempre sobre el árbol, donde `_RAIZ` acierta por accidente.

## Fix

**Aplicado el 9-sep-2026.**

1. Mover el material servido **dentro del paquete** —`src/art/material/bugs/`,
   `src/art/material/docs/`—, poblado en el `build` desde `bugs/` y `docs/`, y
   localizarlo con `importlib.resources.files("art")` en vez de contar
   directorios. `importlib.resources` es la respuesta correcta a esta pregunta y
   funciona igual en árbol, en rueda y en zip.
2. Declarar el material en `pyproject.toml` (`[tool.setuptools.package-data]`).
3. Si se prefiere no engordar la rueda con 125 informes: que los recursos digan
   **por qué** no hay registro —«esta instalación no incluye el material; está en
   github.com/…»— en vez de un mensaje que se lee como «no hay defectos».

## Validation

Comprobado sobre el ARTEFACTO, que es como se estableció el defecto:

```
ANTES (rueda 0.2.0 publicada):   27 ficheros,  bugs 0,   docs 0
AHORA (rueda construida):       173 ficheros,  bugs 126, docs 19
```

Y sobre una **instalación limpia**, cargando el módulo desde `site-packages`:

```
raiz del material    : <venv>/lib/python3.12/site-packages/art/material
indice de defectos   : 24.052 caracteres
  ¿ve el BUG-0125?   : True
```

`tests/test_recursos_en_una_instalacion.py`, cinco pruebas: que la copia está
sincronizada (falla si `bugs/` cambia y nadie corre el guion), que el paquete
manda sobre el árbol, que el índice tiene contenido, que sin material se dice
**por qué** —«no hay defectos» y «esta instalación no los trae» son cosas
distintas, y decir la primera cuando pasa la segunda borra la razón (BUG-0090)—
y una marcada `slow` que **construye la rueda y mira dentro**.

Y en `.github/workflows/publish-art.yml`, dos pasos: sincronizar antes de
construir, y **fallar la publicación** si la rueda no lleva el material. Es la
misma lección que el propio fichero ya llevaba escrita sobre la 0.1.3: lo que no
se comprueba sobre el artefacto se publica roto.

**Lo que este defecto deja dicho, y vale más que el arreglo:** ninguna prueba de
las 1.612 cruzaba una instalación. Es el punto 0.1 de la revisión de
arquitectura, y éste es el segundo defecto que sólo existe al otro lado de esa
frontera — los cuatro de la sesión de Windows fueron los primeros.
