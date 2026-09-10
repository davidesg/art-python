"""BUG-0148 — lo que ocurre ANTES de poder pedir tiene que ir en la CABECERA.

La fase 1 movió la doctrina del canal que se empuja al que se pide, y las
pruebas que la guardaban se repuntaron de `_INSTRUCTIONS` a `_PROTOCOLO`. Ese
repunte convirtió, sin querer,

    «esto tiene que EMPUJARSE al modelo»   en   «esto tiene que EXISTIR»

y para casi toda la doctrina da igual —se pide cuando hace falta—. Para una
clase de reglas **no da igual**: las que gobiernan el momento ANTERIOR a que el
modelo pueda pedir nada.

La pregunta inicial es el caso puro. Ocurre antes del primer `art://` posible.
Si sólo está en el recurso, no está.

Y se perdió de verdad: al acortar, «PREGUNTA INICIAL **OBLIGATORIA** … **SIEMPRE**
pregunta primero» quedó en «PREGUNTA PRIMERO», y la prueba que la guardaba
—repuntada a `_PROTOCOLO`, donde el texto viejo sigue— **siguió en verde**. Lo
detectó el analista al ver que el asistente no preguntaba.

Esta prueba fija la lista de lo que NO puede salir de la cabecera.
"""
import pytest

pytest.importorskip("mcp")

import art.mcp_server as M
from tests._texto import dice, dice_todas

LIMITE = 2000


def cab():
    return M._INSTRUCTIONS


# ────────── lo que ocurre antes de poder pedir ──────────

def test_el_IDIOMA_lo_pone_el_usuario_y_el_ingles_es_solo_el_ambiguo():
    """La segunda regla que se cayó al acortar, y por tres palabras.

        antes    (inglés por defecto SI ES AMBIGUO)
        después  (inglés por defecto)

    Son dos reglas distintas. La primera dice «el idioma lo pone el usuario;
    sólo si no se sabe, inglés». La segunda se lee como «por defecto, inglés» —
    y eso es lo que pasó: el asistente contestaba en inglés a un analista que
    escribía en español.

    Es de esta familia porque el idioma se decide en la PRIMERA frase, antes de
    que quepa pedir un recurso.
    """
    c = cab()
    assert dice(c, "SIEMPRE en el idioma DEL USUARIO"), (
        "sin el «SIEMPRE … DEL USUARIO» la regla se lee como preferencia")
    assert dice(c, "si es ambiguo"), (
        "«inglés por defecto» a secas invierte la regla: el inglés es el caso "
        "AMBIGUO, no el defecto")
    assert dice(c, "tradúcelas"), (
        "las salidas vienen en español; sin esto se pegan tal cual")



def test_la_pregunta_inicial_esta_en_la_CABECERA_y_es_obligatoria():
    """No basta con que esté: tiene que estar dicho que es obligatoria y que se
    hace SIEMPRE. «Pregunta primero» se lee como una recomendación, y una
    recomendación en un texto de 2.000 caracteres compite con todo lo demás."""
    c = cab()
    faltan = dice_todas(c, "OBLIGATORIA", "SIEMPRE",
                        "¿Cómo deseas proceder?", "GUIADO", "AUTÓNOMO")
    assert not faltan, f"la pregunta inicial se ha debilitado: falta {faltan}"


def test_el_objetivo_se_pregunta_en_el_carril_autonomo():
    """La otra decisión que no se puede posponer: es lo único que los datos no
    dan, y decide la ruta estacional."""
    c = cab()
    assert dice(c, "PARA QUÉ es el modelo")
    faltan = dice_todas(c, "UNIVARIANTE", "MULTIVARIANTE", "ESTRUCTURAL")
    assert not faltan, faltan


def test_las_dos_puertas_estan_en_la_cabecera():
    """Sin ellas el modelo llama a los instrumentos sueltos, que era la regla
    general antes de que existieran (98 % de las llamadas)."""
    c = cab()
    faltan = dice_todas(c, "guided_identification", "guided_intervention",
                        "build_model")
    assert not faltan, faltan


def test_el_convenio_de_ficheros_esta_en_la_cabecera():
    """Es la familia de defectos más larga del registro, y se incumple en la
    primera llamada — antes de que nadie piense en pedir un recurso."""
    c = cab()
    assert dice(c, ".inp") and dice(c, ".out") and dice(c, ".pre")
    assert dice(c, "get_out_report"), "sin la salida, la regla no es accionable"


def test_como_pedir_mas_esta_en_la_cabecera():
    """El punto que hace que todo lo demás exista: si el modelo no sabe que hay
    un canal que pedir, la fase 1 sólo habría borrado doctrina."""
    c = cab()
    faltan = dice_todas(c, "art://protocolo", "art://defectos", "art://docs")
    assert not faltan, faltan
    assert dice(c, "recortada"), "hay que decir que el texto puede llegar cortado"


# ────────── y el presupuesto sigue en pie ──────────

def test_todo_eso_cabe_en_2000_caracteres():
    """La prueba que impide resolver lo anterior a base de alargar. Si no cabe,
    algo de la lista tiene que salir — y eso es una decisión, no un descuido."""
    n = len(cab())
    assert n <= LIMITE, f"la cabecera mide {n:,} caracteres"


def test_la_cabecera_NO_es_el_protocolo_entero():
    """El contrario: si vuelven a ser el mismo texto, se han vuelto a empujar
    36.000 caracteres por llamada (BUG-0116)."""
    assert cab() != M._PROTOCOLO
    assert len(M._PROTOCOLO) > 30_000
