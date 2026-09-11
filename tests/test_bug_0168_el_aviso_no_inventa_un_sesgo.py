"""BUG-0168 — el aviso publicaba una magnitud de sesgo que nadie ha calculado.

El analista, en la corrida de ES_CPI:

    «El LLM sistemáticamente está observando los SE. Esto confunde: aparentemente
    está calculando el sesgo, pero ¿cómo lo hace? No tiene ningún algoritmo para
    calcular el sesgo de los SE. Lo único que puede calcular es cuando no hay
    estructura ARMA.»

No lo calcula: **repite nuestras cifras**. El aviso que art pega junto a cada
tabla de errores típicos publicaba cinco números con aspecto de magnitud —«al
menos 4.23×», «desde 0.46× hasta 4.23×», «de 3.02 y 2.83 a 1.31 y 1.28»— y a
continuación decía que no hay corrección posible ni cota conocida. Las dos cosas
a la vez no se sostienen: un número que no se puede aplicar, puesto al lado de
una SE, se aplica.

El proyecto ya rozó esto: la primera versión decía «entre 0.46× y 3.47×», se leyó
como una cota, y el arreglo fue añadir «al menos». Se atacó la FORMA —rango
contra cota— y no el fondo.

Y la asimetría que lo resume: art publicaba lo que NO puede calcular (el sesgo) y
se callaba lo que SÍ puede (σ̂/√n, la SE exacta de μ cuando no hay ARMA).
"""
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.diagnosis import se_exacta_de_la_media
from art.pipeline import AVISO_SE_DESDE_PRE, _RESCALE_FACTOR, _write_inp, estimar


def _serie(seed=3, n=150, deriva=0.2):
    rng = np.random.default_rng(seed)
    y = 100.0 + np.cumsum(rng.standard_normal(n) * 0.5 + deriva)
    return fue.TimeSeries(y.tolist(), freq=12, start=(2002, 1), name="MU")


def _ajusta(tmp_path, con_ar=False, nom="MU"):
    ts = _serie()
    kw = dict(ar=[[0.0]], ar_free=[[True]]) if con_ar else {}
    f = str(tmp_path / f"{nom}.inp")
    _write_inp(ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=True,
                             refactor=_RESCALE_FACTOR, **kw), f)
    return estimar(f)


# ── 1 · el aviso no publica magnitudes ─────────────────────────────────────

def test_no_publica_ningun_FACTOR():
    """Lo que el LLM estaba repitiendo. `4.23×` y compañía fuera."""
    import re
    assert not re.findall(r"\d+[.,]?\d*×", AVISO_SE_DESDE_PRE), \
        "el aviso vuelve a publicar un factor de desviación"


def test_no_publica_razones_t_concretas():
    import re
    assert not re.findall(r"\|t\|\s*=\s*\d", AVISO_SE_DESDE_PRE)
    for n in ("3.02", "2.83", "1.31", "1.28", "0.46", "4.23"):
        assert n not in AVISO_SE_DESDE_PRE, f"sigue la cifra {n}"


def test_dice_POR_QUE_no_hay_magnitud():
    """No basta con quitar los números: sin la razón, el lector supone que se
    nos olvidó medirlo."""
    from tests._texto import dice
    assert dice(AVISO_SE_DESDE_PRE, "No hay forma de saber cuánto se desvían")
    assert dice(AVISO_SE_DESDE_PRE, "subproducto del CAMINO")
    assert dice(AVISO_SE_DESDE_PRE, "No es un sesgo con magnitud: es ruido sin cota")


def test_conserva_lo_que_SI_afirma():
    """El aviso sigue siendo accionable: qué está roto, qué no, y qué hacer."""
    from tests._texto import dice
    assert dice(AVISO_SE_DESDE_PRE, "NO son fiables")
    assert dice(AVISO_SE_DESDE_PRE, "cambia decisiones, no sólo números")
    assert dice(AVISO_SE_DESDE_PRE, "Los **valores** sí son exactos")
    assert dice(AVISO_SE_DESDE_PRE, "reestima desde el `.inp`")
    assert "fue/bugs/BUG-0015" in AVISO_SE_DESDE_PRE, "no apunta a la raíz"


# ── 2 · y se calcula lo que SÍ se puede ────────────────────────────────────

def test_sin_ARMA_el_error_tipico_de_mu_tiene_FORMA_CERRADA(tmp_path):
    """El estimador de μ es la media muestral y no pasa por el optimizador."""
    ts, m = _ajusta(tmp_path)
    se = se_exacta_de_la_media(m)
    assert se is not None
    r = np.asarray(m._result.residuals, dtype=float)
    assert abs(se - r.std(ddof=1) / np.sqrt(r.size)) < 1e-12


def test_con_ARMA_LIBRE_no_aplica_y_devuelve_None(tmp_path):
    """Con ARMA el estimador ya no es la media muestral: la fórmula no vale, y
    devolver un número ahí sería el mismo pecado que se está quitando."""
    _, m = _ajusta(tmp_path, con_ar=True, nom="CONAR")
    assert se_exacta_de_la_media(m) is None


def test_un_AR_FIJO_en_cero_no_es_estructura(tmp_path):
    """`_write_inp` deja `ar=[[0.0]]` con el coeficiente FIJO. Contar la
    PRESENCIA apagaba esto en el caso más común —la media sola—, que es justo
    para el que existe. Es la confusión de BUG-0166 en otro sitio."""
    ts, m = _ajusta(tmp_path, nom="FIJO")
    assert (m.ar or []) and len(m.ar[0]) == 1, "el testigo dejó de valer"
    assert se_exacta_de_la_media(m) is not None


def test_sin_media_estimada_no_aplica(tmp_path):
    ts = _serie()
    f = str(tmp_path / "SINMU.inp")
    _write_inp(ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                             refactor=_RESCALE_FACTOR), f)
    assert se_exacta_de_la_media(estimar(f)[1]) is None


def test_el_bloque_lo_IMPRIME_y_lo_compara(tmp_path):
    """Publicarlo sin el número publicado al lado deja al lector sin la
    comparación, que es la mitad útil."""
    from art.mcp_server import _equation_for_prompt
    from tests._texto import dice
    ts, m = _ajusta(tmp_path, nom="IMP")
    t = _equation_for_prompt(ts, m)
    assert dice(t, "forma cerrada")
    se = se_exacta_de_la_media(m)
    assert f"{se:.6f}" in t, "no imprime σ̂/√n"
    pub = float(np.asarray(m._result.std_errors, dtype=float)[-1])
    assert f"{pub:.6f}" in t, "no imprime el publicado para comparar"


def test_con_ARMA_el_bloque_NO_lo_menciona(tmp_path):
    from art.mcp_server import _equation_for_prompt
    ts, m = _ajusta(tmp_path, con_ar=True, nom="IMPAR")
    assert "forma cerrada" not in _equation_for_prompt(ts, m)
