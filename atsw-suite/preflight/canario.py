"""Plugin de pytest para las suites contra lo instalado (job «suites» de
preflight-atsw.yml): cada paquete de la suite tiene que venir del venv, no del
árbol de fuentes. Se comprueba al acabar la recolección y otra vez al final
(un test podría haber metido src/ en sys.path). Imprime una línea CANARIO[...]
que el workflow busca: «ok ...» o «FUERA DEL VENV {...}»."""
import os
import sys

MODS = ("fue", "pyfug", "drvarma", "drvec", "drtran", "sima", "art")
VENV = os.path.normcase(os.path.realpath(sys.prefix)) + os.sep


def _dentro(f):
    return bool(f) and os.path.normcase(os.path.realpath(f)).startswith(VENV)


def _check(when):
    bad = {m: sys.modules[m].__file__ for m in MODS
           if m in sys.modules and not _dentro(sys.modules[m].__file__)}
    print(f"\nCANARIO[{when}]: " + ("ok " + ",".join(m for m in MODS if m in sys.modules)
                                  if not bad else f"FUERA DEL VENV {bad}"))


def pytest_collection_finish(session):
    _check("collection")


def pytest_sessionfinish(session, exitstatus):
    _check("end")
