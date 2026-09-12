"""BUG-0182 y BUG-0183 — los dos salieron del run 6 de IPC_ES (autónomo).

0182: el LLM, haciendo de analista, metió una RAMPA en el nivel (07/2008) para
      resolver una discrepancia SF/DCD en f=0. Una rampa es un escalón pasado
      por 1/(1−B) —ganancia infinita, tendencia determinista desde la fecha—: la
      previsión hereda esa pendiente para siempre y la banda no recoge
      incertidumbre sobre ella. En el run fijó la inflación de largo plazo en
      0,94 % anual. art la ofrecía como una forma más, sin una palabra.

0183: el asistente ofreció «Previsión / Estructural / Ambos» como objetivos. El
      protocolo dice univariante · multivariante · estructural; `objetivo`
      viajaba como texto libre y la política convertía lo desconocido en
      «univariante» en silencio. Se perdió justo el único que veta algo.
"""
import asyncio
import inspect
import os
import re
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as M
from art import policy
from art.pipeline import _write_bare_inp
from tests._texto import dice


def _fn(n):
    f = getattr(M, n)
    return getattr(f, "fn", f)


def _todo(o):
    """TODOS los bloques de texto: una herramienta puede devolver varios."""
    if isinstance(o, list):
        return "\n".join(getattr(c, "text", "") or "" for c in o)
    return str(o)


@pytest.fixture(scope="module")
def indice(tmp_path_factory):
    """Un índice de precios con la inflación media que cae a mitad de muestra."""
    d = tmp_path_factory.mktemp("rampa")
    r = np.random.default_rng(3)
    n = 144
    g = np.where(np.arange(n) < 60, 0.0030, 0.0008)          # 3,6 % → 1,0 % anual
    ly = np.log(100.0) + np.cumsum(g + 0.002 * r.standard_normal(n))
    ts = fue.TimeSeries(np.exp(ly).tolist(), freq=12, start=(2008, 1), name="IPC_R")
    base = str(d / "IPC_R.inp")
    warnings.simplefilter("ignore")
    _write_bare_inp(ts, base)
    _fn("confirm_and_estimate")(inp_path=base, output_path=str(d / "m0.inp"),
                                lam=0.0, d=1, D=0, p=1, q=0, n_harmonics=0,
                                estimate_mu=True)
    return d


# ── BUG-0182 — la rampa ──────────────────────────────────────────────────

def test_en_autonomo_la_rampa_se_rechaza(indice):
    warnings.simplefilter("ignore")
    t = _todo(_fn("suggest_intervention_form")(
        str(indice / "m0.inp"), str(indice / "r_auto.inp"),
        date="01/2013", form="ramp", modo="autonomo"))
    assert "no se admite en el carril AUTÓNOMO" in t
    assert dice(t, "vuelve al nodo d"), "el rechazo tiene que decir qué hacer"
    assert not os.path.exists(indice / "r_auto.inp"), "se rechaza ANTES de escribir"


def test_guided_intervention_pasa_el_carril_a_quien_construye(indice):
    warnings.simplefilter("ignore")
    t = _todo(_fn("guided_intervention")(
        inp_path=str(indice / "m0.inp"), output_path=str(indice / "gi.inp"),
        date="01/2013", form="ramp", modo="autonomo"))
    assert "no se admite en el carril AUTÓNOMO" in t


@pytest.fixture(scope="module")
def con_rampa(indice):
    warnings.simplefilter("ignore")
    out = _fn("suggest_intervention_form")(
        str(indice / "m0.inp"), str(indice / "r.inp"),
        date="01/2013", form="ramp", modo="guiado")
    return _todo(out), str(indice / "r.pre")


def test_en_guiado_se_admite_y_avisa(con_rampa):
    t, _ = con_rampa
    assert "RAMPA EN EL NIVEL" in t
    assert dice(t, "banda no recoge incertidumbre")
    assert "Zivot-Andrews" in t


def test_el_aviso_da_la_cifra_que_se_estimo(con_rampa):
    """El aviso no es prosa genérica: ω es el que está en el `.pre`."""
    t, pre = con_rampa
    _, m = fue.load(pre)
    rampa = [it for it in m.interventions if it.type == "ramp"][0]
    om = float(np.ravel(rampa.omega)[0])
    mo = re.search(r"ω = ([+-]\d+\.\d+)% por periodo ≈ ([+-]\d+\.\d+)% al año", t)
    assert mo, "el aviso no trae la cifra"
    assert abs(float(mo.group(1)) - om) < 5e-4
    assert abs(float(mo.group(2)) - 12 * om) < 5e-3


