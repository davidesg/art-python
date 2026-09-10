"""Lo que el modelo puede PEDIR, frente a lo que se le empuja.

BUG-0116, primer punto de fondo. La documentación de `art` se entregaba por un
solo canal —la descripción de cada herramienta, que el protocolo empuja EN CADA
LLAMADA— y un cliente real entregó el 23%: se perdían unos 58.000 caracteres por
sesión, entre ellos la documentación de `easter`, la de `ar_f_freqs` y la de
Shin-Fuller.

Acortar no era el arreglo. El texto hace falta; lo que estaba mal era el canal.
MCP tiene un primitivo para esto y `art` usaba **cero**:

    herramientas   se EMPUJAN en cada llamada   caras, y se recortan
    recursos       se PIDEN cuando hacen falta  completos, direccionables
"""
import asyncio
import os

import pytest

os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv


def _leer(uri):
    r = asyncio.run(srv.mcp.read_resource(uri))
    if isinstance(r, (list, tuple)):
        return "".join(getattr(x, "content", str(x)) for x in r)
    return str(r)


@pytest.fixture(scope="module")
def uris():
    fijos = {str(x.uri) for x in asyncio.run(srv.mcp.list_resources())}
    plantillas = {x.uriTemplate for x in asyncio.run(srv.mcp.list_resource_templates())}
    return fijos, plantillas


def test_el_servidor_expone_recursos(uris):
    """Exponía CERO. Cuarenta y seis herramientas y ningún sitio de donde
    consultar."""
    fijos, plantillas = uris
    assert fijos, "sin recursos, todo vuelve al canal que recorta"
    assert plantillas, "sin plantillas no se puede pedir un informe concreto"


@pytest.mark.parametrize("uri", ["art://defectos", "art://docs", "art://protocolo"])
def test_cada_recurso_fijo_se_lee(uris, uri):
    assert uri in uris[0]
    assert len(_leer(uri)) > 100


# ── el registro de defectos, que es la parte que faltaba ──────────────

def test_el_registro_de_defectos_es_pedible():
    """`guion.py` dice que el valor de una iteración fallida es LA RAZÓN por la
    que se descarta. `art` aplicaba ese principio al análisis y no a sí mismo:
    121 informes con su causa medida, y el modelo que opera la herramienta no
    veía ninguno."""
    t = _leer("art://defectos")
    assert "Registro de defectos" in t
    assert "sin cerrar" in t.lower()


def test_el_indice_dice_PARA_QUE_leerlo():
    """Un índice que sólo lista no se consulta. El que dice cuándo mirar, sí."""
    t = _leer("art://defectos")
    assert "antes de proponer una simplificación" in t.lower()


def test_un_informe_concreto_llega_entero():
    """El caso que lo motivó: la razón por la que NO se capa un AR estaba
    escrita en un informe que el modelo no podía leer — y el asistente propuso
    exactamente eso."""
    t = _leer("art://defectos/BUG-0103")
    assert len(t) > 5000, "llega truncado"
    assert "Shin-Fuller" in t
    assert "hipótesis" in t.lower()


@pytest.mark.parametrize("pedido", ["BUG-0103", "0103", "bug-0103"])
def test_el_identificador_se_admite_como_se_escriba(pedido):
    """El modelo lo escribirá como le salga; que la forma no sea un obstáculo."""
    assert "BUG-0103" in _leer(f"art://defectos/{pedido}")


def test_un_identificador_que_no_existe_lo_DICE(capsys):
    """Y dice dónde mirar, en vez de devolver vacío."""
    t = _leer("art://defectos/BUG-9999")
    assert "no hay" in t.lower()
    assert "art://defectos" in t


# ── los documentos de diseño ──────────────────────────────────────────

def test_el_indice_de_documentos_lista_los_que_hay():
    t = _leer("art://docs")
    assert "ESTUDIO-contrato-de-ficheros-y-semillas" in t


