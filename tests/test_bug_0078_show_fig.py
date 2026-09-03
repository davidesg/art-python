"""BUG-0078 — `_show_fig` no podía fallar de forma visible.

Cuatro problemas en catorce líneas, y los cuatro apuntan al mismo sitio:
silenciaba al visor, no comprobaba nada, pisaba el fichero entre herramientas
que compartieran etiqueta, y nunca decía dónde había escrito.

Lo destapó el analista con un «no se renderizó»: la figura estaba generada y
escrita correctamente en /tmp, la ventana no apareció, y no había ni un indicio
en la salida de la herramienta.
"""
import base64
import io as _io
import os

import pytest

import art.mcp_server as srv

# `_show_fig` ya se detecta bajo pytest y no abre ventana, pero se fija aquí
# también con la variable de entorno: si alguien quita esa detección, estas
# pruebas no deben empezar a abrir ventanas en blanco en la pantalla de nadie.
os.environ.setdefault("ART_NO_VIEWER", "1")


def _png() -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    f = plt.figure(figsize=(1, 1))
    b = _io.BytesIO()
    f.savefig(b, format="png")
    plt.close(f)
    return base64.b64encode(b.getvalue()).decode()


def test_devuelve_la_ruta_donde_escribio():
    """Es la mitad del arreglo: quien llama puede decirla."""
    p = srv._show_fig(_png(), "prueba_ruta")
    assert p and os.path.exists(p)
    assert p.endswith(".png")


def test_sin_figura_devuelve_cadena_vacia():
    assert srv._show_fig(None, "x") == ""
    assert srv._show_fig("", "x") == ""


def test_dos_herramientas_con_la_misma_etiqueta_no_se_pisan_entre_procesos():
    """La ruta llevaba SÓLO la etiqueta, y las etiquetas las elige cada
    herramienta a mano: dos que coincidieran se sobrescribían la figura, y el
    analista se quedaba mirando la de otra llamada."""
    p = srv._show_fig(_png(), "colision")
    assert str(os.getpid()) in p, "la ruta discrimina por proceso"


def test_la_misma_etiqueta_en_el_mismo_proceso_SI_reemplaza():
    """Estable dentro de una sesión: la ventana se reemplaza en vez de
    multiplicarse, que es la razón por la que la ruta era estable."""
    a = srv._show_fig(_png(), "estable")
    b = srv._show_fig(_png(), "estable")
    assert a == b


def test_la_nota_dice_la_ruta():
    p = srv._show_fig(_png(), "nota")
    nota = srv._nota_figura(p)
    assert p in nota
    assert "Figura" in nota


def test_la_nota_avisa_si_el_visor_fallo():
    srv._ULTIMO_VISOR_ERROR = "xdg-open no está instalado"
    nota = srv._nota_figura("/tmp/x.png")
    assert "no se pudo abrir sola" in nota
    assert "xdg-open no está instalado" in nota
    srv._ULTIMO_VISOR_ERROR = ""


def test_sin_ruta_no_hay_nota():
    assert srv._nota_figura("") == ""


def test_un_visor_que_no_existe_devuelve_el_motivo(monkeypatch):
    """No poder abrir una ventana no debe levantar excepción — pero tampoco
    pasar inadvertido, que era el bug."""
    import subprocess

    def _revienta(*a, **k):
        raise FileNotFoundError("xdg-open")

    monkeypatch.setattr(subprocess, "run", _revienta)
    assert "no está instalado" in srv._abrir_visor("/tmp/x.png")


def test_un_visor_que_sale_con_error_devuelve_su_mensaje(monkeypatch):
    import subprocess

    class _R:
        returncode = 3
        stderr = "no display"
        stdout = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _R())
    assert srv._abrir_visor("/tmp/x.png") == "no display"


def test_un_visor_que_se_queda_en_primer_plano_NO_es_un_fallo(monkeypatch):
    """Es lo normal con muchos visores: arrancan y no devuelven."""
    import subprocess

    def _cuelga(*a, **k):
        raise subprocess.TimeoutExpired("xdg-open", 5)

    monkeypatch.setattr(subprocess, "run", _cuelga)
    assert srv._abrir_visor("/tmp/x.png") == ""


def test_el_resultado_lleva_la_nota_cuando_hay_figura():
    """La nota va en `_result`, que es por donde pasan todas las herramientas."""
    from art.describe import Description
    srv._show_fig(_png(), "en_result")
    items = srv._result(Description(summary="s", figure_b64=_png(),
                                    recommendation="r", data={}))
    assert "Figura:" in items[0].text


def test_y_no_la_lleva_cuando_no_hay_figura():
    from art.describe import Description
    items = srv._result(Description(summary="s", figure_b64=None,
                                    recommendation="r", data={}))
    assert "Figura:" not in items[0].text


def test_la_suite_no_abre_ventanas():
    """Regresión de la regresión, y la encontró el analista mirando su pantalla.

    Al hacer el lanzamiento del visor SÍNCRONO —para poder detectar sus fallos,
    que era el bug— la suite empezó a abrir una ventana por cada figura que
    genera: cientos, y las de prueba en blanco. La versión anterior con `Popen`
    en hilo daemon fallaba tan deprisa que casi nunca llegaba a abrir nada, y
    por eso nadie lo había notado.
    """
    import inspect
    src = inspect.getsource(srv._show_fig)
    assert "ART_NO_VIEWER" in src
    assert "pytest" in src


# ───────────── multiplataforma ─────────────
#
# La versión anterior llamaba a `xdg-open` sin más, que existe sólo en
# Linux/freedesktop. En Windows y en macOS esta vía no ha funcionado NUNCA, y
# nadie se enteró porque el FileNotFoundError se lo tragaba el hilo daemon con
# la salida a /dev/null — el mismo defecto que el bug.
#
# Lo señaló el analista: «en claude code windows los gráficos se renderizaban
# bien». Y es cierto, pero por la OTRA vía: la figura viaja además como
# `ImageContent` en la respuesta MCP y eso lo pinta el cliente en cualquier
# sistema. La ventana del escritorio es un extra.

def test_en_windows_usa_startfile(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    llamado = {}
    monkeypatch.setattr(srv.os, "startfile",
                        lambda p: llamado.setdefault("path", p), raising=False)
    assert srv._abrir_visor("/tmp/x.png") == ""
    assert llamado["path"] == "/tmp/x.png"


def test_en_macos_usa_open(monkeypatch):
    import subprocess
    visto = {}

    class _R:
        returncode = 0
        stderr = ""
        stdout = ""

    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr(subprocess, "run",
                        lambda a, **k: (visto.setdefault("cmd", a[0]), _R())[1])
    assert srv._abrir_visor("/tmp/x.png") == ""
    assert visto["cmd"] == "open"


def test_en_linux_usa_xdg_open(monkeypatch):
    import subprocess
    visto = {}

    class _R:
        returncode = 0
        stderr = ""
        stdout = ""

    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr(subprocess, "run",
                        lambda a, **k: (visto.setdefault("cmd", a[0]), _R())[1])
    srv._abrir_visor("/tmp/x.png")
    assert visto["cmd"] == "xdg-open"


def test_la_ruta_no_supone_que_exista_slash_tmp():
    """`/tmp` no existe en Windows."""
    import inspect, tempfile
    src = inspect.getsource(srv._show_fig)
    assert "tempfile.gettempdir()" in src
    assert '"/tmp/art_' not in src