def test_un_modelo_sin_rampa_no_avisa(indice):
    from art.pipeline import mirar
    _, m = mirar(str(indice / "m0.pre"))
    assert M.aviso_rampa(m) == ""


def test_el_aviso_sale_tambien_al_reestimar_un_modelo_con_rampa(con_rampa, indice):
    """Una rampa que entra por otra puerta —un `.pre` encadenado, un `.inp`
    editado a mano— sigue fijando la previsión, y hay que decirlo."""
    warnings.simplefilter("ignore")
    t = _todo(_fn("estimate_and_diagnose")(str(indice / "r.inp"), modo="autonomo"))
    assert "RAMPA EN EL NIVEL" in t


def test_ninguna_regla_automatica_elige_una_rampa():
    """La escalera de Ockham y `decide_form` sólo devuelven escalón o impulso:
    la única puerta de una rampa es pedirla, y ésa tiene el cerrojo."""
    from tests._fuente import fuente_de
    src = fuente_de(policy, "decide_form")
    assert '"ramp"' not in src and "'ramp'" not in src
    from art import escalera
    assert '"ramp"' not in open(escalera.__file__, encoding="utf-8").read()


@pytest.mark.parametrize("n", ["suggest_intervention_form", "guided_intervention"])
def test_el_carril_viaja_como_enum(n):
    tools = {t.name: t for t in asyncio.run(M.mcp.list_tools())}
    assert set(tools[n].inputSchema["properties"]["modo"]["enum"]) == {
        "guiado", "autonomo"}


def test_el_protocolo_lo_dice_en_los_dos_carriles():
    P = M._INSTRUCTIONS
    assert dice(P, "NO USES RAMPAS")
    assert dice(P, "RAMPA — INSTRUMENTO DE USUARIO AVANZADO")


# ── BUG-0183 — el objetivo ───────────────────────────────────────────────

def test_toda_herramienta_con_objetivo_lo_publica_como_enum():
    """El guardián: cualquier `objetivo` del esquema lleva sus valores."""
    tools = asyncio.run(M.mcp.list_tools())
    con = [t for t in tools if "objetivo" in t.inputSchema.get("properties", {})]
    assert len(con) >= 3
    for t in con:
        assert set(t.inputSchema["properties"]["objetivo"].get("enum") or []) == \
            set(policy.OBJETIVOS), f"{t.name}: objetivo como texto libre"


@pytest.mark.parametrize("v,esperado", [("univariante", "univariante"),
                                        ("MULTIVARIANTE", "multivariante"),
                                        (" estructural ", "estructural"),
                                        ("", "univariante")])
def test_los_valores_validos_pasan(v, esperado):
    assert M.objetivo_declarado(v) == esperado


@pytest.mark.parametrize("v", ["previsión", "prevision", "ambos",
                               "sin preferencia", "forecast"])
def test_lo_que_no_es_un_objetivo_se_rechaza(v):
    with pytest.raises(ValueError) as e:
        M.objetivo_declarado(v)
    assert "multivariante" in str(e.value)


def test_build_model_ya_no_lo_convierte_en_univariante(indice):
    t = _todo(_fn("build_model")(str(indice / "m0.inp"), str(indice / "bm.inp"),
                                 objetivo="previsión", max_rounds=1))
    assert "no es un objetivo de art" in t


def test_el_protocolo_manda_presentar_las_tres_tal_cual():
    P = M._INSTRUCTIONS
    assert dice(P, "PRESÉNTALAS TAL CUAL: LAS TRES, CON ESOS NOMBRES")
    assert dice(P, "Prever una serie sola es «univariante»")


def test_el_protocolo_no_manda_el_objetivo_donde_no_llega():
    """confirm_and_estimate no lo lee: pasárselo se ignora en silencio."""
    P = M._INSTRUCTIONS
    assert not dice(P, "objetivo= en guided_identification y confirm_and_estimate")
    assert "objetivo" not in inspect.signature(_fn("confirm_and_estimate")).parameters


def test_en_autonomo_el_multivariante_tiene_su_regla():
    assert dice(M._INSTRUCTIONS, "CON OBJETIVO MULTIVARIANTE, LA ESTACIONALIDAD "
                                 "QUEDA DETERMINISTA")
