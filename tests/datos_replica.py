"""Dónde viven los datos de la réplica que algunos tests necesitan.

Varios tests de regresión fijan un comportamiento sobre un caso REAL —el que lo
destapó— además de sobre datos sintéticos. Ese caso vive fuera del repositorio,
en el árbol de trabajo de la réplica, y no se distribuye.

Las rutas se leen de `ART_REPLICA` (el árbol de la réplica) y, para unos pocos,
`ART_REPLICA_DS` (el de su segunda versión). Sin ellas los tests que dependen de
ellas hacen `skip`, que es lo correcto: no se puede comprobar lo que no está.

    export ART_REPLICA=/ruta/a/la/replica  ART_REPLICA_DS=/ruta/a/la/replica_ds

Antes esto era una ruta absoluta escrita en dieciséis ficheros. Además de no
funcionar en ninguna otra máquina, esos ficheros viajan en el sdist de PyPI, o
sea que se distribuían tests que nadie más podía ejecutar: parecían cobertura
sin serlo.
"""
import os

import pytest

def _dir(var):
    p = os.environ.get(var, "").strip()
    return os.path.join(p, "") if p else ""


REPLICA = _dir("ART_REPLICA")
REPLICA_DS = _dir("ART_REPLICA_DS")

HAY_DATOS = bool(REPLICA) and os.path.isdir(REPLICA)

#: Decorador para el archivo o el test entero.
requiere_replica = pytest.mark.skipif(
    not HAY_DATOS,
    reason="datos de la réplica no disponibles (define ART_REPLICA)")


def ruta(*partes: str) -> str:
    """Une bajo `REPLICA`; devuelve "" si no hay datos, para que el skip actúe."""
    return os.path.join(REPLICA, *partes) if REPLICA else ""


def ruta_ds(*partes: str) -> str:
    return os.path.join(REPLICA_DS, *partes) if REPLICA_DS else ""
