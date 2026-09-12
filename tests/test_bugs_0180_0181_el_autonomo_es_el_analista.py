"""BUG-0180 y BUG-0181 — en AUTÓNOMO el LLM es el analista.

0180 (diseño): el protocolo mandaba el AUTÓNOMO a `build_model` —«la heurística
      decide todo»—. El carril que el estudio con varios LLM validó (31 series,
      283 nodos decididos por el LLM, 0.1.x) era otro: el LLM recorre los nodos
      del protocolo y decide cada uno. Sus reglas vivían en el enunciado de cada
      ejercicio y nunca pasaron a art; sin enunciado, el autónomo se reducía a
      una llamada a un auto-ARIMA.

0181: desde 06-sep `confirm_and_estimate` y `estimate_and_diagnose` llevaban
      `modo="guiado"` fijo, así que cada estimación terminaba en ⏸ y el
      protocolo le decía al LLM que ahí acaba su turno. Daba por hecho que
      quien confirma una especificación es siempre un humano.
"""
import inspect
import os
import re
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as M
from art.pipeline import _write_bare_inp
from tests._fuente import cuerpo_de
from tests._texto import dice

HERRAMIENTAS_CON_SOBRE = ("confirm_and_estimate", "estimate_and_diagnose",
                          "build_model")


def _fn(nombre):
    f = getattr(M, nombre)
    return getattr(f, "fn", f)


def _texto(o):
    return o[0].text if isinstance(o, list) and o else str(o)


@pytest.fixture(scope="module")
def serie(tmp_path_factory):
    d = tmp_path_factory.mktemp("carril")
    r = np.random.default_rng(5)
    n = 144
    t = np.arange(n)
    y = 100.0 * np.exp(0.002 * t + 0.01 * np.sin(2 * np.pi * t / 12)
                       + 0.004 * np.cumsum(r.standard_normal(n)))
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2008, 1), name="IPC_T")
    base = str(d / "IPC_T.inp")
    warnings.simplefilter("ignore")
    _write_bare_inp(ts, base)
    # un modelo ya especificado, para estimate_and_diagnose
    _fn("confirm_and_estimate")(inp_path=base, output_path=str(d / "m.inp"),
                                lam=0.0, d=1, D=0, p=0, q=1, n_harmonics=2,
                                estimate_mu=True)
    return d, base


def _llama(serie, nombre, modo=None):
    d, base = serie
    warnings.simplefilter("ignore")
    kw = {} if modo is None else {"modo": modo}
    tag = modo or "defecto"
    if nombre == "confirm_and_estimate":
        o = _fn(nombre)(inp_path=base, output_path=str(d / f"ce_{tag}.inp"),
                        lam=0.0, d=1, D=0, p=0, q=1, n_harmonics=2,
                        estimate_mu=True, **kw)
    elif nombre == "estimate_and_diagnose":
        o = _fn(nombre)(inp_path=str(d / "m.inp"),
                        output_path=str(d / f"ed_{tag}.inp"), **kw)
    else:  # build_model con spec declarada: el caso que antes paraba
        o = _fn(nombre)(inp_path=base, output_path=str(d / f"bm_{tag}.inp"),
                        d=1, max_rounds=2, **kw)
    return _texto(o)


# ── BUG-0181 — las herramientas ───────────────────────────────────────────

@pytest.mark.parametrize("nombre", HERRAMIENTAS_CON_SOBRE)
def test_en_autonomo_la_salida_no_para(serie, nombre):
    """EL DEFECTO. En autónomo no hay analista humano al que esperar."""
    out = _llama(serie, nombre, "autonomo")
    assert "⏸" not in out, f"{nombre} manda parar al LLM que hace de analista"
    assert dice(out.splitlines()[0], "autónomo")


@pytest.mark.parametrize("nombre", HERRAMIENTAS_CON_SOBRE)
def test_en_guiado_sigue_parando(serie, nombre):
    """Y lo que arregló ce89c8b no se deshace: en guiado decide el analista."""
    out = _llama(serie, nombre, "guiado")
    # Presente, no «al final»: `estimate_and_diagnose` añade la nota de lo
    # guardado DETRÁS de la marca desde antes de este arreglo. Es presentación,
    # no carril —el LLM para igual— y va aparte.
    assert M.FIN_DE_TURNO_GUIADO in out


@pytest.mark.parametrize("nombre", ("confirm_and_estimate",
                                    "estimate_and_diagnose"))
