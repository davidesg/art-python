"""BUG-0169 y BUG-0170 — los dos defectos que bloquearon el run 3 de ES_CPI.

Los dos tienen la misma forma: la herramienta **acepta** lo que se le da, hace
otra cosa, y **no lo dice**.

**BUG-0169.** `load_data` sobre un índice `2002-01, 2002-02, …` devolvía
«Período: 2002 → 2294 (n=293, **anual**)» y remataba con «Fechas inferidas del
índice» — que era falso: no las había mirado. La causa está en
`fue.TimeSeries.from_pandas`, que sólo consulta `idx.freqstr`; en un índice
PARSEADO pandas deja eso en `None`, y se caía a `freq=1`.

Es la PRIMERA llamada de cualquier análisis, y de `freq` cuelga el método
entero: la estacionalidad, los armónicos, los retardos de la Q, el MEG, las
fechas de toda intervención.

**BUG-0170.** `confirm_and_estimate(easter=True, base_pre_path=…)` devolvía el
modelo SIN el regresor, con ℓ y AIC idénticos al anterior. Estaba documentado
—«ignored when base_pre_path is given»— y la herramienta no lo mencionaba al
ejecutarse. El daño de segundo orden era el hueco: no quedaba NINGUNA vía para
añadir easter a un modelo ya construido sin volver al `.inp` fresco y perder
todas las intervenciones.
"""
import os
import tempfile

import numpy as np
import pytest

fue = pytest.importorskip("fue")
pd = pytest.importorskip("pandas")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar


def _ld(**kw):
    fn = getattr(srv.load_data, "fn", srv.load_data)
    return "\n".join(getattr(x, "text", "") for x in fn(**kw))


def _csv(tmp_path, fechas, nom="S.csv"):
    f = tmp_path / nom
    rng = np.random.default_rng(2)
    v = 100.0 + np.cumsum(rng.standard_normal(len(fechas)) * 0.4)
    pd.DataFrame({"date": fechas, "value": v}).to_csv(f, index=False)
    return str(f)


# ═════════════════ BUG-0169 — deducir de verdad ═══════════════════════════

@pytest.mark.parametrize("fechas,esperado,etq", [
    ([f"{2002 + i // 12}-{i % 12 + 1:02d}" for i in range(60)], 12, "mensual"),
    ([f"{2002 + i // 4}-{(i % 4) * 3 + 1:02d}" for i in range(40)], 4, "trimestral"),
    ([str(2002 + i) for i in range(30)], 1, "anual"),
])
def test_la_frecuencia_se_DEDUCE_del_espaciado(fechas, esperado, etq, tmp_path):
    """Lo que el defecto hacía: caer a anual en los tres casos."""
    t = _ld(source_path=_csv(tmp_path, fechas, f"{etq}.csv"),
            output_inp=str(tmp_path / f"{etq}.inp"), column="value")
    assert etq in t, f"leída como otra cosa:\n{t[:300]}"
    _, m = fue.inp.load(str(tmp_path / f"{etq}.inp"))
    del m


def test_el_caso_del_run3_YYYY_MM(tmp_path):
    """`2002-01 … 2026-05`, 293 obs. Daba «2002 → 2294, anual»."""
    fechas = [f"{2002 + i // 12}-{i % 12 + 1:02d}" for i in range(293)]
    t = _ld(source_path=_csv(tmp_path, fechas, "ES.csv"),
            output_inp=str(tmp_path / "ES.inp"), column="value")
    assert "mensual" in t and "01/2002" in t
    assert "2294" not in t, "sigue leyendo mensual como anual"


def test_no_dice_haber_INFERIDO_lo_que_no_miro(tmp_path):
    """«Fechas inferidas del índice» afirmaba una comprobación que no se hacía,
    y por eso nadie volvía a mirar."""
    fechas = [f"{2002 + i // 12}-{i % 12 + 1:02d}" for i in range(36)]
    t = _ld(source_path=_csv(tmp_path, fechas), output_inp=str(tmp_path / "a.inp"),
            column="value")
    assert "DEDUCIDAS" in t
    t2 = _ld(source_path=_csv(tmp_path, fechas, "b.csv"),
             output_inp=str(tmp_path / "b.inp"), column="value",
             freq=12, start_year=2002, start_period=1)
    assert "frecuencia declarada" in t2, "no distingue deducir de que se lo digan"


def test_lo_declarado_MANDA_sobre_lo_deducido(tmp_path):
    """Deducir no puede pisar al analista."""
    fechas = [f"{2002 + i // 12}-{i % 12 + 1:02d}" for i in range(36)]
    t = _ld(source_path=_csv(tmp_path, fechas), output_inp=str(tmp_path / "c.inp"),
            column="value", freq=12, start_year=2002, start_period=1)
    assert "mensual" in t


