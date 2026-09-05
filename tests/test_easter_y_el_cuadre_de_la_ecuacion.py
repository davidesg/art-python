"""Un determinista sin rama de render desplaza TODA la ecuación (BUG-0097).

El defecto no era «falta el easter». `_seq` —los parámetros en orden de render—
acepta todos los tipos deterministas y el render sólo tenía ramas para unos
pocos, así que el ω de un tipo sin rama no se consumía y **todo lo posterior
salía corrido, arrastrando el error típico del anterior**. Medido:

    .out (fiel)                        lo que se mostraba
    ω easter = −0.124799  SE 5.8981    Dₜ:  (vacío)
    φ₁       = −0.052053  SE 0.0746    (1 + 0.1248·B)(∇Nₜ + 0.0521) = aₜ
    μ        = +0.623733  SE 2.1745             (5.8981)      (0.0746)

El ω del easter impreso como φ₁, el φ₁ como media, la media desaparecida, y
cada error típico bajo el coeficiente equivocado. Un modelo que no existe, bien
formateado.
"""
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.describe import model_equation
from art.guion import SIN_FECHA, _extract_spec
from art.outfile import lee_out
from art.pipeline import _RESCALE_FACTOR, _make_model, _write_inp, estimar


@pytest.fixture(scope="module")
def ajustado(tmp_path_factory):
    d = tmp_path_factory.mktemp("east")
    rng = np.random.default_rng(3)
    y = np.cumsum(rng.standard_normal(180) * 0.3) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2005, 1), name="E")
    ea = fue.Intervention("easter", at=0, omega=[0.0], omega_free=[True])
    m = fue.Model(ts, d=1, ar=[[0.0]], ar_free=[[True]], mu=0.0,
                  estimate_mu=True, interventions=[ea],
                  refactor=_RESCALE_FACTOR)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _write_inp(ts, m, str(d / "E.inp"))
        ts2, m2 = estimar(str(d / "E.inp"))
        m2.write_out(str(d / "E.out"))
    return ts2, m2, lee_out(str(d / "E.out"))


def _texto(ts, m):
    r = model_equation(ts, m)
    return r.summary if hasattr(r, "summary") else str(r)


# ── la ecuación dice lo que dice el .out ──────────────────────────────

def test_el_easter_aparece(ajustado):
    ts, m, _ = ajustado
    assert "Easter" in _texto(ts, m)


def test_cada_coeficiente_con_SU_error_tipico(ajustado):
    """Ésta es la prueba de fondo: los tres valores del `.out`, en su sitio."""
    ts, m, o = ajustado
    txt = _texto(ts, m)
    for p in (o.parametros or []):
        assert f"{abs(p.valor):.4f}" in txt, f"falta el valor {p.valor}"
        assert f"{p.se:.4f}" in txt, f"falta el error típico {p.se}"


def test_el_omega_del_easter_no_se_imprime_como_AR(ajustado):
    """Era el síntoma exacto: el ω salía donde va φ₁."""
    ts, m, o = ajustado
    txt = _texto(ts, m)
    om = next(p for p in o.parametros if "eterministic" in (p.bloque or ""))
    linea_easter = next(l for l in txt.splitlines() if "Easter" in l)
    assert f"{abs(om.valor):.4f}" in linea_easter


def test_la_media_no_desaparece(ajustado):
    ts, m, o = ajustado
    mu = next(p for p in o.parametros if "Mean" in (p.bloque or ""))
    assert f"{abs(mu.valor):.4f}" in _texto(ts, m)


# ── la clase, cerrada ─────────────────────────────────────────────────

def test_un_tipo_desconocido_no_desplaza_nada():
    """Lo que impide que el defecto vuelva con otro nombre."""
    from tests._fuente import fuente_de
    src = fuente_de(model_equation)
    i = src.index("for itv in (model.interventions")
    j = src.index("Flush harmonics")
    assert "\n        else:\n" in src[i:j], "sin `else` final en el render de Dₜ"


def test_el_otro_recorrido_de_la_misma_secuencia_tambien():
    """`describe_seasonal_params` camina la MISMA secuencia con su propio
    cursor y tenía el mismo agujero: un easter delante de un armónico y los
    armónicos se leían corridos."""
    from tests._fuente import fuente_de
    from art.describe import describe_seasonal_params
    src = fuente_de(describe_seasonal_params)
    assert "\n        else:\n" in src


