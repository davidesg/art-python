"""BUG-0212 — el escaneo latente de anómalos se contradecía.

«distorsión leve (ACF_max=0 %) — SÍ cambian la identificación … NO fijes p y
q» sobre modelos ya adecuados; «distorsión fuerte» sin un solo retardo que
cambiase; y veredictos que cambiaban por cruces mínimos de la banda —r(5) de
0,157 a 0,118 con banda ±0,136 (IPC_ES_SA)—.

Tres arreglos, y cada uno tiene su prueba:

* un MARGEN para el cruce (`MARGEN_CRUCE`): de claramente fuera a claramente
  dentro, un error típico entero a través del borde;
* el nivel de distorsión se RECONCILIA con la calibración: cambia ⇒ nunca
  «leve»; no cambia ⇒ nunca «fuerte»; una sola calibración por salida;
* con ARMA ya estimado la línea latente no ordena «NO fijes p y q».
"""
import os
import warnings

import numpy as np
import pytest

os.environ.setdefault("ART_NO_VIEWER", "1")

from art.calibracion import (MARGEN_CRUCE, CalibracionCorrelograma, Distorsion,
                             calibra_correlograma, describe_calibracion,
                             nivel_coherente)


# ═════════════════════ el margen del cruce ═════════════════════

@pytest.mark.parametrize("obs, cal, banda", [
    (0.157, 0.118, 0.136),        # IPC_ES_SA, r(5)
    (0.161, 0.143, 0.146),        # Salamanca, r(12)
    (-0.2221, -0.1194, 0.2195),   # RATIO_m10, PACF(6): fuera por un 1 %
])
def test_un_cruce_minimo_no_cambia_el_veredicto(obs, cal, banda):
    d = Distorsion(lag=5, banda=banda, acf_obs=obs, acf_cal=cal,
                   pacf_obs=obs, pacf_cal=cal)
    assert d.acf_flip is None and d.pacf_flip is None
    # pero se NOMBRA: cruza el borde, y en la figura se ve
    assert d.cruce_marginal


def test_un_cruce_claro_sigue_contando():
    b = 0.136
    fab = Distorsion(lag=1, banda=b, acf_obs=b * 1.4, acf_cal=b * 0.5,
                     pacf_obs=0.0, pacf_cal=0.0)
    enm = Distorsion(lag=1, banda=b, acf_obs=b * 0.5, acf_cal=b * 1.4,
                     pacf_obs=0.0, pacf_cal=0.0)
    assert fab.acf_flip == "fabricada" and not fab.cruce_marginal
    assert enm.acf_flip == "enmascarada" and not enm.cruce_marginal


def test_el_margen_es_un_error_tipico_a_traves_del_borde():
    """banda = 2/√n, error típico = 1/√n: de banda·(1+m) a banda·(1−m) hay
    2·m·banda, y con m=0,25 eso es exactamente 1/√n."""
    n = 216
    banda = 2 / np.sqrt(n)
    assert 2 * MARGEN_CRUCE * banda == pytest.approx(1 / np.sqrt(n))


def test_el_veredicto_no_cambia_dice_que_hubo_un_roce():
    d = Distorsion(lag=5, banda=0.136, acf_obs=0.157, acf_cal=0.118,
                   pacf_obs=0.149, pacf_cal=0.115)
    c = CalibracionCorrelograma(distorsiones=[d], extremos=[(40, 3.1)], n=216,
                                banda=0.136, umbral=2.5, sigma_obs=1.0,
                                sigma_cal=0.95)
    assert not c.cambia_la_identificacion
    txt = describe_calibracion(c, con_figura=False).summary
    assert "no cambia la identificación" in txt
    assert "r(5)" in txt and "margen" in txt


# ═════════════════════ un solo veredicto ═════════════════════

