"""Los cinco defectos de la revisión del 2026-09-06, y el choque de números.

BUG-0104 · 0105 · 0106 · 0107 · 0109. El 0103 —el hueco de diseño de la
factorización— queda fuera: no es un defecto sino una superficie que falta.
"""
import math
import os
import re
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.describe import model_equation
from art.guion import (Guion, GuionEntry, GuionStats, export_guion_html)
from art.mcp_server import (_alternativas_desde, _conclusiones_desde,
                            _reformulacion_desde, umbral_extremo)
from art.outfile import lee_out
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar


class _Diag:
    def __init__(self, **kw):
        self.data = kw


# ══════ BUG-0106 — la reformulación era ciega a la Q y al JB ══════

def test_la_reformulacion_ve_la_Q_y_el_JB():
    """Leía `q_pass`/`jb_pass` y la diagnosis publica `white_noise`/`normal`.
    `d.get("q_pass")` daba None, `None is False` es False, y la rama de fallo
    NO SE EJECUTABA NUNCA: sobre un modelo con los dos contrastes rechazando,
    la etapa 4 del carril autónomo decía «no procede reformular»."""
    r = _reformulacion_desde(_Diag(white_noise=False, normal=True, n_extreme=0,
                                   nobs=200))
    assert r and "NO se sostiene" in r
    r2 = _reformulacion_desde(_Diag(white_noise=True, normal=False, n_extreme=0,
                                    nobs=200))
    assert r2 and "NO se sostiene" in r2


def test_la_reformulacion_calla_cuando_el_modelo_se_sostiene():
    assert _reformulacion_desde(_Diag(white_noise=True, normal=True,
                                      n_extreme=0, nobs=200)) == ""


def test_una_sola_lectura_de_la_diagnosis():
    """Dos funciones consultando el mismo dict con nombres distintos es
    exactamente cómo se llegó al defecto. `_reformulacion_desde` delega."""
    from tests._fuente import fuente_de
    # Sin los comentarios: el que EXPLICA el defecto nombra las claves viejas,
    # y una prueba que busca en el fichero entero se dispara con su propia
    # explicación. Ha pasado cinco veces en este repositorio.
    src = "\n".join(l.split("#", 1)[0]
                    for l in fuente_de(_reformulacion_desde).splitlines())
    assert "q_pass" not in src and "jb_pass" not in src
    assert "_conclusiones_desde(" in src


# ══════ BUG-0105 — un |z|>3 no es un fallo de adecuación ══════

def test_el_caso_del_informe_ya_no_se_contradice():
    """«Veredicto APROBADO ✓ · Q ✓ · JB ✓» y diez líneas después «El modelo NO
    se sostiene: queda 1 residuo extremo»."""
    c = _conclusiones_desde(_Diag(white_noise=True, normal=True, n_extreme=1,
                                  nobs=215))
    assert "se sostiene" in c and "NO se sostiene" not in c


def test_el_anomalo_se_menciona_calibrado_por_n():
    """El dato no se tira: se pone donde informa, y con su calibración."""
    c = _conclusiones_desde(_Diag(white_noise=True, normal=True, n_extreme=1,
                                  nobs=215))
    assert "n=215" in c and "3.49" in c
    assert "no es un fallo" in c.lower()


def test_con_el_JB_rechazando_el_anomalo_SI_informa():
    c = _conclusiones_desde(_Diag(white_noise=True, normal=False, n_extreme=2,
                                  nobs=215))
    assert "no-normalidad" in c
    assert "BUG-0043" in c, "un JB que falla sin anómalos apunta a λ"


@pytest.mark.parametrize("n,c", [(100, 3.28), (215, 3.49), (500, 3.71)])
def test_el_umbral_crece_con_n(n, c):
    """Bajo especificación correcta el máximo de n normales crece con n. Con
    n=500 y umbral 3 fijo, tres de cada cuatro modelos correctos tendrían un
    «residuo extremo»."""
    assert abs(umbral_extremo(n) - c) < 0.02


def test_no_se_ofrece_intervenir_un_anomalo_esperable():
    """Ofrecerlo como opción A sobre un modelo aprobado es invitar a
    sobre-intervenir."""
    alts = _alternativas_desde(_Diag(
        white_noise=True, normal=True, n_extreme=1, nobs=215,
        intervention_hints=[{"obs": 12, "z": 3.08, "form": "pulse"}]))
    assert not any("Intervenir" in a for a in alts)
    assert any("Adoptar" in a for a in alts)


