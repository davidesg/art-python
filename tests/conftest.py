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


# ── fue anterior a 0.1.17 (fue/BUG-0015) ──────────────────────────────────────
#
# Muchas pruebas fijan las defensas de art contra la covarianza del BFGS del
# CAMINO: la semilla 2/n al reestimar un `.pre`, el rechazo de `estimar()`, los
# avisos. Con fue ≥ 0.1.17 esas defensas no se disparan —las SE salen del
# hessiano en el óptimo—, pero art sigue aceptando fue 0.1.16 y ahí tienen que
# seguir funcionando. Estas fixtures emulan EXACTAMENTE ese fue: estima con la
# matriz del BFGS (`hessian="bfgs"`), no publica `se_method` y no declara la
# capacidad. Con un fue anterior instalado no hacen nada.

def _emula_fue_anterior(mp):
    import fue
    import art.diagnosis as D
    if not D.fue_calcula_hessiano():
        return
    original = fue.Model.fit

    def fit_como_antes(self, *a, **k):
        self.hessian = "bfgs"
        out = original(self, *a, **k)
        r = getattr(self, "_result", None)
        if r is not None:
            r.se_method = None
        return out

    mp.setattr(fue.Model, "fit", fit_como_antes)
    mp.setattr(D, "fue_calcula_hessiano", lambda: False)


@pytest.fixture
def como_fue_anterior():
    mp = pytest.MonkeyPatch()
    _emula_fue_anterior(mp)
    yield
    mp.undo()


@pytest.fixture(scope="module")
def como_fue_anterior_modulo():
    """Para módulos cuyas fixtures de módulo ya estiman (se crean antes que una
    fixture de función)."""
    mp = pytest.MonkeyPatch()
    _emula_fue_anterior(mp)
    yield
    mp.undo()