def _cal(cambia: bool):
    if cambia:
        d = Distorsion(lag=2, banda=0.2, acf_obs=0.30, acf_cal=0.05,
                       pacf_obs=0.0, pacf_cal=0.0)
    else:
        d = Distorsion(lag=2, banda=0.2, acf_obs=0.05, acf_cal=0.06,
                       pacf_obs=0.0, pacf_cal=0.0)
    return CalibracionCorrelograma(distorsiones=[d], extremos=[(5, 3.0)], n=100,
                                   banda=0.2, umbral=2.5, sigma_obs=1.0,
                                   sigma_cal=0.9)


@pytest.mark.parametrize("nivel, cambia, esperado", [
    ("light", True, "moderate"),      # cambia ⇒ nunca «leve»
    ("moderate", True, "moderate"),
    ("strong", True, "strong"),
    ("light", False, "light"),
    ("moderate", False, "moderate"),
    ("strong", False, "moderate"),    # no cambia ⇒ nunca «fuerte»
])
def test_el_nivel_se_reconcilia_con_la_calibracion(nivel, cambia, esperado):
    assert nivel_coherente(nivel, _cal(cambia)) == esperado


def test_sin_calibracion_el_nivel_queda():
    assert nivel_coherente("strong", None) == "strong"


def _series():
    """Series con anómalos de todos los tamaños: ruido blanco, AR(1) y MA(1)."""
    for seed in range(40):
        g = np.random.default_rng(seed)
        n = int(g.integers(90, 240))
        e = g.standard_normal(n + 1)
        tipo = seed % 3
        if tipo == 0:
            x = e[1:]
        elif tipo == 1:
            x = np.zeros(n)
            for t in range(1, n):
                x[t] = 0.5 * x[t - 1] + e[t]
        else:
            x = e[1:] + 0.4 * e[:-1]
        for _ in range(int(g.integers(1, 4))):
            x[int(g.integers(5, n - 5))] += float(g.choice([-1, 1])
                                                  * g.uniform(3, 9))
        yield seed, x


def test_el_escaneo_da_un_solo_veredicto():
    """El invariante del arreglo, sobre 40 series: «fuerte» ⇒ cambia, «leve»
    ⇒ no cambia, y el texto dice lo mismo que el dato."""
    fue = pytest.importorskip("fue")
    from art.describe import describe_prelim_scan
    vistos = set()
    for seed, x in _series():
        ts = fue.TimeSeries(x.tolist(), freq=12, start=(2000, 1), name="X")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            desc = describe_prelim_scan(ts, d=0, D=0, lam=1.0, threshold=2.5)
        dd = desc.data
        if not dd["n_outliers"]:
            continue
        nivel, cambia = dd["distortion_level"], dd["cambia_la_identificacion"]
        vistos.add((nivel, cambia))
        assert cambia is not None, seed
        if nivel == "strong":
            assert cambia, (seed, "«fuerte» sin un solo retardo que cambie")
        if nivel == "light":
            assert not cambia, (seed, "«leve» y «cambia» a la vez")
        s = desc.summary
        if cambia:
            assert "Distorsión leve" not in s, seed
            assert dd["flips_ar"] or dd["flips_ma"]
        else:
            assert "Distorsión fuerte" not in s, seed
        # la calibración de la tabla, con los mismos omitidos, dice lo mismo
        cal = calibra_correlograma(x, umbral=2.5,
                                   omitir=set(dd["omitidos"]), top_pares=0)
        assert cal.cambia_la_identificacion == cambia, seed
    # el barrido tiene dientes: aparecen los dos lados del veredicto
    assert any(c for _, c in vistos) and any(not c for _, c in vistos), vistos


def test_la_banda_del_escaneo_es_la_de_la_calibracion():
    """1,96/√n en el escaneo y 2/√n en la calibración: un retardo entre las
    dos líneas era «fuera» para ACF_max y «dentro» para el veredicto."""
    from art import describe
    src = __import__("_fuente").fuente_de(describe.describe_prelim_scan)
    assert "1.96 / np.sqrt(len(w_std))" not in src
    assert "2.0 / np.sqrt(len(w_std))" in src


# ═════════════════════ la línea latente ═════════════════════