def test_pero_uno_que_SUPERA_el_umbral_calibrado_si():
    alts = _alternativas_desde(_Diag(
        white_noise=True, normal=True, n_extreme=1, nobs=215,
        intervention_hints=[{"obs": 12, "z": 5.9, "form": "step"}]))
    assert any("Intervenir" in a for a in alts)


def test_y_con_algo_fallando_tambien():
    """Si la Q rechaza, el anómalo vuelve a ser lo más obvio primero."""
    alts = _alternativas_desde(_Diag(
        white_noise=False, normal=True, n_extreme=1, nobs=215,
        q_fails=["lag 2"],
        intervention_hints=[{"obs": 12, "z": 3.08, "form": "pulse"}]))
    assert any("Intervenir" in a for a in alts)


def test_la_diagnosis_publica_nobs():
    """Sin n, «1 residuo |z|>3» no se puede juzgar."""
    rng = np.random.default_rng(11)
    y = np.cumsum(rng.standard_normal(150) * 0.4) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2005, 1), name="N")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=True, refactor=_RESCALE_FACTOR)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit()
    from art.describe import describe_diagnosis
    assert (describe_diagnosis(m).data or {}).get("nobs") == 150


# ══════ BUG-0104 — el φ₁ derivado se imprimía como 1 ══════

def test_el_phi1_derivado_sale_con_su_valor(tmp_path):
    """Un factor de frecuencia fija es (1 − φ₁B − φ₂B²) con φ₂ ESTIMADO y
    φ₁ = 2·cos(2πf/s)·√(−φ₂) DERIVADO. El render ponía sólo el 2·cos —que en
    s=12 vale 1 para f=2 y f=4— y se comía el √(−φ₂)."""
    rng = np.random.default_rng(8)
    n = 240
    t = np.arange(n)
    y = (100 + np.cumsum(rng.standard_normal(n) * 0.2)
         + 1.5 * np.cos(2 * np.pi * 4 * t / 12))
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2005, 1), name="F")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                  ar_f=[fue.FixedFreqFactor(freq=4, coef=-0.5, free=True)],
                  refactor=_RESCALE_FACTOR)
    f = str(tmp_path / "F.inp")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _write_inp(ts, m, f)
        ts2, m2 = estimar(f)
    ff = m2.ar_f[0]
    phi1 = 2 * math.cos(2 * math.pi * ff.freq / 12) * math.sqrt(abs(ff.coef))
    r = model_equation(ts2, m2)
    txt = r.summary if hasattr(r, "summary") else str(r)
    assert f"{abs(phi1):.4f}" in txt, f"φ₁={phi1} no está en la ecuación"


def test_f3_en_mensual_no_tiene_termino_en_B():
    """2·cos(2π·3/12) = 0: el factor es (1 + c·B²) y no hay término en B."""
    from tests._fuente import fuente_de
    from art.describe import model_equation as _me
    src = fuente_de(_me)
    assert "abs(tc_val) < 1e-9" in src


# ══════ BUG-0107 — el export moría con un nodo ══════

def _guion_con_nodo():
    g = Guion(series="S", analyst="", created="2026-01-01")
    g.entries.append(GuionEntry(
        version=1, name="lambda", inp_path="", timestamp="t", spec={},
        stats=None, equation="", decision="λ=0", rationale="serie en tasas",
        problems_found="", next_version="", kind="node",
        node={"nodo": "lambda", "decidido": "0", "evidencia": "Box-Cox p=0.31",
              "alternativas": "λ=1 descartada"}, decided_by="analista+LLM"))
    g.entries.append(GuionEntry(
        version=2, name="m00", inp_path="", timestamp="t", spec={"d": 1},
        stats=GuionStats(loglik=-10.0, aic=20.0, bic=25.0, sigma_a=0.1,
                         q_pass=True, jb_pass=True, n_extreme=0),
        equation="∇ln y = a", decision="", rationale="", problems_found="",
        next_version=""))
    return g


def test_el_export_sobrevive_a_un_nodo():
    """Bastaba UN nodo de decisión para que el informe navegable muriera con
    AttributeError y no produjera fichero alguno."""
    assert len(export_guion_html(_guion_con_nodo())) > 0


def test_el_nodo_no_se_omite_sino_que_se_dibuja():
    """Omitirlo sería peor: los nodos son la mitad que explica POR QUÉ."""
    h = export_guion_html(_guion_con_nodo())
    assert "nodo de decisión" in h
    assert "Box-Cox p=0.31" in h and "λ=1 descartada" in h
    assert "analista+LLM" in h


