"""La spec del guion tiene que DETERMINAR el modelo.

Hallazgo #3 de la revisión con contexto limpio, y es el de fondo. Medido sobre
81 guiones reales: de 50 pares con spec idéntica **carácter a carácter**, 48
tenían ℓ distinta — mediana Δℓ = 4,87, máximo 57,88.

No eran revisitas. Era una spec que no distinguía modelos separados por 57
puntos de verosimilitud. Abiertos contra el motor, lo que los separaba era
siempre uno de tres, y los tres se caían de `_extract_spec`:

    ar_free / ma_free   las banderas libre/fijo   21 pares
    estimate_mu / mu    la media                  19 pares
    el `alter` de Nyquist                          5 pares

**La consecuencia no es cosmética.** Sin esto no hay identidad de estado
definible, y sin identidad de estado no hay lista cerrada posible: una construida
con la clave vieja declararía a `m01` una revisita de `m00` y podaría el modelo
bueno — 37,6 puntos de AIC en el caso medido. Y `guion_diff`, que compara dos
recorridos nodo a nodo, comparaba specs que no determinan modelos.
"""
import json
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.guion import _build_equation, _extract_spec
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar


def _spec_de(tmp, nombre, **kw):
    rng = np.random.default_rng(31)
    y = np.cumsum(rng.standard_normal(120) * 0.4) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1995, 1), name="V")
    base = dict(d=1, ar=[[0.0]], ar_free=[[True]], mu=0.0, estimate_mu=False,
                refactor=_RESCALE_FACTOR)
    base.update(kw)
    m = fue.Model(ts, **base)
    f = str(tmp / f"{nombre}.inp")
    _write_inp(ts, m, f)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, mm = estimar(f)
    return json.dumps(_extract_spec(mm, 0.0), sort_keys=True), mm._result.loglik


# ───────────── los tres campos que faltaban ─────────────

def test_la_media_distingue(tmp_path):
    """Un μ=0 FIJO y un μ=0 ESTIMADO son modelos distintos con un parámetro de
    diferencia. La spec los declaraba iguales."""
    a, la = _spec_de(tmp_path, "sin", estimate_mu=False)
    b, lb = _spec_de(tmp_path, "con", estimate_mu=True)
    assert a != b
    assert la != lb, "la fixture ya no separa los dos modelos"


def test_las_banderas_libre_fijo_distinguen(tmp_path):
    a, _ = _spec_de(tmp_path, "libre", ar=[[0.3]], ar_free=[[True]])
    b, _ = _spec_de(tmp_path, "fijo", ar=[[0.3]], ar_free=[[False]])
    assert a != b


def test_el_alter_queda_registrado(tmp_path):
    """El armónico de Nyquist —el (−1)ᵗ— es un término determinista como
    cualquier otro, y se filtraba por no ser un suceso."""
    rng = np.random.default_rng(5)
    y = np.cumsum(rng.standard_normal(100) * 0.4) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="A")
    alt = fue.Intervention("alter", at=0, omega=[0.0], omega_free=[True])
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, interventions=[alt],
                  refactor=_RESCALE_FACTOR)
    assert _extract_spec(m, 0.0)["alter"] is True
    m2 = fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                   refactor=_RESCALE_FACTOR)
    assert _extract_spec(m2, 0.0)["alter"] is False


def test_los_campos_nuevos_estan_todos():
    from tests._fuente import fuente_de

    from art.guion import _extract_spec
    src = fuente_de(_extract_spec)
    for c in ("mu", "estimate_mu", "alter", "ar_free", "ma_free",
              "ar_s_free", "ma_s_free"):
        assert f'"{c}"' in src, c


# ───────────── la ecuación también los muestra ─────────────

def test_la_ecuacion_muestra_la_media():
    """La ecuación es la presentación autoritativa. Si dos modelos distintos se
    escriben igual, la presentación miente."""
    base = {"lam": 0.0, "d": 1, "D": 0, "ifadf": [0, 0, 0], "p": 1, "q": 0,
            "P": 0, "Q": 0, "n_harmonics": 0, "interventions": [], "mu": 0.0,
            "alter": False}
    sin = _build_equation(base, 4)
    con = _build_equation(dict(base, estimate_mu=True), 4)
    assert sin != con
    assert "μ" in con and "μ" not in sin


def test_la_ecuacion_muestra_el_alter():
    base = {"lam": 0.0, "d": 1, "D": 0, "ifadf": [0, 0, 0], "p": 1, "q": 0,
            "P": 0, "Q": 0, "n_harmonics": 0, "interventions": [], "mu": 0.0}
    assert "(−1)ᵗ" in _build_equation(dict(base, alter=True), 4)
    assert "(−1)ᵗ" not in _build_equation(dict(base, alter=False), 4)


def test_una_media_fija_no_nula_tambien_se_ve():
    base = {"lam": 0.0, "d": 1, "D": 0, "ifadf": [0, 0, 0], "p": 1, "q": 0,
            "P": 0, "Q": 0, "n_harmonics": 0, "interventions": [],
            "estimate_mu": False, "alter": False}
    assert "+0.5" in _build_equation(dict(base, mu=0.5), 4)


# ───────────── compatibilidad ─────────────

def test_un_guion_viejo_sin_los_campos_sigue_abriendose():
    """Los campos son nuevos; los guiones ya escritos no los llevan."""
    viejo = {"lam": 0.0, "d": 1, "D": 0, "ifadf": [0, 0, 0], "p": 1, "q": 0,
             "P": 0, "Q": 0, "n_harmonics": 0, "interventions": []}
    eq = _build_equation(viejo, 4)
    assert eq.startswith("∇[ln y_t]")
    assert "μ" not in eq


def test_el_guion_real_recoge_los_campos(tmp_path):
    """De extremo a extremo, por la herramienta."""
    import art.mcp_server as srv
    rng = np.random.default_rng(12)
    y = np.cumsum(rng.standard_normal(90) * 0.4) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="E")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
    f = str(tmp_path / "E.inp")
    _write_inp(ts, m, f)
    ce = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ce(f, str(tmp_path / "E_m00.inp"), lam=0.0, d=1, D=0, p=1, q=0,
           n_harmonics=0, estimate_mu=True, guion_decision="x")
    g = [x for x in os.listdir(str(tmp_path)) if x.endswith("guion.json")][0]
    sp = json.load(open(str(tmp_path / g)))["entries"][0]["spec"]
    assert sp["estimate_mu"] is True
    assert "ar_free" in sp and "alter" in sp