@pytest.fixture(scope="module")
def modelo(tmp_path_factory):
    """Un MA(1) sobre ∇ln, estimado: el modelo ya ADECUADO del informe."""
    fue = pytest.importorskip("fue")
    from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar
    d = tmp_path_factory.mktemp("b212")
    g = np.random.default_rng(212)
    n = 200
    e = g.standard_normal(n + 1) * 0.01
    w = e[1:] - 0.4 * e[:-1] + 0.002
    w[120] += 0.05
    ts = fue.TimeSeries(np.exp(4 + np.cumsum(w)).tolist(), freq=12,
                        start=(2002, 1), name="W")
    f = str(d / "W.inp")
    _write_inp(ts, fue.Model(ts, d=1, boxlam=0.0, ma=[[0.4]], ma_free=[[True]],
                             mu=0.002, estimate_mu=True,
                             refactor=_RESCALE_FACTOR), f)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ts2, m = estimar(f)
    m.write_pre(f[:-4] + ".pre")
    return ts2, m, f


def _escaneo_falso(monkeypatch, **data):
    """El escaneo con un veredicto dado, para ver qué hace la línea con él."""
    from art import describe
    from art.describe import Description
    base = dict(n_outliers=2, distortion_level="moderate", var_outlier_pct=4.3,
                acf_max_pct=0.0, cambia_la_identificacion=True,
                flips_ar=[5], flips_ma=[5], flips_fabricados=[5],
                flips_enmascarados=[])
    base.update(data)
    monkeypatch.setattr(describe, "describe_prelim_scan",
                        lambda *a, **k: Description(summary="", figure_b64=None, data=base,
                                                    recommendation=""))


def _linea(modelo):
    import art.mcp_server as srv
    ts, m, f = modelo
    txt, _ = srv._auto_scan_section(ts, m, 0.0, 1, 0, 0, 1, 0, 0, f,
                                    f[:-4] + ".pre")
    return txt


def test_con_arma_estimado_no_ordena_no_fijar_p_y_q(modelo, monkeypatch):
    _escaneo_falso(monkeypatch)
    txt = _linea(modelo)
    assert "Escaneo de anómalos (latente)" in txt
    assert "NO fijes p y q" not in txt
    assert "lo fabrica el anómalo" in txt
    assert "procede a contrastes formales" in txt


def test_con_arma_y_señal_tapada_pide_revisar_sin_ordenar(modelo, monkeypatch):
    _escaneo_falso(monkeypatch, flips_fabricados=[], flips_enmascarados=[5])
    txt = _linea(modelo)
    assert "NO fijes p y q" not in txt
    assert "tapa" in txt and "residual_outlier_scan" in txt


def test_la_linea_no_es_leve_y_decisiva_a_la_vez(modelo, monkeypatch):
    _escaneo_falso(monkeypatch, distortion_level="moderate")
    txt = _linea(modelo)
    assert "distorsión leve" not in txt


def test_sin_cambio_procede(modelo, monkeypatch):
    _escaneo_falso(monkeypatch, distortion_level="light",
                   cambia_la_identificacion=False, flips_ar=[], flips_ma=[],
                   flips_fabricados=[])
    txt = _linea(modelo)
    assert "ningún retardo cambia" in txt
    assert "NO fijes" not in txt and "SÍ cambian" not in txt