def test_y_el_modelo_sigue_saliendo_entero():
    h = export_guion_html(_guion_con_nodo())
    assert "m00" in h and "20.0" in h


# ══════ BUG-0109 — registrar antes de persistir ══════

def test_se_persiste_antes_de_registrar():
    """La comprobación de la terna mira si el `.pre` y el `.out` EXISTEN al
    registrar. Registrando primero, la entrada los daba por ausentes aunque
    acabaran en disco un instante después — y el analista encadenaba desde un
    `.pre` más antiguo, perdiendo la intervención."""
    src = open("src/art/mcp_server.py", encoding="utf-8").read().splitlines()

    def cuerpo(nombre):
        ini = next(i for i, l in enumerate(src)
                   if re.match(rf"^(async )?def {nombre}\(", l))
        fin = next((i for i in range(ini + 1, len(src))
                    if re.match(r"^(async )?def |^@mcp\.tool", src[i])), len(src))
        return src[ini:fin]

    for nombre in ("suggest_intervention_form", "confirm_and_estimate"):
        c = cuerpo(nombre)
        reg = next(i for i, l in enumerate(c) if "_record_to_guion(" in l)
        pre = next(i for i, l in enumerate(c)
                   if ".write_pre(" in l or "_persist_pre_out" in l)
        assert pre < reg, f"{nombre} registra antes de persistir"


def test_el_defecto_esta_documentado():
    assert os.path.exists("bugs/BUG-0109-repro/repro.py")


# ══════ El choque de identificadores ══════

def test_ningun_identificador_de_bug_esta_repetido():
    """Hubo dos BUG-0102 el mismo día y se comitearon juntos sin que nada
    avisara. Peor: sus carpetas de repro se llamaban igual y una pisó a la otra,
    perdiendo un repro."""
    import collections
    ids = collections.Counter()
    for f in sorted(os.listdir("bugs")):
        if not f.startswith("BUG-") or not f.endswith(".md"):
            continue
        for l in open(os.path.join("bugs", f), encoding="utf-8"):
            if l.startswith("id:"):
                ids[l.split(":", 1)[1].strip()] += 1
                break
    repes = {k: v for k, v in ids.items() if v > 1}
    assert not repes, f"identificadores repetidos: {repes}"


def test_cada_carpeta_de_repro_tiene_su_informe():
    """Una carpeta `BUG-NNNN-repro` sin informe `BUG-NNNN` es lo que queda
    cuando dos informes con el mismo número se pisan la carpeta: el repro
    sobrevive huérfano y el otro desaparece.

    NO se comprueba que un informe cite sólo su propio repro: citar el de otro
    es legítimo y frecuente —BUG-0011 cita el de BUG-0010 porque comparten
    causa—."""
    informes = set()
    for f in os.listdir("bugs"):
        if f.startswith("BUG-") and f.endswith(".md"):
            for l in open(os.path.join("bugs", f), encoding="utf-8"):
                if l.startswith("id:"):
                    informes.add(l.split(":", 1)[1].strip())
                    break
    huerfanas = [d for d in os.listdir("bugs")
                 if d.endswith("-repro") and d[:8] not in informes]
    assert not huerfanas, f"repros sin informe: {huerfanas}"


# ══════ BUG-0108 — el padre inventado, y la cascada que lo cree ══════

def test_estimate_and_diagnose_acepta_declarar_el_linaje():
    """No tenía ningún parámetro para decirlo, así que anotaba como padre la
    ÚLTIMA entrada del guion — que no tiene por qué ser el modelo del que sale
    el `.inp`."""
    from tests._fuente import fuente_de
    ed = getattr(srv.estimate_and_diagnose, "fn", srv.estimate_and_diagnose)
    src = fuente_de(ed)
    assert "base_pre_path: str" in src
    assert "base_pre_path=base_pre_path" in src


def test_se_registra_COMO_se_supo_el_padre():
    """Un padre inferido y uno declarado no valen lo mismo, y el registro no
    los distinguía: el mapa parecía igual de firme en los dos casos."""
    from art.guion import GuionEntry
    e = GuionEntry(version=1, name="a", inp_path="", timestamp="t", spec={},
                   stats=None, equation="", decision="", rationale="",
                   problems_found="", next_version="")
    assert e.parent_origen == ""
    from tests._fuente import fuente_de
    src = fuente_de(srv._record_to_guion)
    assert '"declarado" if base_pre_path else "inferido"' in src
    assert "parent_origen=parent_origen" in src