def test_el_defecto_es_el_lado_seguro(serie, nombre):
    """Sin declarar el carril, se para. Olvidarse en autónomo cuesta una
    pregunta; olvidarse en guiado costaría decidir por el analista."""
    assert "⏸" in _llama(serie, nombre)


@pytest.mark.parametrize("nombre", HERRAMIENTAS_CON_SOBRE)
def test_el_carril_viaja_como_enum_en_el_esquema(nombre):
    import asyncio
    tools = {t.name: t for t in asyncio.run(M.mcp.list_tools())}
    prop = tools[nombre].inputSchema["properties"]["modo"]
    assert set(prop.get("enum", [])) == {"guiado", "autonomo"}, (
        "texto libre en el carril es un carril que se escribe mal y cae al "
        "defecto sin que nadie lo vea (BUG-0155)")


def test_ningun_sobre_fija_el_carril_a_mano():
    """El guardián del siguiente: cualquier llamada a `envuelve_iteracion` que
    fije «guiado» a mano vuelve a dar por hecho que confirma un humano."""
    src = open(M.__file__, encoding="utf-8").read()
    fijos = [m.start() for m in re.finditer(
        r"envuelve_iteracion\([^)]*?modo\s*=\s*[\"']guiado", src, re.S)]
    assert not fijos, "hay sobres con el carril fijado a «guiado»"


@pytest.mark.parametrize("nombre", HERRAMIENTAS_CON_SOBRE)
def test_cada_herramienta_con_sobre_acepta_el_carril(nombre):
    assert "modo" in inspect.signature(_fn(nombre)).parameters
    assert "modo" in cuerpo_de(M, nombre)


# ── BUG-0180 — el protocolo ───────────────────────────────────────────────

P = M._INSTRUCTIONS
# La cabecera de la sección, no la primera mención: el párrafo de enrutado la
# nombra antes («…», más abajo).
_CAB = "\nEL CARRIL AUTÓNOMO — TÚ ERES EL ANALISTA\n"


def _seccion_autonoma():
    i = P.index(_CAB)
    j = P.index("\n══════", i + len(_CAB) + 60)
    return P[i:j]


def test_el_autonomo_ya_no_es_build_model():
    assert not dice(P, "Si el usuario elige autónomo → usa build_model"), (
        "el protocolo sigue mandando el autónomo al auto-ARIMA")
    assert dice(P, "AUTÓNOMO NO ES build_model")


def test_el_carril_autonomo_tiene_su_seccion():
    sec = _seccion_autonoma()
    assert dice(sec, "DECIDIENDO TÚ SOLO CADA NODO")
    assert dice(sec, "Eso NO significa ir rápido")


@pytest.mark.parametrize("nodo", ["dominio", "lambda", "estacionalidad",
                                  "media", "modelo base", "intervenciones",
                                  "ordenes", "contrastes", "reformulación"])
def test_la_seccion_recorre_los_nodos(nodo):
    assert nodo in _seccion_autonoma(), (
        f"el nodo «{nodo}» no está en el carril autónomo")


def test_las_reglas_que_valido_el_estudio_estan_escritas():
    sec = _seccion_autonoma()
    assert dice(sec, "NUNCA DECIDAS NODOS EN LOTE")
    assert dice(sec, 'decidido_por="LLM"')
    assert dice(sec, 'modo="autonomo"')
    assert dice(sec, "Un empate se resuelve ESTIMANDO")
    assert "guion_abandon" in sec


def test_la_superficie_y_el_protocolo_dicen_lo_mismo():
    """`guion_node` documenta «LLM» como el decisor del autónomo; el protocolo
    tiene que describir ese mismo carril, no otro."""
    doc = inspect.getdoc(_fn("guion_node"))
    assert '"LLM" (autonomous)' in doc
    assert dice(P, 'decidido_por="LLM"')


def test_build_model_se_presenta_como_atajo():
    doc = inspect.getdoc(_fn("build_model"))
    assert dice(doc, "NO es el modo autónomo")


def test_las_reglas_de_parar_son_del_guiado():
    """«No encadenes pasos» y «decide el usuario» valen en guiado; en autónomo
    son exactamente lo que no hay que hacer."""
    assert dice(P, "En GUIADO, NUNCA encadenes pasos")
    assert not re.search(r"^- NUNCA encadenes pasos", P, re.M)
    assert dice(P, "En GUIADO las decisiones")
