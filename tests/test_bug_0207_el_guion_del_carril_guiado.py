"""BUG-0207 — el guion del carril guiado no se escribía solo.

Siete defectos, uno por bloque:

D1  `guided_identification` no escribía nodos: λ, d, la estacionalidad y los
    órdenes —todo lo anterior al primer modelo— quedaban fuera del guion.
D2  `criterio="dominio"` exige un nodo `dominio` y el flujo guiado no lo creaba.
D3  `q_pass` lo decide Q(3s+3): un modelo con Q(12) p=0,0003 salía Q✓ en el
    mapa y «el modelo se sostiene» en la conclusión.
D4  lo que ve la diagnosis no llegaba a `problems_found`, y no había forma de
    anotar una versión ya registrada.
D5  en `confirm_and_estimate` modo nuevo el padre no se podía declarar.
D6  nadie escribía `status="adopted"`; «adoptar» reinscribiendo duplicaba.
D7  el aviso de instrumento contaba los NODOS, que no se calculan.
"""
import json
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.guion import (Guion, GuionEntry, GuionStats, adopt, annotate,
                       hallazgos_de_la_diagnosis, load_guion, q_estado,
                       q_marca, save_guion)
from art.pipeline import _RESCALE_FACTOR, _write_inp


def _fn(tool):
    return getattr(tool, "fn", tool)


def _txt(out):
    return "\n".join(x if isinstance(x, str) else getattr(x, "text", "")
                     for x in out)


def _call(tool, *a, **k):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return _txt(_fn(tool)(*a, **k))


def _entradas(gp):
    return json.load(open(gp))["entries"]


@pytest.fixture(scope="module")
def serie(tmp_path_factory):
    """Un índice mensual: deriva, estacionalidad y un AR(1) en la inflación."""
    d = tmp_path_factory.mktemp("b207")
    rng = np.random.default_rng(207)
    n = 168
    a = rng.standard_normal(n) * 0.004
    infl = np.zeros(n)
    for t in range(1, n):
        infl[t] = 0.5 * infl[t - 1] + a[t]
    est = 0.01 * np.sin(2 * np.pi * np.arange(n) / 12)
    y = np.exp(np.log(80) + np.cumsum(infl + 0.002) + est)
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2005, 1), name="IPCX")
    f = str(d / "IPCX.inp")
    _write_inp(ts, fue.Model(ts, d=1, boxlam=0.0, refactor=_RESCALE_FACTOR), f)
    return d, f


# ── D1 + D2 ──────────────────────────────────────────────────────────────

def test_D1_D2_el_carril_guiado_escribe_sus_nodos(serie):
    d, inp = serie
    gp = str(d / "d1_guion.json")
    t1 = _call(srv.guided_identification, inp, domain="price_index",
               guion_path=gp)
    # D2: sin expectativas el nodo dominio no se inventa: se piden.
    assert "Falta el nodo `dominio`" in t1
    nodos = [(e["node"] or {}).get("nodo") for e in _entradas(gp)]
    assert nodos == ["lambda"]
    assert (_entradas(gp)[0]["node"] or {}).get("pendiente")

    _call(srv.guided_identification, inp, lam=0, domain="price_index",
          guion_path=gp, expectativas="inercia: AR con φ>0")
    _call(srv.guided_identification, inp, lam=0, d=1, guion_path=gp,
          razon="tendencia clara")
    _call(srv.guided_identification, inp, lam=0, d=1, D=1, guion_path=gp,
          razon="B2: el objetivo es prever")
    es = _entradas(gp)
    por_nodo = {(e["node"] or {}).get("nodo"): e for e in es}
    assert set(por_nodo) == {"lambda", "dominio", "d", "estacionalidad", "ordenes"}
    assert all(e["kind"] == "node" for e in es)
    assert json.load(open(gp))["series"] == "IPCX"
    # λ: propuesta 0 por la regla de dominio, elegido 0 → coincide (por VALOR)
    lam = por_nodo["lambda"]
    assert lam["node"]["decidido"] == "0" and lam["coincide"] is True
    assert "gap=" in lam["node"]["evidencia"]
    # d: confirmado con la razón de la llamada que lo trajo
    assert por_nodo["d"]["node"]["decidido"] == "1"
    assert por_nodo["d"]["rationale"] == "tendencia clara"
    assert "ADF" in por_nodo["d"]["node"]["evidencia"]
    # estacionalidad: decidido D=1 con su ruta; no pendiente
    est = por_nodo["estacionalidad"]
    assert est["node"]["decidido"].startswith("D=1")
    assert not est["node"].get("pendiente")
    # órdenes: PENDIENTE hasta que se estime
    assert por_nodo["ordenes"]["node"].get("pendiente")
    assert por_nodo["ordenes"]["propuesta"].startswith("ARMA(")
    # D2: con el nodo dominio escrito, `criterio="dominio"` se admite
    t = _call(srv.guion_node, gp, "media", "μ libre", razon="deriva",
              criterio="dominio")
    assert "Error" not in t and "no tiene" not in t