def _guion_linaje(tmp_path, origen_v3):
    from art.guion import Guion, GuionEntry, GuionStats, save_guion

    def E(v, n, padre, origen):
        return GuionEntry(
            version=v, name=n, inp_path="", timestamp="t", spec={},
            stats=GuionStats(loglik=-1.0, aic=1.0, bic=2.0, sigma_a=0.1,
                             q_pass=True, jb_pass=True, n_extreme=0),
            equation="", decision="", rationale="", problems_found="",
            next_version="", parent=padre, parent_origen=origen)

    g = Guion(series="S", analyst="", created="2026-01-01")
    g.entries += [E(1, "m00", None, "declarado"), E(2, "m01", 1, "declarado"),
                  E(3, "m02", 2, origen_v3), E(4, "m03", 3, "declarado")]
    gp = str(tmp_path / "S_guion.json")
    save_guion(g, gp)
    return gp


def test_la_cascada_avisa_si_el_parentesco_es_INFERIDO(tmp_path):
    """`guion_abandon` arrastra descendientes POR DISEÑO, y eso sólo es correcto
    si el parentesco es cierto. Sobre un linaje inventado, marcar un callejón
    correcto barre la rama viva — y hubo que descubrirlo a mano."""
    gp = _guion_linaje(tmp_path, "inferido")
    ga = getattr(srv.guion_abandon, "fn", srv.guion_abandon)
    t = ga(gp, 2, why="LR rechaza")[0].text
    assert "parentesco INFERIDO" in t
    assert "v3 (m02)" in t
    assert "cascade=False" in t


def test_y_calla_cuando_todo_el_linaje_es_declarado(tmp_path):
    gp = _guion_linaje(tmp_path, "declarado")
    ga = getattr(srv.guion_abandon, "fn", srv.guion_abandon)
    assert "parentesco INFERIDO" not in ga(gp, 2, why="LR rechaza")[0].text


def test_sin_cascada_no_hay_nada_de_que_avisar(tmp_path):
    gp = _guion_linaje(tmp_path, "inferido")
    ga = getattr(srv.guion_abandon, "fn", srv.guion_abandon)
    t = ga(gp, 2, why="LR rechaza", cascade=False)[0].text
    assert "parentesco INFERIDO" not in t


def test_nadie_lee_del_dict_de_diagnosis_una_clave_que_no_existe():
    """La guarda que cierra la CLASE de BUG-0106.

    La causa de fondo son dos vocabularios para los mismos dos hechos:

        el dict de diagnosis   "white_noise"  "normal"
        GuionStats             `q_pass`       `jb_pass`

    Los dos son legítimos en su sitio, y por eso nadie los unificó. Pero el que
    lee el dict escribiendo `q_pass` no obtiene un error: obtiene `None`, que
    pasa silenciosamente todas las comparaciones `is False`. El defecto no se
    manifiesta como fallo sino como una rama que nunca se ejecuta.

    Esto comprueba que todo lo que consulta `d.get(...)` sobre la diagnosis usa
    claves que `describe_diagnosis` realmente escribe.
    """
    import ast

    escritas = set()
    arbol = ast.parse(open("src/art/describe.py", encoding="utf-8").read())
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Dict):
            claves = [k.value for k in nodo.keys
                      if isinstance(k, ast.Constant) and isinstance(k.value, str)]
            if "white_noise" in claves and "normal" in claves:
                escritas.update(claves)
    assert "white_noise" in escritas, "no se encontró el dict de la diagnosis"

    # Las funciones de mcp_server que consumen ese dict.
    fuente = open("src/art/mcp_server.py", encoding="utf-8").read()
    sospechosas = set()
    for nombre in ("_conclusiones_desde", "_alternativas_desde",
                   "_reformulacion_desde"):
        i = fuente.index(f"def {nombre}(")
        j = fuente.find("\ndef ", i + 1)
        cuerpo = fuente[i:j if j > 0 else len(fuente)]
        cuerpo = "\n".join(l.split("#", 1)[0] for l in cuerpo.splitlines())
        for m in re.findall(r'd\.get\(\s*"([a-z_]+)"', cuerpo):
            if m not in escritas:
                sospechosas.add(f"{nombre}: d.get(\"{m}\")")
    assert not sospechosas, (
        f"leen claves que la diagnosis NO escribe: {sorted(sospechosas)}. "
        f"Devuelven None, que pasa en silencio toda comparación `is False`.")