def test_un_documento_llega_entero():
    t = _leer("art://doc/ESTUDIO-contrato-de-ficheros-y-semillas")
    assert len(t) > 3000
    assert ".pre" in t


def test_un_documento_inexistente_lo_dice():
    assert "no hay" in _leer("art://doc/no_existe").lower()


# ── el protocolo, releíble ────────────────────────────────────────────

def test_el_protocolo_se_puede_RELEER():
    """Va como `instructions` del servidor y llega entero, pero eso ocurre una
    vez: a mitad de un análisis largo puede haber salido de la ventana. Como
    recurso se vuelve a pedir."""
    t = _leer("art://protocolo")
    # Desde ORDEN 1.1 el recurso YA NO es el mismo texto que las
    # `instructions`: aquéllas son una cabecera de 2.000 caracteres y esto es
    # el método entero. La propiedad que la prueba guarda —que se pueda releer
    # y llegue entero— no cambia; cambia dónde vive.
    assert t == srv._PROTOCOLO
    assert len(t) > 30_000, f"el protocolo vino con {len(t):,} caracteres"
    assert "NUNCA SE CAPA UN AR" in t
    assert t != srv._INSTRUCTIONS, (
        "si volvieran a ser el mismo texto, la cabecera habría vuelto a "
        "llevarse los 36.000 caracteres en cada llamada (BUG-0116)")


# ── la propiedad que justifica todo esto ──────────────────────────────

def test_un_recurso_NO_se_recorta_como_una_descripcion():
    """La razón de ser: lo que se pide llega entero. Un informe de 14.000
    caracteres cabe; la descripción de una herramienta de 9.000 no llegaba ni al
    cuarto."""
    t = _leer("art://defectos/BUG-0103")
    assert len(t) > 9000, (
        "si esto se recortara, los recursos no resolverían nada")


def test_leer_un_recurso_no_puede_tumbar_el_servidor(tmp_path, monkeypatch):
    """Un recurso es conveniencia: si el fichero no está, se dice y ya.

    La afirmación cambió con el BUG-0125, y en qué: antes buscaba la palabra
    «no hay». Ese mensaje era el defecto — se lee como «no hay defectos» cuando
    lo que pasa es que esta instalación no los trae, y decir la primera cosa
    cuando pasa la segunda borra la razón (BUG-0090). Lo que se comprueba sigue
    siendo lo mismo: que degrada en vez de reventar, y que lo dice."""
    from art import recursos
    monkeypatch.setattr(recursos, "_RAIZ", str(tmp_path))
    for txt in (recursos.indice_de_documentos(), recursos.indice_de_defectos()):
        assert txt.strip().startswith("*("), "no degrada con una nota"
        assert "BUG-0125" in txt, "no dice por qué no hay material"


# ── que el modelo SEPA que existen ────────────────────────────────────

def test_las_instrucciones_anuncian_los_recursos():
    """Un recurso que nadie sabe que existe es igual que no tenerlo. Y las
    instrucciones son el canal que SÍ llega entero, así que es donde hay que
    anunciarlo."""
    ins = srv._INSTRUCTIONS
    for uri in ("art://protocolo", "art://defectos", "art://docs"):
        assert uri in ins, uri


def test_las_instrucciones_dicen_CUANDO_consultarlos():
    """Listar las URI no basta: hace falta el disparador. «Antes de proponer una
    simplificación que parezca obvia» es el momento en que el registro de
    defectos vale algo."""
    ins = srv._INSTRUCTIONS
    assert "antes de proponer una simplificación" in ins.lower()
    assert "BUG-0103" in ins, "el ejemplo concreto es lo que hace entender cuándo"


def test_las_instrucciones_avisan_de_que_las_descripciones_se_recortan():
    """El modelo no puede saber que le llegó un texto truncado —no ve el
    original— así que hay que decírselo y darle la salida."""
    ins = srv._INSTRUCTIONS.lower()
    assert "recortada" in ins or "truncan" in ins