def test_el_escaneo_real_y_la_tabla_dicen_lo_mismo(modelo):
    """`residual_outlier_scan`: el veredicto del escaneo y el de la tabla de
    calibración salen de la misma cuenta — no puede haber «distorsión leve,
    razonable pasar a ARMA» encima de «cambia la identificación»."""
    import art.mcp_server as srv
    _, _, f = modelo
    fn = getattr(srv.residual_outlier_scan, "fn", srv.residual_outlier_scan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = fn(f, threshold=2.5)
    txt = "\n".join(getattr(x, "text", "") for x in out)
    assert "Veredicto —" in txt
    if "**cambia la identificación**" in txt:
        assert "Distorsión leve" not in txt
    else:
        assert "Distorsión fuerte" not in txt


# ═════════════════════ la ventana estacional ═════════════════════
# Decisión del mantenedor: la calibración decide sobre los retardos que
# identifican el modelo — 1..12 y, SI HAY ESTACIONALIDAD, s, 2s, 3s. Lo que
# cae fuera (el k=28 de Villaverde m07) no decide nunca.

def _con_pares(separacion, n=216, golpe=6.0, semilla=24):
    """Ruido blanco con cuatro anómalos separados `separacion`: fabrican
    r(separacion) y nada en los retardos 1..12."""
    x = np.random.default_rng(semilla).standard_normal(n)
    for t in (50, 50 + separacion, 50 + 2 * separacion, 50 + 3 * separacion):
        x[t] += golpe
    return x


def test_un_flip_en_24_con_estacionalidad_cambia_la_identificacion():
    cal = calibra_correlograma(_con_pares(24), umbral=3.0, estacional=12)
    assert [d.lag for d in cal.distorsiones][-2:] == [24, 36]
    assert cal.ventana_texto == "retardos 1–12 y 24, 36"
    assert any(d.lag == 24 and d.acf_flip == "fabricada" for d in cal.flips_ma)
    assert cal.cambia_la_identificacion
    txt = describe_calibracion(cal, con_figura=False).summary
    assert "retardos 1–12 y 24, 36" in txt


def test_el_mismo_flip_sin_estacionalidad_no_decide():
    cal = calibra_correlograma(_con_pares(24), umbral=3.0, estacional=0)
    assert max(d.lag for d in cal.distorsiones) == 12
    assert not cal.cambia_la_identificacion
    assert "retardos 1–12" in describe_calibracion(cal, con_figura=False).summary


def test_el_retardo_28_no_decide_nunca():
    for s in (0, 12):
        cal = calibra_correlograma(_con_pares(28), umbral=3.0, estacional=s)
        assert 28 not in [d.lag for d in cal.distorsiones]
        assert not cal.cambia_la_identificacion, s


def test_los_retardos_estacionales_se_acotan_por_n_cuartos():
    # n=100: retardo útil 25 → entran 24 pero no 36
    cal = calibra_correlograma(np.random.default_rng(1).standard_normal(100),
                               umbral=3.0, estacional=12)
    assert [d.lag for d in cal.distorsiones][-1] == 24
    # trimestral, n=120: 1..12 y 4, 8, 12 ya están dentro → sólo 1..12
    cal = calibra_correlograma(np.random.default_rng(1).standard_normal(120),
                               umbral=3.0, estacional=4)
    assert [d.lag for d in cal.distorsiones] == list(range(1, 13))


def test_la_estacionalidad_sale_del_modelo():
    fue = pytest.importorskip("fue")
    from art.calibracion import estacionalidad_del_modelo
    ts = fue.TimeSeries(list(np.exp(np.cumsum(np.full(120, 0.01)))), freq=12,
                        start=(2000, 1), name="S")
    assert estacionalidad_del_modelo(fue.Model(ts, d=1)) == 0
    assert estacionalidad_del_modelo(fue.Model(ts, d=1, D=1)) == 12
    assert estacionalidad_del_modelo(
        fue.Model(ts, d=1, ma_s=[[0.5]], ma_s_free=[[True]])) == 12


def test_el_escaneo_sin_modelo_usa_la_D_que_le_pasan():
    fue = pytest.importorskip("fue")
    from art.describe import describe_prelim_scan
    x = _con_pares(24)
    ts = fue.TimeSeries(x.tolist(), freq=12, start=(2000, 1), name="X")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        con = describe_prelim_scan(ts, d=0, D=0, lam=1.0, threshold=3.0,
                                   estacional=12)
        sin = describe_prelim_scan(ts, d=0, D=0, lam=1.0, threshold=3.0,
                                   estacional=0)
    assert 24 in con.data["ventana"] and con.data["cambia_la_identificacion"]
    assert 24 not in sin.data["ventana"]
    assert not sin.data["cambia_la_identificacion"]
