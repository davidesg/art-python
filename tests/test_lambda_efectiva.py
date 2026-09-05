"""La λ que se registra es la del MODELO, no la del argumento.

Hallazgo #1 de la revisión con contexto limpio. `_record_to_guion` se llama
desde seis sitios: cinco leían la λ del modelo ajustado y uno registraba el
argumento de la herramienta — `confirm_and_estimate`, que es **la puerta
principal del carril guiado**.

Y el daño se activa justo en el camino que las propias instrucciones de art
mandan usar por defecto: *«ENCADENA SIEMPRE por `base_pre_path` cuando ya existe
un `.pre`»*. Con `base_pre_path`, `lam` **se ignora** para construir el modelo
—la transformación viene del `.pre`— pero se mostraba y se registraba desde el
argumento, cuyo valor por defecto es `0.0`.

Resultado: un modelo en NIVELES quedaba en el guion como λ=0 y su ecuación se
imprimía como ∇[ln y]. Un registro falso, en el camino recomendado.
"""
import json
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.pipeline import _RESCALE_FACTOR, _load_ts_model, _write_inp

CE = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)


@pytest.fixture
def encadenado(tmp_path):
    """Un modelo en NIVELES (λ=1) y otro encadenado desde su `.pre` sin declarar
    λ — el caso exacto que producía el registro falso."""
    rng = np.random.default_rng(9)
    y = np.cumsum(rng.standard_normal(100) * 0.4) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1999, 1), name="L")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
    base = str(tmp_path / "L.inp")
    _write_inp(ts, m, base)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        CE(base, str(tmp_path / "A.inp"), lam=1.0, d=1, D=0, p=1, q=0,
           n_harmonics=0, guion_decision="niveles")
        txt = " ".join(getattr(c, "text", "") for c in CE(
            base, str(tmp_path / "B.inp"), d=1, D=0, p=2, q=0, n_harmonics=0,
            base_pre_path=str(tmp_path / "A.pre"), guion_decision="encadenado"))
    g = [x for x in os.listdir(str(tmp_path)) if x.endswith("guion.json")][0]
    return json.load(open(str(tmp_path / g)))["entries"], txt, str(tmp_path)


def test_el_guion_registra_la_lambda_del_modelo(encadenado):
    entries, _, _ = encadenado
    for e in entries:
        _, m = _load_ts_model(e["inp_path"])
        assert e["spec"]["lam"] == m.boxlam, (
            f"{e['name']}: guion λ={e['spec']['lam']} y motor λ={m.boxlam}")


def test_al_encadenar_NO_se_hereda_el_defecto_del_argumento(encadenado):
    """El caso concreto: se encadena sin declarar λ, el `.pre` es de niveles, y
    el guion tiene que decir 1.0 y no el 0.0 del defecto."""
    entries, _, _ = encadenado
    assert entries[-1]["spec"]["lam"] == 1.0


def test_la_linea_de_spec_muestra_la_misma(encadenado):
    """Guion y pantalla tienen que contar la misma historia: la salida declaraba
    λ dos veces y de dos maneras opuestas en la misma respuesta."""
    _, txt, _ = encadenado
    linea = next(l for l in txt.split("\n") if "λ=" in l and "ARIMA" in l)
    assert "λ=1.0" in linea


def test_la_ecuacion_no_dice_log_sobre_un_modelo_en_niveles(encadenado):
    _, txt, _ = encadenado
    assert "∇[ln" not in txt or "∇[y" in txt


def test_los_seis_llamantes_leen_la_lambda_del_modelo():
    """La quinta duplicación de concepto de la sesión: seis sitios registran λ y
    uno la tomaba de otro sitio. Un concepto, una fuente."""
    import ast
    import pathlib

    src = pathlib.Path("src/art/mcp_server.py").read_text()
    lin = src.split("\n")
    malos = []
    for n in ast.walk(ast.parse(src)):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "_record_to_guion"):
            continue
        for k in n.keywords:
            if k.arg != "lam":
                continue
            txt = "\n".join(lin[k.value.lineno - 1:k.value.end_lineno])
            # `lam=lam` sólo vale si `lam` se ha rebindado desde el modelo
            if "boxlam" not in txt and "lam_fit" not in txt:
                fn = next((f.name for f in ast.walk(ast.parse(src))
                           if isinstance(f, ast.FunctionDef)
                           and f.lineno <= n.lineno <= f.end_lineno), "?")
                cuerpo = "\n".join(lin[
                    next(f for f in ast.walk(ast.parse(src))
                         if isinstance(f, ast.FunctionDef)
                         and f.name == fn).lineno - 1:n.lineno])
                if "boxlam" not in cuerpo and "result.lam" not in cuerpo:
                    malos.append(f"{fn}:{n.lineno}")
    assert not malos, f"registran λ sin leerla del modelo: {malos}"