def test_D1_repetir_una_llamada_no_duplica_el_nodo(serie):
    d, inp = serie
    gp = str(d / "d1b_guion.json")
    for _ in range(2):
        _call(srv.guided_identification, inp, lam=0, guion_path=gp,
              expectativas="sin expectativa")
    nodos = [(e["node"] or {}).get("nodo") for e in _entradas(gp)]
    assert nodos.count("d") == 1 and nodos.count("dominio") == 1


def test_D1_confirm_and_estimate_cierra_el_nodo_de_ordenes(serie):
    d, inp = serie
    gp = str(d / "d1c_guion.json")
    for kw in (dict(), dict(lam=0), dict(lam=0, d=1), dict(lam=0, d=1, D=1)):
        _call(srv.guided_identification, inp, guion_path=gp,
              expectativas="inercia", **kw)
    prop = next(e for e in _entradas(gp)
                if (e["node"] or {}).get("nodo") == "ordenes")["node"]["propuesta_valor"]
    p, q, P, Q = prop
    _call(srv.confirm_and_estimate, inp, str(d / "c01.inp"), lam=0, d=1, D=1,
          p=p, q=q, P=P, Q=Q, guion_path=gp, guion_name="c01")
    es = _entradas(gp)
    ordn = next(e for e in es if (e["node"] or {}).get("nodo") == "ordenes")
    assert not ordn["node"].get("pendiente") and ordn["coincide"] is True
    # el nodo es la etapa 1 del modelo: el modelo cuelga de él
    assert es[-1]["kind"] == "model" and es[-1]["parent"] == ordn["version"]


# ── D3 ───────────────────────────────────────────────────────────────────

def _stats(q_pass=True, pv=(0.0003, 0.006, 0.20, 0.30)):
    return GuionStats(loglik=-40.0, q_pass=q_pass, jb_pass=True,
                      q_lags=[12, 24, 36, 39], q_pvalues=list(pv), nobs=216)


def test_D3_pasa_con_salvedad_es_un_tercer_estado():
    assert q_estado(_stats()) == "salvedad"
    assert q_marca(_stats()) == "Q⚠(12,24)"
    assert q_estado(_stats(pv=(0.3, 0.4, 0.5, 0.6))) == "pasa"
    assert q_estado(_stats(q_pass=False, pv=(0.3, 0.4, 0.5, 0.01))) == "rechaza"
    assert q_estado(GuionStats()) is None


def test_D3_el_mapa_no_pinta_Q_check_con_salvedad(tmp_path):
    g = Guion(series="X", analyst="", created="2026-10-06")
    g.entries = [GuionEntry(version=1, name="m01", inp_path="", timestamp="",
                            spec={}, stats=_stats(), equation="", decision="",
                            rationale="", problems_found="", next_version="",
                            instrumento="x")]
    gp = str(tmp_path / "g.json")
    save_guion(g, gp)
    mapa = _call(srv.guion_map, gp)
    linea = next(l for l in mapa.splitlines() if "m01" in l)
    assert "Q⚠(12,24)" in linea and "Q✓" not in linea


def test_D3_la_conclusion_dice_la_salvedad():
    class D:
        data = {"white_noise": True, "normal": True,
                "q_fails": ["lag 12 (Q=34.90, p=0.0003)"]}
    c = srv._conclusiones_desde(D())
    assert "SALVEDAD" in c and "lag 12" in c
    alts = srv._alternativas_desde(D())
    assert not any("Adoptar este modelo" in a for a in alts)


# ── D4 ───────────────────────────────────────────────────────────────────

def test_D4_los_hallazgos_de_la_diagnosis_van_a_su_version():
    class Diag:
        white_noise = True
        q_lag_cancerbero, q_p_cancerbero = 39, 0.30
        normal, jb_pvalue = False, 0.001
        centred, mean_t = False, -2.4
        seasonal = None
    st = _stats()
    st.extreme = [{"obs": 50, "date": "02/2009", "z": -4.2},
                  {"obs": 9, "date": "09/2005", "z": 3.1}]
    h = hallazgos_de_la_diagnosis(Diag(), st, umbral_z=3.5)
    assert "rechaza en 12 (p=0.0003)" in h
    assert "Jarque-Bera" in h and "media residual" in h
    assert "02/2009" in h and "09/2005" not in h


def test_D4_el_modelo_estimado_lleva_sus_problemas(serie):
    d, inp = serie
    gp = str(d / "d4_guion.json")
    # (0,1,0)(0,1,1): la inflación AR(1) queda sin modelar
    _call(srv.confirm_and_estimate, inp, str(d / "p01.inp"), lam=0, d=1, D=1,
          p=0, q=0, P=0, Q=1, guion_path=gp, guion_name="p01",
          guion_problems="lo que dice el analista")
    pf = _entradas(gp)[-1]["problems_found"]
    assert pf.startswith("lo que dice el analista")
    assert "[diagnosis]" in pf and "rechaza" in pf


