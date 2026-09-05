"""BUG-0092 — la terna del guion quedaba rota, y el mapa apuntaba al vacío.

El convenio hace de cada versión una TERNA con el mismo basename: el `.inp` que
se estimó, el `.pre` con el óptimo y el `.out` con el registro. La entrada del
guion apunta al `.inp`, que es por donde el analista vuelve a un nodo.

`estimate_and_diagnose` escribía `.pre` y `.out` en el basename de `output_path`
y **no el `.inp`**, registrando de todos modos `inp_path=output_path`. Como los
otros dos sí estaban, la carpeta parecía completa. Defecto introducido al cerrar
BUG-0088.
"""
import filecmp
import json
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.pipeline import _RESCALE_FACTOR, _load_fitted, _write_inp

ED = getattr(srv.estimate_and_diagnose, "fn", srv.estimate_and_diagnose)


@pytest.fixture
def fuente(tmp_path):
    rng = np.random.default_rng(3)
    y = np.cumsum(rng.standard_normal(90) * 0.4) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="R92")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
    f = str(tmp_path / "R92.inp")
    _write_inp(ts, m, f)
    return f, str(tmp_path)


def _txt(res):
    return "\n".join(getattr(c, "text", "") for c in res)


# ───────────── la terna ─────────────

def test_la_terna_queda_completa(fuente):
    f, d = fuente
    dst = os.path.join(d, "R92_m00.inp")
    ED(f, dst)
    base = os.path.splitext(dst)[0]
    for ext in (".inp", ".pre", ".out"):
        assert os.path.exists(base + ext), f"falta {ext}"


def test_el_inp_de_la_terna_es_la_ESPECIFICACION(fuente):
    """Byte a byte del fuente. Reserializar el modelo AJUSTADO escribiría las
    estimaciones donde van las semillas — la trampa de BUG-0027 dentro de un
    `.inp`, que ya se pisó una vez en esta misma sesión."""
    f, d = fuente
    dst = os.path.join(d, "R92_m00.inp")
    ED(f, dst)
    assert filecmp.cmp(f, dst, shallow=False)


def test_reestimar_el_inp_copiado_da_SE_validas(fuente):
    """La consecuencia de lo anterior: si la copia llevara estimaciones, la
    siguiente estimación arrancaría en el óptimo y la covarianza se quedaría en
    la semilla (BUG-0090)."""
    from art.pipeline import viene_de_pre
    f, d = fuente
    dst = os.path.join(d, "R92_m00.inp")
    ED(f, dst)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        _, m = _load_fitted(dst)
    assert not viene_de_pre(m)


def test_si_output_es_el_mismo_fichero_no_se_copia_nada(fuente):
    f, d = fuente
    antes = sorted(os.listdir(d))
    ED(f, f)
    assert os.path.exists(f)
    assert os.path.exists(os.path.splitext(f)[0] + ".pre")


def test_no_se_pisa_un_inp_existente_con_otro_contenido(fuente, tmp_path):
    """Un `.pre` o un `.out` se rehacen estimando; una especificación perdida
    no se recupera."""
    f, d = fuente
    otro = os.path.join(d, "OTRO.inp")
    with open(f) as fh:
        contenido = fh.read()
    with open(otro, "w") as fh:
        fh.write(contenido.replace("R92", "DISTINTO"))
    t = _txt(ED(f, otro))
    with open(otro) as fh:
        assert "DISTINTO" in fh.read(), "se pisó una especificación ajena"
    assert "ya existe con otro" in t


# ───────────── el guion comprueba lo que registra ─────────────

def test_el_inp_registrado_resuelve(fuente):
    f, d = fuente
    ED(f, os.path.join(d, "R92_m00.inp"))
    g = [x for x in os.listdir(d) if x.endswith("guion.json")][0]
    e = json.load(open(os.path.join(d, g)))["entries"][0]
    assert os.path.exists(e["inp_path"])


def test_registrar_una_ruta_ausente_se_dice(fuente):
    """Medido sobre el corpus real: 4 de 15 entradas apuntaban al vacío y el
    guion no lo decía. Registrar mal es mejor que no registrar, pero callarlo
    rompe la operación que el guion existe para sostener."""
    f, d = fuente
    _, m = _load_fitted(f)
    nota = srv._record_to_guion(
        model=m, inp_path=os.path.join(d, "no_existe.inp"), lam=0.0,
        guion_path=os.path.join(d, "aviso.json"), name="x")
    assert "no existe" in nota
    assert "no se puede reestimar" in nota


def test_una_terna_sin_pre_se_menciona_pero_sin_alarma(fuente):
    """Un `.pre` o un `.out` que faltan se rehacen estimando el `.inp`: es una
    nota, no un aviso."""
    f, d = fuente
    _, m = _load_fitted(f)
    nota = srv._record_to_guion(
        model=m, inp_path=f, lam=0.0,
        guion_path=os.path.join(d, "aviso2.json"), name="y")
    assert "⚠" not in nota
    assert ".pre" in nota or ".out" in nota


def test_una_terna_completa_no_añade_ruido(fuente):
    f, d = fuente
    dst = os.path.join(d, "R92_m00.inp")
    ED(f, dst)
    g = [x for x in os.listdir(d) if x.endswith("guion.json")][0]
    _, m = _load_fitted(dst)
    nota = srv._record_to_guion(
        model=m, inp_path=dst, lam=0.0,
        guion_path=os.path.join(d, "aviso3.json"), name="z")
    assert "⚠" not in nota and "sin ." not in nota
