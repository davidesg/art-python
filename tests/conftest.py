"""Configuración común de la suite.

Ahora mismo hace una sola cosa, y es higiene: **las figuras de las pruebas no
van al temporal compartido** (BUG-0082).

`_show_fig` escribe el fichero aunque no abra ventana —es lo que una prueba
necesita comprobar— pero lo escribía en `tempfile.gettempdir()` y con el mismo
patrón de nombre que la salida real. Cada corrida sembraba `/tmp` de PNG en
blanco `art_*.png`, indistinguibles del producto: el analista vio 49 ficheros de
651 bytes y concluyó que **art estaba renderizando en blanco**. No lo estaba —
las figuras de su sesión eran correctas, de 51 a 112 KB. La basura de las
pruebas era indistinguible del producto, y averiguarlo costó una sesión.
"""
import os

import pytest


@pytest.fixture(autouse=True)
def _figuras_fuera_del_temporal_comun(tmp_path, monkeypatch):
    """Cada prueba escribe sus figuras en SU `tmp_path`.

    `autouse` a propósito: la higiene no puede depender de que cada prueba nueva
    se acuerde de pedirla. pytest limpia `tmp_path` solo, así que no queda nada.
    """
    d = tmp_path / "figs"
    d.mkdir(exist_ok=True)
    monkeypatch.setenv("ART_FIG_DIR", str(d))
    # Y ninguna prueba abre ventanas en la pantalla de nadie.
    monkeypatch.setenv("ART_NO_VIEWER", "1")