def test_si_NO_se_puede_deducir_se_NIEGA_en_vez_de_suponer(tmp_path):
    """Adivinar mal es peor que preguntar: de `freq` cuelga el método entero."""
    fechas = ["2002-01-03", "2002-01-05", "2002-03-19", "2004-11-02", "2009-06-30"]
    t = _ld(source_path=_csv(tmp_path, fechas, "irr.csv"),
            output_inp=str(tmp_path / "irr.inp"), column="value")
    assert "no he sabido deducir la" in t.lower() or "no he sabido" in t.lower()
    assert "anual" not in t.split("frecuencia")[0]


# ═════════════════ BUG-0170 — easter al encadenar ═════════════════════════

@pytest.fixture(scope="module")
def base_pre(tmp_path_factory):
    """Un modelo mensual con paquete estacional y SIN easter."""
    d = tmp_path_factory.mktemp("east")
    rng = np.random.default_rng(5)
    n = 200
    y = 100.0 + np.cumsum(rng.standard_normal(n) * 0.4 + 0.15)
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2002, 1), name="E")
    itvs = []
    for k in (1, 2, 3):
        itvs.append(fue.Intervention("cos", at=0, omega=[0.0], omega_free=[True],
                                     harmonic=float(k)))
        itvs.append(fue.Intervention("sin", at=0, omega=[0.0], omega_free=[True],
                                     harmonic=float(k)))
    f = str(d / "E_m00.inp")
    _write_inp(ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                             refactor=_RESCALE_FACTOR, interventions=itvs), f)
    _, fit = estimar(f)
    fit.write_pre(f[:-4] + ".pre")
    return str(d), f[:-4] + ".pre"


def _n_easter(path):
    _, m = fue.load(path)
    return sum(1 for i in (m.interventions or []) if i.type == "easter")


def _ce(src, out, **kw):
    fn = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return fn(src, out, lam=0.0, d=1, D=0, p=1, q=0, n_harmonics=3, **kw)


def test_easter_llega_al_modelo_ENCADENADO(base_pre):
    """El defecto: el argumento se aceptaba y se descartaba en silencio."""
    d, pre = base_pre
    assert _n_easter(pre) == 0, "el testigo ya lo traía"
    out = os.path.join(d, "enc.inp")
    _ce(pre, out, easter=True, base_pre_path=pre)
    assert _n_easter(out[:-4] + ".pre") == 1, "sigue ignorándose al encadenar"


def test_no_se_DUPLICA_si_el_pre_ya_lo_trae(base_pre):
    """Se AÑADE, no se sustituye — y heredar no puede significar duplicar."""
    d, pre = base_pre
    p1 = os.path.join(d, "d1.inp")
    _ce(pre, p1, easter=True, base_pre_path=pre)
    p2 = os.path.join(d, "d2.inp")
    _ce(p1[:-4] + ".pre", p2, easter=True, base_pre_path=p1[:-4] + ".pre")
    assert _n_easter(p2[:-4] + ".pre") == 1


def test_sin_pedirlo_no_aparece(base_pre):
    d, pre = base_pre
    out = os.path.join(d, "sin.inp")
    _ce(pre, out, base_pre_path=pre)
    assert _n_easter(out[:-4] + ".pre") == 0


def test_el_resto_del_modelo_sobrevive(base_pre):
    """Añadir un determinista no puede costar los demás: es el hueco que el
    defecto abría —volver al `.inp` fresco perdía todo lo construido."""
    d, pre = base_pre
    _, m0 = fue.load(pre)
    out = os.path.join(d, "resto.inp")
    _ce(pre, out, easter=True, base_pre_path=pre)
    _, m1 = fue.load(out[:-4] + ".pre")
    n0 = len(m0.interventions or [])
    assert len(m1.interventions or []) == n0 + 1
    for t in ("cos", "sin"):
        assert (sum(1 for i in m1.interventions if i.type == t)
                == sum(1 for i in m0.interventions if i.type == t))


def test_la_descripcion_ya_no_dice_que_se_ignora():
    """La limitación estaba escrita y era cierta; ahora sería mentira."""
    import asyncio

    from tests._texto import dice
    ts = asyncio.run(srv.mcp.list_tools())
    t = next(x for x in ts if x.name == "confirm_and_estimate")
    d = t.description or ""
    assert not dice(d, "Like n_harmonics, it is ignored when base_pre_path")
    assert dice(d, "Funciona TAMBIÉN con `base_pre_path`")
