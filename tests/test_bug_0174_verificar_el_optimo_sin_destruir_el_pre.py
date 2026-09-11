"""BUG-0174 — verificar el óptimo perturbando POCO, no poniendo las semillas a 0.

En el run 4 —hecho sin contexto— el asistente detectó bien el problema y propuso
una maniobra peligrosa: reestimar «desde semillas neutras (armónicos/Easter/μ=0,
φ=0.1, testigos MA_f=−0.5)» para sacar las SE de la semilla del BFGS.

**El diagnóstico era correcto.** Sobre `m06` (n=216) la semilla es √(2/n)=0,09645
y cinco de los doce errores típicos estaban a menos del 5 % de ella.

**Y la maniobra funcionó — sin que nadie lo comprobara**: ℓ coincidió a 1,3e-09.
Ése es el problema. Con las semillas a 0 el optimizador arranca FUERA de la
cuenca y puede caer en otra; y si eso se vuelve práctica, destruye el convenio del
`.pre` —la cadena `.inp → .pre → .inp` sólo significa algo si cada eslabón
arranca donde acabó el anterior—.

La alternativa: perturbar **una desviación típica** —lejos para que el optimizador
trabaje, cerca para no cambiar de cuenca— y **comparar ℓ**.
"""
import math
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar, reestima_en_frio


@pytest.fixture(scope="module")
def pre_en_caliente(tmp_path_factory):
    """Un modelo estimado y luego ENCADENADO desde su propio óptimo — que es lo
    que deja la covarianza en la semilla."""
    d = tmp_path_factory.mktemp("frio")
    rng = np.random.default_rng(9)
    n = 216
    e = rng.standard_normal(n) * 0.4
    for t in range(1, n):
        e[t] += 0.45 * e[t - 1]
    ts = fue.TimeSeries((100.0 + np.cumsum(e + 0.12)).tolist(), freq=12,
                        start=(2002, 1), name="FRIO")
    itvs = []
    for k in (1, 2):
        itvs.append(fue.Intervention("cos", at=0, omega=[0.0], omega_free=[True],
                                     harmonic=float(k)))
        itvs.append(fue.Intervention("sin", at=0, omega=[0.0], omega_free=[True],
                                     harmonic=float(k)))
    f = str(d / "F_m00.inp")
    _write_inp(ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=True,
                             refactor=_RESCALE_FACTOR, ar=[[0.0]],
                             ar_free=[[True]], interventions=itvs), f)
    _, fit = estimar(f)
    fit.write_pre(f[:-4] + ".pre")
    return str(d), f[:-4] + ".pre"


# ── lo que tiene que hacer ─────────────────────────────────────────────────

def test_verifica_el_optimo_y_saca_las_SE_de_la_semilla(pre_en_caliente):
    d, pre = pre_en_caliente
    m, inf = reestima_en_frio(pre, os.path.join(d, "v.inp"))
    assert inf["veredicto"] == "verificado", inf
    assert abs(inf["delta"]) <= inf["tol"]
    assert inf["niter_frio"] > inf["niter_pre"], (
        "no ha hecho trabajar al optimizador: la covarianza seguirá siendo la semilla")
    assert inf["en_la_semilla_despues"] <= inf["en_la_semilla_antes"]


def test_NO_pone_las_semillas_a_cero(pre_en_caliente):
    """El punto entero del defecto. La perturbación se mide en desviaciones
    típicas desde el óptimo, no desde el origen."""
    import fue as _f
    d, pre = pre_en_caliente
    _, m0 = _f.load(pre)
    m, inf = reestima_en_frio(pre, os.path.join(d, "c.inp"))
    # el punto de partida perturbado sigue estando CERCA del óptimo
    _, mc = _f.load(os.path.join(d, "c.inp"))
    a = float(m0.ar[0][0])
    b = float(mc.ar[0][0])
    assert abs(b) > 0.05, "el AR salió del orden de magnitud del óptimo"
    assert abs(b - a) < 0.5 * max(abs(a), 0.1), "se ha ido de la cuenca"


