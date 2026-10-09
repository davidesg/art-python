"""BUG-0225 … BUG-0231 — el carril GUIADO del IPC de España (P02, 8-oct-2026).

Un recorrido guiado completo sobre IPC_ES (desestacionalizado, 2002-2019), con
guion, y lo que cada salida tiene que decir. La regla de d que atraviesa 0226 y
0227 —un paso cada vez: desde d=0 sólo d=1, desde d=1 sólo d=2, nunca por
debajo de la d confirmada, y sin preguntar por otra diferencia con la
estacionalidad sin tratar— tiene además sus pruebas de política, sin MCP.
"""
import os
import re
import shutil
import tempfile

import pytest

os.environ.setdefault("ART_NO_VIEWER", "1")

from art import mcp_server as s
from art import policy as pol

INP = os.path.join(os.path.dirname(__file__), "..", "bugs", "BUG-0225-repro",
                   "IPC_ES.inp")


def T(r):
    return r if isinstance(r, str) else "\n".join(
        t for c in r if isinstance(t := getattr(c, "text", None), str))


@pytest.fixture(scope="module")
def recorrido():
    w = tempfile.mkdtemp(prefix="bug0225-")
    shutil.copy(INP, w)
    inp, g = os.path.join(w, "IPC_ES.inp"), os.path.join(w, "g.json")
    GI = dict(guion_path=g, domain="price_index")
    out = {"inp": inp, "g": g, "w": w}
    out["t1"] = T(s.guided_identification(inp, expectativas="índice; inercia", **GI))
    out["t2"] = T(s.guided_identification(inp, lam=0, razon="dominio", **GI))
    out["t3"] = T(s.guided_identification(inp, lam=0, d=1, razon="tendencia", **GI))
    out["t4"] = T(s.guided_identification(inp, lam=0, d=1, D=0, razon="sin est.", **GI))
    kw = dict(lam=0, d=1, D=0, n_harmonics=0, seasonal=False, estimate_mu=True,
              domain="price_index", guion_path=g)
    out["m1"] = T(s.confirm_and_estimate(inp, os.path.join(w, "m01.inp"), p=0, q=1,
                                         guion_name="m01", **kw))
    out["m2"] = T(s.confirm_and_estimate(inp, os.path.join(w, "m02.inp"), p=1, q=0,
                                         parent=5, guion_name="m02", **kw))
    out["m3"] = T(s.confirm_and_estimate(inp, os.path.join(w, "m03.inp"), p=2, q=0,
                                         parent=7, guion_name="m03", **kw))
    yield out
    shutil.rmtree(w, ignore_errors=True)


# ── BUG-0225 ────────────────────────────────────────────────────────────────
def test_0225_boxcox_con_signo_y_sin_se_pasa(recorrido):
    t = recorrido["t1"]
    assert "varianza homogénea" not in t
    assert "→ se pasa" not in t
    assert "corr = -0.305" in t or "corr = −0.305" in t


# ── BUG-0226 ────────────────────────────────────────────────────────────────
def test_0226_la_propuesta_de_d_es_la_que_se_recomienda(recorrido):
    assert "**d** pendiente (propuesta: 1)" in recorrido["t2"]
    assert "**d = 1** — coincide con la propuesta" in recorrido["t3"]


# ── BUG-0227 y la regla de un paso ───────────────────────────────────────────
def test_0227_el_paso_3_no_reabre_d0(recorrido):
    t = recorrido["t3"]
    assert "recomendación de la tabla es d=0" not in t
    seccion = t.split("¿Hace falta una diferencia más?")[-1]
    assert "| 0 |" not in seccion
    assert "| 1 |" in seccion and "| 2 |" in seccion


def _ev(rec, filas, trend=0.0):
    return {"recommended_d": rec, "trend_r2": trend,
            "results": [{"d": d, "verdict": v} for d, v in filas]}


def test_regla_nunca_por_debajo_de_la_d_actual():
    assert pol.decide_d(_ev(0, [(0, "ambiguous"), (1, "ambiguous")]), current_d=1) == 1


