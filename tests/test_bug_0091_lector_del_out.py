"""BUG-0091 — `get_out_report` no leía el `.out`, y nada en art podía leerlo.

El `.out` es la ÚNICA constancia fiel de las desviaciones típicas: la covarianza
no es una propiedad del óptimo sino un subproducto del camino del optimizador
(BUG-0090), así que un fichero que sólo guarda el óptimo —el `.pre`— no puede
llevarla.

art lo sabía —`AVISO_COV_CASI_SEMILLA` le dice al analista «el `.out` del modelo
trae la covarianza completa»— y no tenía con qué leerlo: la instrucción existía y
no era ejecutable. Y la herramienta que debía darlo lo REESTIMABA, con lo que un
`.pre` producía un informe 247% desviado del fichero de al lado.
"""
import math
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.outfile import LecturaOut, hay_out, lee_out
from art.pipeline import _RESCALE_FACTOR, _load_fitted, _write_inp

GOR = getattr(srv.get_out_report, "fn", srv.get_out_report)


@pytest.fixture(scope="module")
def terna(tmp_path_factory):
    """Una terna completa: `.inp`, `.pre`, `.out`."""
    d = tmp_path_factory.mktemp("b91")
    rng = np.random.default_rng(11)
    y = np.cumsum(rng.standard_normal(140) * 0.4) + 100.0
    y[70:] += 5.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1990, 1), name="R91")
    itv = fue.Intervention("step", at=70, omega=[0.0], omega_free=[True])
    m = fue.Model(ts, d=1, ar=[[0.0]], ar_free=[[True]], mu=0.0,
                  estimate_mu=False, interventions=[itv],
                  refactor=_RESCALE_FACTOR)
    f_inp = str(d / "R91.inp")
    _write_inp(ts, m, f_inp)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, fit = _load_fitted(f_inp)
    f_pre, f_out = str(d / "R91.pre"), str(d / "R91.out")
    fit.write_pre(f_pre)
    fit.write_out(f_out)
    return f_inp, f_pre, f_out, str(d)


def _txt(p):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return "\n".join(getattr(c, "text", "") for c in GOR(p))


# ───────────── el lector ─────────────

def test_lee_los_parametros_con_su_error_tipico(terna):
    _, _, f_out, _ = terna
    r = lee_out(f_out)
    assert r.parametros
    assert all(p.se > 0 for p in r.parametros)
    assert r.npar == len(r.parametros)


def test_las_SE_cuadran_con_la_covarianza(terna):
    """Las dos vías del mismo fichero tienen que coincidir, o una está mal
    leída."""
    _, _, f_out, _ = terna
    r = lee_out(f_out)
    assert r.covarianza
    for i, p in enumerate(r.parametros):
        assert abs(math.sqrt(r.covarianza[i][i]) - p.se) < 1e-6


def test_lee_el_ajuste_y_la_especificacion(terna):
    _, _, f_out, _ = terna
    r = lee_out(f_out)
    assert r.loglik is not None
    assert r.sigma2 is not None and r.sigma2 > 0
    assert r.nobs and r.d is not None and r.freq


def test_la_etiqueta_no_se_cuela_como_numero(terna):
    """`sigma2:` daba 2.0 —el dígito de la etiqueta— buscando el número en la
    línea entera. Las etiquetas del `.out` llevan número, así que hay que
    cortar por los dos puntos."""
    _, _, f_out, _ = terna
    r = lee_out(f_out)
    assert r.sigma2 != 2.0
    assert abs(r.sigma2 - (r.sigma or 0) ** 2) < 1e-6


def test_lee_las_estadisticas_de_los_residuos(terna):
    _, _, f_out, _ = terna
    r = lee_out(f_out)
    assert r.residuos.jarque_bera is not None
    assert r.residuos.desv_tipica is not None
    assert r.residuos.maximo and len(r.residuos.maximo) == 3


def test_encuentra_el_out_por_cualquier_hermano(terna):
    """La terna comparte basename: exigir la extensión exacta trasladaría al
    llamante una regla que este módulo ya conoce."""
    f_inp, f_pre, f_out, _ = terna
    assert lee_out(f_inp).ruta == f_out
    assert lee_out(f_pre).ruta == f_out
    assert hay_out(f_inp) and hay_out(f_pre)


def test_un_out_truncado_no_revienta(terna, tmp_path):
    """Lectura defensiva: una sección ausente es None, no una excepción."""
    _, _, f_out, _ = terna
    corto = tmp_path / "corto.out"
    corto.write_text("\n".join(open(f_out).read().split("\n")[:20]))
    r = lee_out(str(corto))
    assert isinstance(r, LecturaOut)
    assert not r.completo


def test_un_out_que_no_existe_levanta(tmp_path):
    with pytest.raises(FileNotFoundError):
        lee_out(str(tmp_path / "nada.inp"))
    assert not hay_out(str(tmp_path / "nada.inp"))


# ───────────── la herramienta ─────────────

@pytest.mark.parametrize("cual", [0, 1, 2])
def test_devuelve_el_registro_venga_por_donde_venga(terna, cual):
    """Incluso con el `.pre`, que antes producía un informe 247% desviado."""
    rutas = terna[:3]
    disco = open(terna[2]).read()
    t = _txt(rutas[cual])
    assert disco.strip() in t
    assert "Leído de" in t


def test_sin_out_reestima_y_lo_dice(terna, tmp_path):
    """Reestimar es legítimo si no hay registro; hacerlo en silencio no."""
    f_inp, _, _, _ = terna
    import shutil
    otro = tmp_path / "solo.inp"
    shutil.copyfile(f_inp, otro)
    t = _txt(str(otro))
    assert "REESTIMADO" in t
    assert "no es el registro" in t


def test_ya_no_reestima_cuando_hay_registro(terna):
    from tests._fuente import fuente_de
    src = fuente_de(srv.get_out_report)
    assert "hay_out" in src and "lee_out" in src
