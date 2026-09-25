"""BUG-0081 y BUG-0082 — las figuras se pisaban entre sí y ensuciaban `/tmp`.

Son dos caras del mismo bloque, y las dos nacieron del arreglo de BUG-0078.

**0081.** Aquel arreglo discriminaba la ruta con `os.getpid()`, y el servidor MCP
es UN proceso durante toda la sesión: dentro de una sesión no discriminaba nada,
que es justo donde ocurría la colisión. Dos series por los mismos nodos guiados
escribían el mismo `art_boxcox_<pid>.png`, y el analista abría el diagrama de la
otra serie mientras leía los números de ésta. Y `_result` publicaba la ruta de
`_ULTIMA_FIGURA`, una global mutable, no la de su propia figura.

**0082.** El fichero se escribía en el temporal COMPARTIDO, con el mismo patrón
de nombre que la salida real. Cada corrida de la suite sembraba `/tmp` de PNG en
blanco indistinguibles del producto — 49 ficheros de 651 bytes— y el analista
concluyó que art renderizaba en blanco. No lo hacía.
"""
import base64
import io
import os
import subprocess
import sys
import tempfile

import pytest

import art.mcp_server as srv
from art.describe import Description


def _png(color=None) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    f = plt.figure(figsize=(1, 1))
    if color is not None:
        f.patch.set_facecolor(color)
    b = io.BytesIO()
    f.savefig(b, format="png")
    plt.close(f)
    return base64.b64encode(b.getvalue()).decode()


# ───────────── BUG-0081: el discriminante ─────────────

def test_dos_figuras_distintas_no_comparten_fichero():
    a = srv._show_fig(_png(), "boxcox")
    b = srv._show_fig(_png("red"), "boxcox")
    assert a != b
    with open(a, "rb") as fa, open(b, "rb") as fb:
        assert fa.read() != fb.read()


def test_la_misma_figura_vuelve_al_mismo_fichero():
    """La propiedad que se quería conservar: la ventana se reemplaza en vez de
    multiplicarse. Con la huella del contenido sale sola."""
    p = _png("blue")
    assert srv._show_fig(p, "boxcox") == srv._show_fig(p, "boxcox")


def test_el_pid_ya_no_esta_en_la_ruta():
    """Era el discriminante equivocado: sólo separa sesiones distintas, que ya
    estaban separadas por el reloj."""
    assert str(os.getpid()) not in srv._show_fig(_png(), "sin_pid")


def test_la_etiqueta_sigue_en_la_ruta():
    """La huella identifica; la etiqueta es lo que hace la ruta legible."""
    assert "art_seasonality_" in os.path.basename(
        srv._show_fig(_png(), "seasonality"))


# ───────────── BUG-0081: la nota cita SU figura ─────────────

def test_result_cita_su_propia_figura_no_la_ultima():
    a, b = _png(), _png("green")
    pa = srv._show_fig(a, "nodo_1")
    pb = srv._show_fig(b, "nodo_2")
    assert srv._ULTIMA_FIGURA == pb
    txt = "\n".join(getattr(c, "text", "") for c in
                    srv._result(Description(summary="s", figure_b64=a,
                                            recommendation="r")))
    assert pa in txt
    assert pb not in txt


def test_result_nunca_cita_la_ruta_de_otra_figura():
    """Mejor ninguna nota que una que apunta al fichero de otra serie. La nota
    existe para cuando la ventana no aparece: si miente, la red de seguridad
    falla igual que aquello que venía a cubrir.

    ESTA PRUEBA CAMBIÓ CON EL BUG-0122, y conviene decir en qué. Antes exigía
    que `_result` NO citara ninguna ruta cuando la figura no se había escrito
    —`assert "Figura" not in txt`—. La premisa de aquella exigencia era que una
    figura sin escribir fuese un caso a tolerar, y el 0122 la desmonta: quince
    de las veintiocho herramientas que devuelven figura no la escribían nunca,
    así que el caso «no se escribió» no era una excepción rara sino la mitad
    del programa, y el analista se quedaba sin fichero, sin ventana y sin ruta.
    Ahora `_result` la ESCRIBE, y por eso esa rama ya no se puede alcanzar.

    Lo que sobrevive intacto es el contenido de la regla —no citar la ruta de
    otra figura—, y es lo que se comprueba aquí."""
    otra = srv._show_fig(_png(), "otra")
    txt = "\n".join(getattr(c, "text", "") for c in
                    srv._result(Description(summary="s",
                                            figure_b64=_png("yellow"),
                                            recommendation="r")))
    assert otra not in txt, "cita el fichero de otra figura"
    assert srv._huella_figura(_png("yellow")) in srv._FIGURAS, (
        "BUG-0122: _result tiene que escribir la figura que devuelve")


def test_el_registro_no_crece_sin_limite():
    """Una sesión larga no puede acumular una entrada por figura para siempre."""
    for k in range(srv._FIGURAS_TOPE + 20):
        srv._registra_figura(f"b64_{k}", f"/tmp/x{k}.png")
    assert len(srv._FIGURAS) <= srv._FIGURAS_TOPE


# ───────────── BUG-0082: la higiene del temporal ─────────────

def test_art_fig_dir_saca_las_figuras_del_temporal_comun(tmp_path, monkeypatch):
    d = tmp_path / "otro"
    monkeypatch.setenv("ART_FIG_DIR", str(d))
    p = srv._show_fig(_png(), "dirigida")
    assert os.path.dirname(p) == str(d)
    assert os.path.exists(p)


def test_el_conftest_ya_lo_hace_por_defecto():
    """`autouse` a propósito: la higiene no puede depender de que cada prueba
    nueva se acuerde de pedirla."""
    p = srv._show_fig(_png(), "por_defecto")
    assert os.path.dirname(p) != tempfile.gettempdir()
    assert "pytest" in p


def test_una_corrida_de_la_suite_no_deja_nada_en_el_temporal_comun(tmp_path):
    """La comprobación de verdad: correr pruebas que escriben figuras y contar
    lo que queda en `/tmp`. Es lo que el repro mide, aquí como regresión."""
    tmpdir = tempfile.gettempdir()
    antes = set(f for f in os.listdir(tmpdir) if f.startswith("art_"))
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_bug_0078_show_fig.py",
         "-q", "-p", "no:randomly"],
        # La raíz del REPOSITORIO, que es donde está el test que se corre. No
        # se deduce del paquete: instalado (no editable), `art` vive en
        # site-packages y dos niveles por encima no hay ningún `tests/`.
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        capture_output=True, text=True, timeout=300,
        env={**os.environ, "ART_NO_VIEWER": "1"})
    despues = set(f for f in os.listdir(tmpdir) if f.startswith("art_"))
    assert r.returncode == 0, r.stdout[-2000:]
    assert not (despues - antes), f"la suite sembró {despues - antes}"


def test_el_directorio_se_crea_si_no_existe(tmp_path, monkeypatch):
    d = tmp_path / "no" / "existe" / "aun"
    monkeypatch.setenv("ART_FIG_DIR", str(d))
    p = srv._show_fig(_png(), "creado")
    assert os.path.exists(p)