def test_regla_desde_d1_fila_ambigua_no_da_el_segundo_paso():
    # ADF no rechaza en 1 (rec=2) pero el KPSS acepta: fila ambigua, se queda.
    ev = _ev(2, [(1, "ambiguous"), (2, "stationary")])
    assert pol.decide_d(ev, current_d=1) == 1
    assert pol.razon_d(ev, current_d=1) == "paso"


def test_regla_desde_d1_los_dos_ven_raiz_si_da_el_segundo_paso():
    ev = _ev(2, [(1, "unit_root"), (2, "stationary")])
    assert pol.decide_d(ev, current_d=1) == 2


def test_regla_desde_d0_nunca_salta_a_2():
    ev = _ev(2, [(0, "unit_root"), (1, "unit_root"), (2, "stationary")])
    assert pol.decide_d(ev, current_d=0) == 1


def test_regla_con_estacionalidad_tope_en_1():
    ev = _ev(2, [(1, "unit_root"), (2, "stationary")])
    assert pol.decide_d(ev, seasonal=True, current_d=1) == 1


# ── BUG-0229 ────────────────────────────────────────────────────────────────
def test_0229_el_primer_candidato_no_cierra_el_empate(recorrido):
    assert "ordenes = ARMA(0,1)" not in recorrido["m1"]
    assert "**ordenes** sigue pendiente" in recorrido["m1"]


# ── BUG-0230 ────────────────────────────────────────────────────────────────
def test_0230_no_se_ofrece_adoptar_una_sobreparametrizacion(recorrido):
    m3 = recorrido["m3"]
    assert "Adoptar este modelo" not in m3
    assert "Quitar lo que sobra" in m3 and "AR(2) con t =" in m3


def test_0230_sobreparametrizar_estima_de_verdad(recorrido):
    m2 = recorrido["m2"]
    assert "Adoptar este modelo" in m2
    assert "overparameterization_analysis(" not in m2
    assert re.search(r"base_pre_path=.*p=2, q=0", m2)


# ── BUG-0231 ────────────────────────────────────────────────────────────────
def test_0231_la_diagnosis_cita_la_Q_en_12_y_24(recorrido):
    linea = next(l for l in recorrido["m2"].splitlines() if "Ruido blanco (Q)" in l)
    assert "Q(12)=" in linea and "Q(24)=" in linea and "decide 3f+3" in linea


# ── BUG-0229, el cierre: guion_node y el mapa ────────────────────────────────
def test_0229_el_nodo_explicito_cierra_el_pendiente_y_el_mapa_no_miente(recorrido):
    g = recorrido["g"]
    r = T(s.guion_node(g, "ordenes", "AR(1) (m02)", razon="empate; dominio",
                       criterio="dominio", parent=7))
    assert "estaba pendiente" in r
    # cerrar un pendiente no le cambia el sitio: con parent=7 hacía un ciclo
    import json
    es = {e["version"]: e for e in json.load(open(g))["entries"]}
    assert es[5]["parent"] != 7 and es[7]["parent"] == 5
    assert "m02" in T(s.guion_map(g))
    mp = T(s.guion_map(g))
    assert "sin modelo estimado detrás" not in mp
    assert "el analista corrigió 0" in mp


def test_0230_un_arma11_persistente_y_significativo_no_sobra():
    """Falso positivo del primer arreglo: Salamanca ARMA(1,1), corr(φ̂, θ̂) =
    0,75 con t = 27 y t = 8. Se puede adoptar, pero con el aviso de fue
    (umbral 0,7), que no se sube."""
    w = tempfile.mkdtemp(prefix="bug0230-")
    src = os.path.join(os.path.dirname(__file__), "..", "bugs", "BUG-0208-repro",
                       "Salamanca.inp")
    shutil.copy(src, w)
    inp = os.path.join(w, "Salamanca.inp")
    r = T(s.confirm_and_estimate(inp, os.path.join(w, "m.inp"), lam=0, d=1, D=0,
                                 p=1, q=1, n_harmonics=0, seasonal=False,
                                 estimate_mu=True, domain="multiplicative"))
    assert "Quitar lo que sobra" not in r
    assert "Adoptar este modelo" in r
    # el aviso de fue (umbral 0,7) se da también en la decisión
    assert "por encima de 0,7" in r
