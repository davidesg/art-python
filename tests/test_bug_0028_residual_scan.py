"""BUG-0028 — el escaneo de anómalos sobre RESIDUOS era inalcanzable.

`preliminary_outlier_scan` hace `ts, _ = _load_ts_model(inp_path)`: descarta el
modelo y escanea la SERIE. Eso es correcto para su sitio —ANTES de que exista un
modelo— pero la sugerencia que ART imprimía mandaba a llamarla con un `.pre` y
`d=0, D=0, lam=1.0` «para ver la contribución de cada outlier a la ACF», y así
analiza la serie cruda sin transformar.

El modo de fallo es el peor: silencioso y tranquilizador. Sobre un modelo con un
residuo en |z|≈9 respondía «Sin observaciones extremas. Las ACF/PACF reflejan
fielmente la estructura ARMA.»

Un anómalo sólo lo es *respecto de un modelo*: antes de ajustar la dinámica, lo
que parece anómalo puede ser justo lo que el modelo predice. Por eso hacen falta
las dos herramientas, y por eso no pueden confundirse.
"""
import os
import tempfile

import numpy as np
import pytest

from art import mcp_server as A


def _texto(res):
    return "\n".join(c.text for c in res if hasattr(c, "text"))


@pytest.fixture(scope="module")
def caso():
    """Nivel SUAVE con tendencia y un escalón: invisible en niveles (la sd está
    dominada por la tendencia), |z| enorme en los residuos. Es la configuración
    que produce el falso negativo, y la de una serie económica corriente."""
    d = tempfile.mkdtemp(prefix="bug0028-")
    rng = np.random.default_rng(31)
    n = 96
    y = 100.0 + 3.0 * np.arange(n) + np.cumsum(rng.normal(0, 1.0, n))
    y[60:] += 40.0
    inp = os.path.join(d, "S.inp")
    A.create_inp(list(map(float, y)), inp, name="S", freq=4,
                 start_year=2000, start_period=1)
    modelo = os.path.join(d, "S_m00.inp")
    A.confirm_and_estimate(inp_path=inp, output_path=modelo, lam=1.0, d=1, D=0,
                           p=0, q=0, n_harmonics=0, seasonal=False,
                           estimate_mu=False, guion_name="m00")
    return inp, modelo


def test_el_escaneo_de_residuos_encuentra_lo_que_hay(caso):
    _, modelo = caso
    txt = _texto(A.residual_outlier_scan(modelo, threshold=2.5))
    assert "observación(es) extrema(s)" in txt
    assert "z=+9" in txt                      # el anómalo, con su tamaño


def test_dice_explicitamente_que_escanea_residuos(caso):
    """La cabecera antigua decía «Serie tipificada» sin decir CUÁL: nada
    delataba la sustitución."""
    _, modelo = caso
    txt = _texto(A.residual_outlier_scan(modelo))
    assert "sobre los RESIDUOS" in txt
    assert "no sobre la serie" in txt


def test_la_herramienta_de_serie_sigue_dando_el_falso_negativo(caso):
    """No se ha «arreglado» preliminary_outlier_scan: hace lo que debe hacer,
    escanear la serie. Lo que se arregla es que no se confunda con la otra."""
    _, modelo = caso
    txt = _texto(A.preliminary_outlier_scan(modelo.replace(".inp", ".pre"),
                                            d=0, D=0, lam=1.0, threshold=2.5))
    assert "Sin observaciones extremas" in txt      # sigue siendo así


def test_pero_ahora_AVISA_cuando_el_fichero_lleva_modelo(caso):
    _, modelo = caso
    txt = _texto(A.preliminary_outlier_scan(modelo, d=0, D=0, lam=1.0))
    assert "lleva un MODELO" in txt
    assert "residual_outlier_scan" in txt
    assert "BUG-0028" in txt


def test_no_avisa_en_su_uso_legitimo(caso):
    """Antes de que exista modelo, escanear la serie es exactamente lo que toca
    y el aviso sería ruido."""
    inp, _ = caso
    txt = _texto(A.preliminary_outlier_scan(inp, d=1, D=0, lam=1.0))
    assert "lleva un MODELO" not in txt


def test_la_sugerencia_impresa_ya_no_manda_a_la_herramienta_equivocada():
    fuente = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "src", "art", "mcp_server.py"),
        encoding="utf-8").read()
    assert 'preliminary_outlier_scan(inp_path=\\"<modelo_actual>.pre\\"' not in fuente
    assert 'residual_outlier_scan(inp_path=\\"<modelo_actual>.inp\\")' in fuente


def test_los_dos_escaneos_ven_series_distintas(caso):
    """La prueba directa: las medias tipificadas que reportan no coinciden."""
    _, modelo = caso
    r = _texto(A.residual_outlier_scan(modelo))
    s = _texto(A.preliminary_outlier_scan(modelo, d=0, D=0, lam=1.0))
    def mu(t):
        for l in t.splitlines():
            if "Serie tipificada" in l:
                return l.split("μ̂=")[1].split(",")[0]
        return None
    assert mu(r) is not None and mu(s) is not None
    assert mu(r) != mu(s)