def test_D4_anotar_anade_y_no_pisa(tmp_path):
    gp = str(tmp_path / "g.json")
    g = Guion(series="X", analyst="", created="2026-10-06")
    g.entries = [GuionEntry(version=1, name="m01", inp_path="", timestamp="",
                            spec={}, stats=_stats(), equation="", decision="",
                            rationale="", problems_found="r1 = 0,38",
                            next_version="")]
    save_guion(g, gp)
    t = _call(srv.guion_annotate, gp, 1, "problemas", "Q(12) p=0,0003")
    pf = load_guion(gp).entries[0].problems_found
    assert pf.startswith("r1 = 0,38") and "Q(12) p=0,0003" in pf
    assert "Error" not in t
    assert "Error" in _call(srv.guion_annotate, gp, 1, "nada", "x")
    with pytest.raises(ValueError):
        annotate(g, 1, "evidencia", "sólo para nodos")


# ── D5 + D6 ──────────────────────────────────────────────────────────────

def test_D5_D6_padre_declarado_y_adoptar_sin_duplicar(serie):
    d, inp = serie
    gp = str(d / "d5_guion.json")
    kw = dict(lam=0, d=1, D=1, guion_path=gp)
    m02 = str(d / "m02.inp")
    _call(srv.confirm_and_estimate, inp, m02, p=1, q=0, P=0, Q=1,
          guion_name="m02", **kw)
    v02 = _entradas(gp)[-1]["version"]
    _call(srv.confirm_and_estimate, inp, str(d / "m03.inp"), p=1, q=1, P=0,
          Q=1, guion_name="m03", parent=v02, **kw)
    _call(srv.confirm_and_estimate, inp, str(d / "m04.inp"), p=1, q=0, P=1,
          Q=1, guion_name="m04", parent=v02, **kw)
    e04 = _entradas(gp)[-1]
    assert e04["parent"] == v02 and e04["parent_origen"] == "declarado"

    # D6: la vía antigua —reinscribir con decision="adoptado"— adopta la
    # entrada que ya está, sin duplicarla
    n = len(_entradas(gp))
    pre = m02[:-4] + ".pre"
    t = _call(srv.record_version, pre, gp, name="m02 ADOPTADO",
              decision="adoptado", rationale="ruido blanco y parsimonia",
              base_pre_path=pre)
    es = _entradas(gp)
    assert len(es) == n, "adoptar reinscribiendo sigue duplicando"
    e02 = next(e for e in es if e["version"] == v02)
    assert e02["status"] == "adopted"
    assert e02["why_adopted"] == "ruido blanco y parsimonia"
    assert "m03" in t and "m04" in t          # los hermanos que siguen vivos
    mapa = _call(srv.guion_map, gp)
    assert f"✓ v{v02} m02" in mapa


def test_D6_guion_adopt_exige_razon_y_un_modelo_vivo(tmp_path):
    g = Guion(series="X", analyst="", created="2026-10-06")
    mk = lambda v, **k: GuionEntry(version=v, name=f"m{v}", inp_path="",
                                   timestamp="", spec={}, stats=_stats(),
                                   equation="", decision="", rationale="",
                                   problems_found="", next_version="", **k)
    g.entries = [mk(1), mk(2, parent=1, status="dead-end", why_abandoned="no"),
                 GuionEntry(version=3, name="d", inp_path="", timestamp="",
                            spec={}, stats=None, equation="", decision="",
                            rationale="", problems_found="", next_version="",
                            kind="node", parent=1),
                 mk(4, parent=1)]
    with pytest.raises(ValueError):
        adopt(g, 1, "  ")
    with pytest.raises(ValueError):
        adopt(g, 2, "razón")
    with pytest.raises(ValueError):
        adopt(g, 3, "razón")
    assert adopt(g, 1, "el mejor") == [4]
    assert g.entries[0].status == "adopted"
    gp = str(tmp_path / "g.json")
    save_guion(g, gp)
    assert "Error" in _call(srv.guion_adopt, gp, 2, "razón")


# ── D7 ───────────────────────────────────────────────────────────────────

def test_D7_los_nodos_no_disparan_el_aviso_de_instrumento(tmp_path):
    gp = str(tmp_path / "g.json")
    g = Guion(series="X", analyst="", created="2026-10-06")
    nodo = lambda v: GuionEntry(version=v, name="lambda", inp_path="",
                                timestamp="", spec={}, stats=None, equation="",
                                decision="", rationale="r", problems_found="",
                                next_version="", kind="node",
                                node={"nodo": "lambda", "decidido": "0"},
                                parent=v - 1 if v > 1 else None)
    g.entries = [nodo(1), nodo(2),
                 GuionEntry(version=3, name="m01", inp_path="", timestamp="",
                            spec={}, stats=_stats(pv=(.5, .5, .5, .5)),
                            equation="", decision="", rationale="",
                            problems_found="", next_version="", parent=2,
                            instrumento=srv._version_instr())]
    save_guion(g, gp)
    assert "mismo instrumento" not in _call(srv.guion_map, gp)
    # un MODELO sin instrumento sí lo dispara, y sólo él se nombra
    g.entries[2].instrumento = ""
    save_guion(g, gp)
    mapa = _call(srv.guion_map, gp)
    assert "mismo instrumento" in mapa
    assert "sin registrar: v3 " in mapa
