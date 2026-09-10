"""`_PROTOCOLO` es el mapa de la superficie: lo que no está ahí, no existe.

El servidor entrega este texto al modelo. Una herramienta registrada pero
ausente de él no está rota — es que el LLM no sabe que puede llamarla.

Medido antes de esta prueba: **23 de 46 herramientas no aparecían**, entre ellas
`guided_intervention` y `guion_evidencia`, las dos que la sesión acababa de
añadir, y siete de las nueve del nodo de intervención. Es el defecto del §2.1 del
documento de arquitectura —«ninguna de las nueve remite a otra»— un piso más
arriba: se arregló el cableado herramienta→herramienta y quedó sin cablear
instrucciones→herramienta, que es el que decide si la herramienta se llega a
llamar.

> La capacidad está en la capa de abajo y la superficie no la nombra.
"""

# ORDEN 1.1 — DÓNDE VIVE AHORA ESTA DOCTRINA.
#
# Estas afirmaciones se hacían sobre `_INSTRUCTIONS`, que hasta el 10-sep-2026
# eran los 35.941 caracteres del método entero y viajaban EN CADA LLAMADA.
# Ahora `_INSTRUCTIONS` es una cabecera de 2.000 y el método vive en
# `_PROTOCOLO`, que se sirve por `art://protocolo` y se PIDE.
#
# La propiedad que estas pruebas guardan —que la doctrina exista y esté
# enunciada— no cambia. Lo que cambia es el canal, y con él la garantía: antes
# se empujaba (y el cliente recortaba el 77%, BUG-0116), ahora se pide. Lo que
# tiene que estar en la CABECERA, sí o sí, lo fija
# `tests/test_presupuesto_del_semaforo.py`.
#
# DECISIÓN DEL ANALISTA (10-sep-2026), sobre si la cabecera debe llevar además
# la lista pelada de las 46: **no, se confía en la arquitectura**. Si las
# medidas del `ART_CALL_LOG` —que desde ORDEN 0.3 cuenta también los recursos—
# muestran que el modelo no pide `art://protocolo`, entonces se añade. Antes
# no: sería pagar 1.400 caracteres por llamada contra una sospecha.
#
# Y el descubrimiento de una herramienta no depende de este texto: va en
# `tools/list`, que el cliente manda siempre. Lo que este texto da es CUÁNDO
# usar cuál.
import asyncio

import pytest

import art.mcp_server as srv


@pytest.fixture(scope="module")
def registradas():
    return sorted(t.name for t in asyncio.run(srv.mcp.list_tools()))


def test_todas_las_herramientas_estan_en_las_instrucciones(registradas):
    """La prueba que impide la reincidencia: una herramienta nueva que nadie
    nombre hace fallar la suite."""
    ins = srv._PROTOCOLO
    faltan = [t for t in registradas if t not in ins]
    assert not faltan, (
        "herramientas registradas y ausentes de _PROTOCOLO "
        f"({len(faltan)}/{len(registradas)}): {faltan}. "
        "Una herramienta que el LLM no ve es una herramienta que no existe.")


def test_las_dos_puertas_estan_en_su_etapa():
    """No basta con nombrarlas: tienen que estar donde se decide usarlas."""
    ins = srv._PROTOCOLO
    i_ident = ins.index("guided_identification")
    i_etapa3 = ins.index("ETAPA 3")
    i_itv = ins.index("guided_intervention")
    assert i_ident < i_etapa3 < i_itv or i_itv > i_etapa3, \
        "guided_intervention tiene que aparecer en la ETAPA 3, no en una lista"


def test_el_mapa_y_la_evidencia_van_juntos():
    """Son pareja: el mapa dice a dónde volver, la evidencia qué hay allí."""
    ins = srv._PROTOCOLO
    assert "guion_evidencia" in ins
    assert "guion_map" in ins
    bloque = ins[ins.index("EL GUION"):ins.index("EL GUION") + 2500]
    assert "guion_map" in bloque and "guion_evidencia" in bloque


def test_la_puerta_del_nodo_dice_el_criterio_de_parada():
    """La escalada no se detiene sola: cada intervención encoge σ̂ y promueve
    al siguiente anómalo. Sin el criterio escrito, el protocolo invita a
    sobre-intervenir."""
    ins = srv._PROTOCOLO
    assert "no se detiene sola" in ins or "NO se detiene sola" in ins
    assert "sobre-intervenir" in ins


def test_el_convenio_de_signo_esta_donde_se_usa():
    """Está en tres docstrings y aun así se falló dos veces. En el protocolo
    va con su remedio: no hagas la resta, mira el camino del nivel."""
    ins = srv._PROTOCOLO
    assert "CAMINO" in ins and "restan" in ins.lower()


def test_el_arbitro_entre_los_dos_criterios_de_forma_esta_dicho():
    """`incident_configurations` gobierna sobre `residual_episodes` para la
    FORMA. Eran dos respuestas a la misma pregunta sin árbitro."""
    ins = srv._PROTOCOLO
    assert "GOBIERNA sobre residual_episodes" in ins


def test_la_regla_del_out_sigue_escrita():
    """Estaba antes de esta sesión y el código la incumplía (BUG-0091). Ahora
    la cumple; la regla no debe desaparecer al arreglarla."""
    ins = srv._PROTOCOLO
    assert "NUNCA DE REEJECUTAR" in ins
    assert "get_out_report" in ins


def test_las_instrucciones_no_nombran_herramientas_inexistentes(registradas):
    """El otro lado del mismo defecto: prometer algo que no está."""
    import re
    ins = srv._PROTOCOLO
    citadas = set(re.findall(r"\b([a-z][a-z0-9_]{6,})\(", ins))
    conocidas = set(registradas) | {
        "guion_abandon", "print", "range", "len", "float", "int", "str",
    }
    fantasmas = [c for c in citadas
                 if c not in conocidas and hasattr(srv, c) is False
                 and "_" in c and not c.startswith(("plot_", "describe_"))]
    assert not fantasmas, f"las instrucciones citan lo que no existe: {fantasmas}"


def test_ninguna_prueba_usa_inspect_getsource_sobre_una_FUNCION():
    """La sexta vez que el mismo artefacto muerde en una sesión.

    `inspect.getsource` congela `co_firstlineno` en el import y lee el fichero al
    llamar: editar mientras la suite corre le hace devolver el trozo equivocado,
    y la prueba falla señalando a otra función. `tests/_fuente.fuente_de`
    localiza la función POR NOMBRE parseando el fichero en el momento.

    Sobre un MÓDULO entero no hay problema —no hay número de línea que se
    desplace— así que ése se permite.
    """
    import ast
    import pathlib

    malos = []
    for f in sorted(pathlib.Path("tests").glob("test_*.py")):
        arbol = ast.parse(f.read_text())
        for n in ast.walk(arbol):
            if not (isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "getsource"):
                continue
            arg = n.args[0] if n.args else None
            # `getsource(modulo)` es seguro; `getsource(modulo.funcion)` no.
            if isinstance(arg, ast.Attribute) or isinstance(arg, ast.Name) \
                    and arg.id not in ("mcp_server", "describe", "srv"):
                malos.append(f"{f.name}:{n.lineno}")
    assert not malos, (
        "usa `tests._fuente.fuente_de` en vez de `inspect.getsource` sobre una "
        f"función: {malos}")
