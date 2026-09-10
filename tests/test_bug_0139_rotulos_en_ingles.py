"""BUG-0139 — lo que se DIBUJA va en inglés; lo que se NARRA, no.

El reparto no es cosmético y tiene una razón operativa: la narrativa de `art`
—el `summary` de cada `Description`— la traduce el asistente al idioma del
usuario antes de enseñarla, y así lo mandan las instrucciones del servidor. La
FIGURA no pasa por ahí: los píxeles llegan al analista tal cual se dibujaron. Un
rótulo en español dentro de la figura es texto que NADIE va a traducir.

De ahí la regla del analista en el censo de figuras:

> *«Los labels y nombres deberían estar en inglés dado que usamos acf/pacf, que
> son siglas en inglés… impulse en lugar de impulso, etc.»*

Esta prueba la hace exigible: recoge TODO el texto de cada figura superviviente
—títulos, ejes, leyendas, anotaciones y el pie— y busca español.
"""
import numpy as np
import pytest

fue = pytest.importorskip("fue")
matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
from matplotlib.text import Text

import art.describe as _d
from art.describe import describe_prelim_scan
from art.episodes import agrupa_episodios
from art.escalera import escalera_de_ockham, describe_escalera
from art.ltf import describe_ltf, describe_superposicion


# Palabras que sólo existen en español. No es una lista de «palabras
# prohibidas» arbitraria: son las que estaban en las figuras el día que se
# levantó el defecto, más las vecinas obvias por las que se colarían otra vez.
CASTELLANO = (
    "retardo", "peldaño", "observación", "contribución", "tipificada",
    "respuesta", "ganancia", "umbral", "escalón", "impulso", "nivel",
    "omitiendo", "calibrado", "suceso", "residuo", "diferencias",
    "estacional", "serie", "media", "atípico", "anómalo", "muestra",
    "decide el orden", "camino",
)


def _textos_de(fig) -> list[str]:
    """Todo el texto que la figura pone delante del analista."""
    out = [t.get_text() for t in fig.findobj(Text)]
    for ax in fig.axes:
        leg = ax.get_legend()
        if leg is not None:
            out += [t.get_text() for t in leg.get_texts()]
    return [t for t in out if t and t.strip()]


@pytest.fixture
def captura(monkeypatch):
    """Intercepta `_fig_b64` para quedarse con la figura antes de cerrarla.

    Las tres funciones importan `_fig_b64` DENTRO del cuerpo (`from
    art.describe import ...`), así que parchear el módulo basta y no hace falta
    tocar ninguna firma para poder mirar lo que se dibujó.
    """
    vistas = []
    real = _d._fig_b64

    def espia(fig, *a, **k):
        vistas.append(_textos_de(fig))
        return real(fig, *a, **k)

    monkeypatch.setattr(_d, "_fig_b64", espia)
    return vistas


def _sin_castellano(textos, quien):
    plano = " · ".join(textos).lower()
    malas = [w for w in CASTELLANO if w in plano]
    assert not malas, (
        f"{quien}: la figura dibuja texto en español que nadie traducirá: "
        f"{malas}\n  texto: {textos}"
    )


def _base_con_suceso(nivel=(9.0,), semilla=11):
    rng = np.random.default_rng(semilla)
    y = rng.standard_normal(200)
    for k, v in enumerate(nivel):
        y[60 + k] += v
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2004, 1), name="SINT")
    m = fue.Model(ts, d=0, mu=0.0, estimate_mu=False)
    m.fit()
    r = np.asarray(m._result.residuals, dtype=float)
    z = (r - r.mean()) / r.std(ddof=0)
    ext = [(i + 1, float(z[i])) for i in range(len(z)) if abs(z[i]) > 3]
    return ts, m, max(agrupa_episodios(ext, ventana=2, d=0), key=lambda e: e.z_max)


def test_la_calibracion_de_distorsiones_rotula_en_ingles(captura):
    # Serie positiva y en niveles: `describe_prelim_scan` mira la SERIE
    # transformada (λ, d, D), no los residuos, y con λ=1 y d=1 el pico de +9
    # sale como el anómalo que tiene que rotular.
    rng = np.random.default_rng(11)
    y = 100.0 + np.cumsum(rng.standard_normal(120))
    y[60] += 12.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2004, 1), name="SINT")
    describe_prelim_scan(ts, d=1, D=0, lam=1.0, threshold=3.0)
    assert captura, "no se dibujó ninguna figura"
    _sin_castellano(captura[-1], "describe_prelim_scan")


def test_la_escalera_de_ockham_rotula_en_ingles(captura):
    _ts, m, ep = _base_con_suceso()
    describe_escalera(escalera_de_ockham(m, ep))
    assert captura, "no se dibujó ninguna figura"
    _sin_castellano(captura[-1], "describe_escalera")


def test_la_respuesta_de_la_flt_rotula_en_ingles(captura):
    describe_ltf([2.5, -1.0], K=12)
    assert captura, "no se dibujó ninguna figura"
    _sin_castellano(captura[-1], "describe_ltf")


def test_la_superposicion_sigue_rotulando_en_ingles(captura):
    """Ésta ya estaba en inglés (BUG-0135) y aquí queda con red debajo."""
    _ts, m, ep = _base_con_suceso()
    r = np.asarray(m._result.residuals, dtype=float)
    describe_superposicion(r.tolist(), at=ep.inicio, omega=[9.0], d=0)
    assert captura, "no se dibujó ninguna figura"
    _sin_castellano(captura[-1], "describe_superposicion")


def test_el_nombre_del_peldano_sigue_en_espanol_en_la_TABLA():
    """El reparto, por el otro lado: la narrativa NO se traduce a inglés.

    Si alguien «arregla» el defecto traduciendo `Peldano.nombre`, la tabla y el
    dict de datos se van a inglés y el asistente pierde el texto que sabe
    traducir. La figura tiene su propio nombre y por eso no hace falta.
    """
    _ts, m, ep = _base_con_suceso()
    d = describe_escalera(escalera_de_ockham(m, ep))
    assert "escalón en el nivel" in d.summary or "impulso en el nivel" in d.summary
