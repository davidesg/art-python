"""ORDEN 1.3 — las anotaciones, y por qué se VERIFICAN.

`readOnlyHint` no es una etiqueta decorativa: es una **afirmación** sobre la
herramienta. El cliente la usa para no pedir confirmación antes de llamarla. Una
declarada de sólo lectura que escribe hace que el cliente deje de preguntar
antes de una acción que sí modifica el disco — peor que no anotar nada.

Por eso la lista `_SOLO_LECTURA` se declara a mano (es un hecho sobre cada
herramienta, no algo derivable con una heurística: un primer intento por AST dio
`save_identification_report` como de sólo lectura) y se **contrasta** aquí
contra lo que el cuerpo realmente hace.
"""
import ast
import asyncio
from pathlib import Path

import pytest

pytest.importorskip("mcp")

import art.mcp_server as M

FUENTE = Path(M.__file__)

# QUÉ CUENTA COMO ESCRIBIR, que es la decisión de diseño de esta prueba.
#
# `readOnlyHint` gobierna si el cliente pide confirmación. Lo que importa
# confirmar es que se toque el ESTADO DEL ANÁLISIS —el `.inp`, el `.pre`, el
# `.out`, el guion—, no que se deje una figura en el directorio de figuras.
#
# Y la razón no es de comodidad: desde BUG-0122 **toda** herramienta que
# devuelve figura la escribe. Si escribir un PNG descalificara, casi ninguna
# sería de sólo lectura y la anotación no distinguiría nada. La figura es un
# artefacto derivado; el `.pre` es la afirmación.
ESCRITORES = frozenset({
    "_write_inp", "_write_bare_inp", "write_text", "write_pre",
    "save_guion", "registra_version", "run_full", "build_and_fit",
})

# `write_out(path)` escribe; `write_out()` DEVUELVE el texto y no toca el
# disco (fue.Model.write_out: «Write to this file path, or return as a string
# if None»). Es la diferencia entre `get_out_report`, que sólo mira, y el
# pipeline, que deja el registro.
CONDICIONALES = {"write_out": "escribe sólo si se le da una ruta"}


def _escrituras(nodo: ast.AST) -> list[str]:
    """Los escritores que este cuerpo LLAMA de verdad.

    Por AST y no por texto: `guion_map` menciona `guion_abandon(...)` DENTRO
    de una cadena que sugiere al analista, y un emparejado por subcadena lo
    contaba como una llamada. Una prueba que da falsos positivos se acaba
    relajando, y entonces deja de proteger nada.
    """
    fuera = []
    for c in ast.walk(nodo):
        if not isinstance(c, ast.Call):
            continue
        f = c.func
        nombre = f.id if isinstance(f, ast.Name) else (
            f.attr if isinstance(f, ast.Attribute) else "")
        if nombre in ESCRITORES:
            fuera.append(nombre)
        elif nombre in CONDICIONALES and (c.args or c.keywords):
            fuera.append(f"{nombre}(con ruta)")
    return fuera


def _cuerpos():
    """{nombre: nodo AST} de las herramientas registradas."""
    src = FUENTE.read_text(encoding="utf-8")
    return {n.name: n for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.FunctionDef)
            and any(ast.unparse(d).startswith("mcp.tool")
                    for d in n.decorator_list)}


def _tools():
    return asyncio.run(M.mcp.list_tools())


def test_las_46_llevan_anotacion_y_titulo():
    ts = _tools()
    sin = [t.name for t in ts if not (t.annotations and t.annotations.title)]
    assert not sin, f"sin título: {sin}"


def test_ninguna_declarada_de_solo_lectura_ESCRIBE():
    """LA prueba. Si una de `_SOLO_LECTURA` llama a un escritor, la afirmación
    es falsa y el cliente dejará de preguntar antes de una acción que modifica."""
    cuerpos = _cuerpos()
    culpables = {}
    for nombre in sorted(M._SOLO_LECTURA):
        nodo = cuerpos.get(nombre)
        if nodo is None:
            continue
        hallados = _escrituras(nodo)
        if hallados:
            culpables[nombre] = sorted(set(hallados))
    assert not culpables, (
        "declaradas de sólo lectura y llaman a un escritor: "
        + "; ".join(f"{k} → {v}" for k, v in culpables.items()))


def test_la_lista_no_nombra_herramientas_que_no_existen():
    """Una lista a mano envejece. Ésta no puede: si alguien renombra una
    herramienta, aquí se entera."""
    nombres = {t.name for t in _tools()}
    fantasmas = sorted(set(M._SOLO_LECTURA) - nombres)
    assert not fantasmas, f"en _SOLO_LECTURA y no existen: {fantasmas}"
    fantasmas_t = sorted(set(M._TITULOS) - nombres)
    assert not fantasmas_t, f"en _TITULOS y no existen: {fantasmas_t}"


def test_todas_las_herramientas_tienen_titulo_declarado():
    nombres = {t.name for t in _tools()}
    faltan = sorted(nombres - set(M._TITULOS))
    assert not faltan, f"sin título en _TITULOS: {faltan}"


def test_las_que_ESCRIBEN_no_estan_marcadas_de_solo_lectura():
    """El otro lado: las puertas y el pipeline escriben, y tienen que decirlo."""
    for n in ("confirm_and_estimate", "build_model", "batch_build",
              "guion_node", "guion_abandon", "record_version",
              "suggest_intervention_form", "meg_reformulate",
              "save_identification_report"):
        assert n not in M._SOLO_LECTURA, f"{n} escribe y está como sólo lectura"


def test_ninguna_se_declara_destructiva():
    """Ninguna borra ni sobrescribe lo que no creó. La única que destruye
    información es `guion_abandon`, y no borra: MARCA, con su `why` obligatorio."""
    for t in _tools():
        assert t.annotations.destructiveHint is False, t.name


def test_el_detector_NO_es_vacuo():
    """La trampa de una prueba como la de arriba: pasar porque no detecta nada.

    Si `_escrituras` dejara de reconocer los escritores, `test_ninguna_
    declarada_de_solo_lectura_ESCRIBE` pasaría siempre y no protegería nada.
    Aquí se exige que SÍ los vea donde los hay.
    """
    cuerpos = _cuerpos()
    for nombre in ("confirm_and_estimate", "build_model", "guion_node"):
        assert _escrituras(cuerpos[nombre]), (
            f"el detector no ve ninguna escritura en {nombre}, que escribe")
    # y que no las vea donde no las hay
    assert not _escrituras(cuerpos["series_info"])
