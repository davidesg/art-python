"""Dónde viven los datos de la réplica que algunos tests necesitan.

Varios tests de regresión fijan un comportamiento sobre un caso REAL —el que lo
destapó— además de sobre datos sintéticos. Ese caso vive fuera del repositorio,
en el árbol de trabajo de la réplica, y no se distribuye.

La ruta se lee de `ART_TEST_DATA`. Sin esa variable los tests que dependen de
ella hacen `skip`, que es lo correcto: no se puede comprobar lo que no está.

    export ART_TEST_DATA=/ruta/al/arbol

Se espera que esa raíz contenga `Tesis_Michael/replica/` y, para unos pocos,
`Tesis_Michael_DS/replica/`.

Antes esto era una ruta absoluta escrita en dieciséis ficheros. Además de no
funcionar en ninguna otra máquina, esos ficheros viajan en el sdist de PyPI, o
sea que se distribuían tests que nadie más podía ejecutar: parecían cobertura
sin serlo.
"""
import os

import pytest

RAIZ = os.environ.get("ART_TEST_DATA", "").strip()

REPLICA = os.path.join(RAIZ, "Tesis_Michael", "replica") + os.sep if RAIZ else ""
REPLICA_DS = (os.path.join(RAIZ, "Tesis_Michael_DS", "replica") + os.sep
              if RAIZ else "")

HAY_DATOS = bool(RAIZ) and os.path.isdir(REPLICA)

#: Decorador para el archivo o el test entero.
requiere_replica = pytest.mark.skipif(
    not HAY_DATOS,
    reason="datos de la réplica no disponibles (define ART_TEST_DATA)")


def ruta(*partes: str) -> str:
    """Une bajo `REPLICA`; devuelve "" si no hay datos, para que el skip actúe."""
    return os.path.join(REPLICA, *partes) if REPLICA else ""


def ruta_ds(*partes: str) -> str:
    return os.path.join(REPLICA_DS, *partes) if REPLICA_DS else ""
