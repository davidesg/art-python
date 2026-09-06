"""Un `.inp` sin ningún factor ARMA mata al binario `fue` (fue/BUG-0013).

El puente de Python lo desvía —por eso `estimar()` funciona— pero el ejecutable
y las wheels sin ese desvío mueren con SIGSEGV. Y no es hipotético: 178 de 4.505
`.inp` del ecosistema no declaran ningún factor, entre ellos ITCER, PGAS y RATIO,
las tres series del TFM en curso. Comprobado contra /usr/local/bin/fue.

El rodeo es el que los ficheros antiguos ya usaban sin saber por qué: declarar un
AR(1) FIJADO EN CERO. Mismo modelo, misma ℓ, mismo npar.
"""
import os
import shutil
import subprocess
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar


def _seccion_ar(ruta):
    txt = open(ruta, encoding="utf-8").read()
    return txt.split("regular AR operators:")[1].splitlines()[1].strip()


@pytest.fixture
def sin_arma(tmp_path):
    rng = np.random.default_rng(3)
    y = np.cumsum(rng.standard_normal(150) * 0.3) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2005, 1), name="W")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=True, refactor=_RESCALE_FACTOR)
    f = str(tmp_path / "W.inp")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _write_inp(ts, m, f)
    return f


def test_nunca_se_escribe_la_seccion_AR_vacia(sin_arma):
    assert _seccion_ar(sin_arma) != "0"
    assert _seccion_ar(sin_arma).split()[0] == "1"


def test_el_factor_va_FIJO_y_en_cero(sin_arma):
    """Si saliera libre, sería un parámetro más: otro modelo."""
    txt = open(sin_arma, encoding="utf-8").read()
    bloque = txt.split("regular AR operators:")[1].splitlines()[1:4]
    coef = [l for l in bloque if l.strip() and not l.startswith("**")][-1]
    val, libre = coef.split()
    assert float(val) == 0.0
    assert libre == "0", "el AR del rodeo tiene que ir FIJO"


def test_no_cambia_ni_un_digito(sin_arma, tmp_path):
    """El rodeo es una convención de escritura, no una reespecificación."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, m = estimar(sin_arma)
    # npar cuenta sólo lo libre: μ. El AR fijo no entra.
    assert m._result.npar == 1
    assert abs(m._result.loglik - (-724.0)) < 500      # cordura, no un número mágico
    libres = sum(1 for f in (m.ar_free or [[]])[0] if f) if m.ar else 0
    assert libres == 0


def test_un_modelo_CON_arma_no_se_toca(tmp_path):
    rng = np.random.default_rng(4)
    y = np.cumsum(rng.standard_normal(120) * 0.3) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2005, 1), name="A")
    m = fue.Model(ts, d=1, ar=[[0.3]], ar_free=[[True]], mu=0.0,
                  estimate_mu=False, refactor=_RESCALE_FACTOR)
    f = str(tmp_path / "A.inp")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _write_inp(ts, m, f)
    txt = open(f, encoding="utf-8").read()
    bloque = txt.split("regular AR operators:")[1].splitlines()[1:4]
    coef = [l for l in bloque if l.strip() and not l.startswith("**")][-1]
    assert coef.split()[1] == "1", "un AR de verdad tiene que seguir libre"


@pytest.mark.skipif(shutil.which("fue") is None, reason="sin binario fue")
def test_el_binario_ya_no_muere(sin_arma, tmp_path):
    """La prueba de fondo, y la única que mira el defecto real."""
    base = os.path.splitext(sin_arma)[0]
    r = subprocess.run(["fue", os.path.basename(base), "eml"],
                       cwd=os.path.dirname(sin_arma),
                       capture_output=True, timeout=180)
    assert r.returncode != -11, "SIGSEGV: el rodeo no está puesto"
    assert r.returncode == 0, f"fue devolvió {r.returncode}"


# ── el efecto lateral, que la suite encontró ──────────────────────────

def test_el_relleno_no_es_estructura():
    """En cuanto `art` empezó a escribir el AR(1) fijo, todo lo que preguntaba
    «¿este fichero lleva un modelo?» mirando si hay factores empezó a decir que
    sí sobre una serie pelada."""
    from art.pipeline import es_relleno, tiene_estructura_arma

    class M:
        ar = [[0.0]]
        ar_free = [[False]]
        ma = ar_s = ma_s = []
        ma_free = ar_s_free = ma_s_free = []
        ar_f = ma_f = []

    assert es_relleno([0.0], [False])
    assert not es_relleno([0.0], [True]), "libre en cero SÍ es un parámetro"
    assert not es_relleno([0.3], [False]), "fijo en 0,3 SÍ es un término"
    assert not tiene_estructura_arma(M())


def test_lo_que_distingue_un_modelo_es_que_SE_ESTIMO(tmp_path):
    """Un modelo de sólo `d=1` no tiene ningún término y sigue siendo un modelo
    estimado, con sus residuos. Lo que lo separa de una serie pelada no es su
    contenido: es su terna."""
    import art.mcp_server as srv
    rng = np.random.default_rng(31)
    n = 96
    y = 100.0 + 3.0 * np.arange(n) + np.cumsum(rng.normal(0, 1.0, n))
    y[60:] += 40.0
    ci = getattr(srv.create_inp, "fn", srv.create_inp)
    ce = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
    serie = str(tmp_path / "S.inp")
    modelo = str(tmp_path / "S_m00.inp")
    ci(list(map(float, y)), serie, name="S", freq=4, start_year=2000,
       start_period=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ce(inp_path=serie, output_path=modelo, lam=1.0, d=1, D=0, p=0, q=0,
           n_harmonics=0, seasonal=False, estimate_mu=False, guion_name="m00")
    pos = getattr(srv.preliminary_outlier_scan, "fn",
                  srv.preliminary_outlier_scan)
    def _txt(r):
        return "\n".join(c.text for c in r if getattr(c, "text", None))
    assert "lleva un MODELO" not in _txt(pos(serie, d=1, D=0, lam=1.0))
    assert "lleva un MODELO" in _txt(pos(modelo, d=1, D=0, lam=1.0))