def test_la_perturbacion_es_DETERMINISTA(pre_en_caliente):
    """Un instrumento de verificación que no se puede repetir no verifica."""
    d, pre = pre_en_caliente
    _, i1 = reestima_en_frio(pre, os.path.join(d, "d1.inp"))
    _, i2 = reestima_en_frio(pre, os.path.join(d, "d2.inp"))
    assert i1["loglik_frio"] == i2["loglik_frio"]
    assert i1["niter_frio"] == i2["niter_frio"]


def test_el_inp_escrito_se_puede_reestimar(pre_en_caliente):
    d, pre = pre_en_caliente
    out = os.path.join(d, "r.inp")
    reestima_en_frio(pre, out)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, m2 = estimar(out)
    assert m2._result is not None


# ── las tres ramas del veredicto ───────────────────────────────────────────

def test_una_tolerancia_imposible_NO_da_verificado(pre_en_caliente):
    """La rama que importa: si ℓ se mueve más de lo tolerado, NO se autoriza a
    usar las SE. Se prueba apretando la tolerancia porque construir una
    verosimilitud multimodal a demanda es otra investigación — lo que aquí hay
    que garantizar es que el veredicto DEPENDE de Δℓ y no es decorativo."""
    d, pre = pre_en_caliente
    _, inf = reestima_en_frio(pre, os.path.join(d, "t.inp"), tol=1e-30)
    assert inf["veredicto"] != "verificado"
    assert inf["veredicto"] in ("mejora", "no_llego")


def test_el_veredicto_distingue_MEJORA_de_NO_LLEGO(pre_en_caliente):
    """No son lo mismo y no se arreglan igual: ℓ que sube dice que el `.pre` no
    era el óptimo; ℓ que baja dice que la corrida en frío no alcanzó."""
    d, pre = pre_en_caliente
    _, inf = reestima_en_frio(pre, os.path.join(d, "s.inp"), tol=1e-30)
    esperado = "mejora" if inf["delta"] > 0 else "no_llego"
    assert inf["veredicto"] == esperado


# ── por la superficie ──────────────────────────────────────────────────────

def test_la_herramienta_AVISA_de_no_poner_las_semillas_a_cero():
    """Es el consejo que el run 4 se dio a sí mismo. Tiene que estar donde el
    modelo lo lee, no sólo en un informe."""
    import asyncio

    import art.mcp_server as srv
    from tests._texto import dice
    ts = asyncio.run(srv.mcp.list_tools())
    t = next((x for x in ts if x.name == "verify_optimum"), None)
    assert t is not None, "la herramienta no está publicada"
    d = t.description or ""
    assert dice(d, "NO pongas las semillas a cero")
    assert dice(d, "destruye el convenio del `.pre`")
    assert dice(d, "fuera de la cuenca")


def test_la_salida_publica_las_TRES_columnas_que_deciden(pre_en_caliente):
    import warnings

    import art.mcp_server as srv
    d, pre = pre_en_caliente
    fn = getattr(srv.verify_optimum, "fn", srv.verify_optimum)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        txt = "\n".join(getattr(x, "text", "")
                        for x in fn(pre, os.path.join(d, "mcp.inp")))
    assert "Mismo óptimo" in txt
    assert "iteraciones" in txt and "SE en la semilla del BFGS" in txt
    assert "Δℓ" in txt


# ── el caso real del run 4 ─────────────────────────────────────────────────

_RUN4 = os.path.expanduser("~/Dropbox/run4/cases/IPC_ES/work/IPC_ES_m06.pre")


@pytest.mark.skipif(not os.path.exists(_RUN4), reason="falta el run 4")
def test_sobre_el_caso_del_run4(tmp_path):
    """m06: cinco SE en la semilla √(2/216)=0,09645, y la maniobra de cero
    acertó sin comprobarlo."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m, inf = reestima_en_frio(_RUN4, str(tmp_path / "m06f.inp"))
    assert inf["veredicto"] == "verificado"
    assert abs(inf["delta"]) < 1e-5
    assert inf["en_la_semilla_antes"] >= 3
    assert inf["en_la_semilla_despues"] == 0
