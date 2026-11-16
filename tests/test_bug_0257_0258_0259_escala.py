"""BUG-0257, 0258 y 0259: el factor de reescala fuera de los logaritmos, la
presentación y la semilla de μ. La regla es de `fue.scale`."""
import importlib.util
import pathlib

import numpy as np
import pytest

import fue

BUGS = pathlib.Path(__file__).resolve().parents[1] / "bugs"


@pytest.mark.parametrize("n", ["0257", "0258", "0259"])
def test_el_repro_sale_con_cero(n):
    ruta = BUGS / f"BUG-{n}-repro" / "repro.py"
    spec = importlib.util.spec_from_file_location(f"repro_{n}", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main() == 0


def _serie(nivel=100.0, n=160, seed=3):
    rng = np.random.default_rng(seed)
    e = np.zeros(n)
    for t in range(1, n):
        e[t] = 0.6 * e[t - 1] + rng.normal(0, 0.01)
    return nivel * np.exp(e)


@pytest.mark.parametrize("lam,d,nivel,factor", [
    (0.0, 0, 100.0, 100.0),     # logaritmos: siempre 100
    (0.0, 1, 1e6, 100.0),
    (1.0, 0, 100.0, 100.0),     # niveles en torno a 100: 100 vale (d.t. 122)
    (1.0, 0, 1e4, 1.0),         # con 100, 12 000: fuera de la banda
])
def test_el_factor_es_100_salvo_fuera_de_banda(lam, d, nivel, factor):
    from art.pipeline import factor_de_reescala
    ts = fue.TimeSeries(list(map(float, _serie(nivel))), freq=12, start=(2000, 1), name="Y")
    assert factor_de_reescala(ts, lam, d, 0) == factor


def test_el_factor_del_fichero_base_se_hereda_mientras_valga():
    from art.pipeline import factor_de_reescala
    ts = fue.TimeSeries(list(map(float, _serie())), freq=12, start=(2000, 1), name="Y")
    assert factor_de_reescala(ts, 0.0, 1, 0, base=10.0) == 10.0     # 0.1: dentro
    assert factor_de_reescala(ts, 0.0, 1, 0, base=1.0) == 100.0     # 0.01: fuera


@pytest.mark.parametrize("factor", [1.0, 10.0, 100.0, 1000.0])
@pytest.mark.parametrize("lam", [0.0, 1.0])
def test_la_ecuacion_no_depende_del_factor(lam, factor):
    """ω, μ y σ̂ₐ se leen igual venga el fichero con el factor que venga
    (BUG-0258): la GUI de atsw-gui escribe 1 y art 100."""
    from art.describe import model_equation
    y = _serie()
    y[100:] *= 1.05
    ts = fue.TimeSeries(list(map(float, y)), freq=12, start=(2000, 1), name="Y")

    def texto(f):
        w = fue.boxcox(y, lam, f)
        m = fue.Model(ts, d=0, D=0, boxlam=lam, ar=[[0.1]], ar_free=[[True]],
                      mu=float(np.mean(w)), estimate_mu=True, refactor=f,
                      interventions=[fue.Intervention("step", at=101, omega=[0.0],
                                                      omega_free=[True])])
        m.fit()
        out = model_equation(ts, m)
        return "\n".join(l for l in (out if isinstance(out, str) else str(out)).splitlines()
                         if "ℓ =" not in l and "ESCALA" not in l
                         and "factor" not in l and "fiar" not in l)

    import re
    def cifras(t):
        return [round(float(x), 2) for x in re.findall(r"\d+\.\d+", t)]
    assert cifras(texto(factor)) == pytest.approx(cifras(texto(100.0)), abs=0.02)


def test_la_ecuacion_avisa_de_una_escala_fuera_de_banda():
    from art.describe import aviso_de_escala
    y = _serie()
    ts = fue.TimeSeries(list(map(float, y)), freq=12, start=(2000, 1), name="Y")
    def modelo(f, d):
        return fue.Model(ts, d=d, D=0, boxlam=0.0, ar=[[0.1]], ar_free=[[True]], refactor=f)
    assert aviso_de_escala(modelo(100.0, 1)) == []
    aviso = "\n".join(aviso_de_escala(modelo(1.0, 1)))        # lo que escribe la GUI
    assert "ESCALA" in aviso and "factor 100" in aviso