def test_si_el_cursor_no_cuadra_se_dice(ajustado):
    """La red de seguridad. Se fuerza el desajuste quitando una rama de facto:
    un modelo cuyo `_seq` tiene más entradas de las que el render consume."""
    from tests._fuente import fuente_de
    src = fuente_de(model_equation)
    assert "pi.i != len(_seq)" in src
    assert "NO CUADRA" in src


# ── el registro no inventa fechas ─────────────────────────────────────

def test_el_easter_no_lleva_fecha_en_la_spec(ajustado):
    """`{'type':'easter','date':'01/2005'}` decía que hubo un suceso en enero de
    2005. No lo hubo: es un regresor de calendario sobre toda la muestra."""
    _, m, _ = ajustado
    itvs = _extract_spec(m, 0.0)["interventions"]
    ea = next(i for i in itvs if i["type"] == "easter")
    assert "date" not in ea


def test_un_suceso_de_verdad_SI_lleva_fecha(tmp_path):
    rng = np.random.default_rng(4)
    y = np.cumsum(rng.standard_normal(120) * 0.3) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2005, 1), name="S")
    itvs = [fue.Intervention("easter", at=0, omega=[0.0], omega_free=[True]),
            fue.Intervention("step", at=60, omega=[0.0], omega_free=[True])]
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, interventions=itvs,
                  refactor=_RESCALE_FACTOR)
    sp = _extract_spec(m, 0.0)["interventions"]
    assert {i["type"]: ("date" in i) for i in sp} == {"easter": False,
                                                     "step": True}
    assert next(i for i in sp if i["type"] == "step")["date"] == "01/2010"


def test_los_tipos_sin_fecha_estan_nombrados():
    assert "easter" in SIN_FECHA and "trend" in SIN_FECHA


# ── expuesto en el flujo guiado ───────────────────────────────────────

def test_se_puede_pedir_sin_editar_el_inp(tmp_path):
    rng = np.random.default_rng(11)
    y = np.cumsum(rng.standard_normal(180) * 0.3) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2005, 1), name="S")
    m = _make_model(ts, lam=0.0, d=1, D=0, p=1, q=0, n_harmonics=2,
                    estimate_mu=True, easter=True)
    assert any(i.type == "easter" for i in (m.interventions or []))


def test_en_series_no_mensuales_se_niega():
    """El motor sólo lo construye en mensual. Aceptarlo en trimestral daría un
    regresor vacío y un parámetro estimado sobre nada."""
    rng = np.random.default_rng(5)
    y = np.cumsum(rng.standard_normal(80) * 0.3) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2005, 1), name="Q")
    with pytest.raises(ValueError, match="MENSUALES"):
        _make_model(ts, lam=0.0, d=1, D=0, p=0, q=0, n_harmonics=1, easter=True)


def test_la_herramienta_lo_acepta_y_lo_documenta():
    from tests._fuente import fuente_de
    import art.mcp_server as srv
    ce = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
    src = fuente_de(ce)
    assert "easter: bool = False" in src
    assert "MONTHLY" in src, "el docstring tiene que decir que es sólo mensual"


# ── el contrato de ficheros aguanta con el easter dentro ──────────────

def test_el_pre_conserva_el_easter(tmp_path):
    """Era BUG-0007 de fue: el escritor del `.pre` emitía siete de las nueve
    palabras deterministas y el easter no tenía rama, así que el modelo se
    perdía en silencio. Arreglado en fue-1.13.1; esto lo vigila desde aquí."""
    rng = np.random.default_rng(3)
    y = np.cumsum(rng.standard_normal(150) * 0.3) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2005, 1), name="P")
    ea = fue.Intervention("easter", at=0, omega=[0.0], omega_free=[True])
    m = fue.Model(ts, d=1, ar=[[0.0]], ar_free=[[True]], mu=0.0,
                  estimate_mu=True, interventions=[ea],
                  refactor=_RESCALE_FACTOR)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _write_inp(ts, m, str(tmp_path / "P.inp"))
        _, m2 = estimar(str(tmp_path / "P.inp"))
        m2.write_pre(str(tmp_path / "P.pre"))
    assert "easter" in (tmp_path / "P.pre").read_text()
    from art.pipeline import mirar
    _, m3 = mirar(str(tmp_path / "P.pre"))
    assert [i.type for i in (m3.interventions or [])] == ["easter"]
    assert abs(m3.interventions[0].omega[0]
               - m2.interventions[0].omega[0]) < 1e-5


def test_el_defecto_esta_documentado():
    assert os.path.exists("bugs/BUG-0097-repro/repro.py")
