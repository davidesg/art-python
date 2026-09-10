"""BUG-0140 — las figuras del nodo de intervención rotulaban «observación 61».

El analista discute el suceso por su FECHA. Lo escribe así en el `.inp`
(`step 4 2008`), lo lee así en el `.out`, y lo dice así en la tesis. El único
sitio donde tenía que traducir a mano de un índice a un trimestre era la
figura — y encima con el desfase de la diferenciación en la cabeza, porque
sobre residuos la observación 1 no es la 1 de la serie (BUG-0067).

El calendario **ya estaba** en `model.series`. No era un dato que faltase: era
un dato que nadie leía.
"""
import numpy as np
import pytest

fue = pytest.importorskip("fue")
matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
from matplotlib.text import Text

import art.describe as _d
from art.describe import _eje_de_fechas
from art.episodes import agrupa_episodios
from art.escalera import escalera_de_ockham, describe_escalera
from art.ltf import describe_superposicion, _fecha_de


@pytest.fixture
def captura(monkeypatch):
    vistas = []
    real = _d._fig_b64

    def espia(fig, *a, **k):
        fig.canvas.draw()          # los ticks no existen hasta que se dibuja
        t = [x.get_text() for x in fig.findobj(Text)]
        vistas.append([x for x in t if x and x.strip()])
        return real(fig, *a, **k)

    monkeypatch.setattr(_d, "_fig_b64", espia)
    return vistas


# ────────── la cuenta, que es donde estaba el riesgo ──────────

def test_la_fecha_de_una_observacion_lleva_el_desfase_de_la_diferenciacion():
    """Un pico en la observación 66 (1-based) de una trimestral desde 2004Q1.

    Sobre la SERIE es la 66 y cae en Q2/2020. Sobre los residuos de un modelo
    con d=1 esa misma fecha es la observación 65, porque la diferenciación se
    comió la primera. Las dos rutas tienen que dar Q2/2020.
    """
    assert _fecha_de(66, 4, (2004, 1), desfase=0) == "Q2/2020"
    assert _fecha_de(65, 4, (2004, 1), desfase=1) == "Q2/2020"
    # y con estacional: d=1, D=1, s=4 se come cinco
    assert _fecha_de(61, 4, (2004, 1), desfase=5) == "Q2/2020"


def test_sin_calendario_no_se_inventa_ninguno():
    assert _fecha_de(66, 0, (2004, 1)) == ""
    assert _fecha_de(66, 4, ()) == ""


def test_el_helper_rotula_los_ticks_con_fechas():
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.plot(np.arange(1, 41), np.zeros(40))
    _eje_de_fechas(ax, 4, (2004, 1), desfase=0)
    fig.canvas.draw()
    etq = [t.get_text() for t in ax.get_xticklabels() if t.get_text()]
    plt.close(fig)
    assert etq, "el eje quedó sin rótulos"
    assert all(e.startswith("Q") and "/" in e for e in etq), etq
    # el tick de la observación 20: at0 = 19, y 19 trimestres desde 2004Q1
    # son Q4/2008 — la misma cuenta que escribe `step 4 2008` en un `.inp`.
    assert "Q4/2008" in etq, etq


# ────────── las dos figuras ──────────

def _base_con_suceso():
    rng = np.random.default_rng(11)
    y = rng.standard_normal(120)
    y[64] += 9.0                      # 0-based 64 → obs 65 → Q1/2020 en niveles
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2004, 1), name="SINT")
    m = fue.Model(ts, d=0, mu=0.0, estimate_mu=False)
    m.fit()
    r = np.asarray(m._result.residuals, dtype=float)
    z = (r - r.mean()) / r.std(ddof=0)
    ext = [(i + 1, float(z[i])) for i in range(len(z)) if abs(z[i]) > 3]
    return ts, m, max(agrupa_episodios(ext, ventana=2, d=0), key=lambda e: e.z_max)


def test_la_escalera_rotula_su_eje_con_fechas(captura):
    _ts, m, ep = _base_con_suceso()
    describe_escalera(escalera_de_ockham(m, ep))
    txt = captura[-1]
    fechas = [t for t in txt if t.startswith("Q") and "/20" in t]
    assert fechas, f"la escalera sigue sin fechas en el eje: {txt}"
    assert "observation" not in " ".join(txt).lower()


def test_la_superposicion_rotula_su_eje_con_fechas_y_el_titulo_tambien(captura):
    _ts, m, ep = _base_con_suceso()
    r = np.asarray(m._result.residuals, dtype=float)
    describe_superposicion(r.tolist(), at=int(ep.inicio), omega=[9.0], d=0,
                           freq=4, start=(2004, 1), desfase=0)
    txt = captura[-1]
    assert any(t.startswith("Q") and "/20" in t for t in txt), txt
    # el título dice CUÁNDO, no un índice
    assert any("Overlay around Q" in t for t in txt), txt


def test_sin_calendario_la_superposicion_sigue_hablando_de_observaciones(captura):
    """El contrato de la lista pelada. `describe_superposicion` acepta un
    `observado` sin fecha —los tests y los usos sueltos lo pasan así— y ahí lo
    honrado es decir «observation», no fabricar un calendario."""
    _ts, m, ep = _base_con_suceso()
    r = np.asarray(m._result.residuals, dtype=float)
    describe_superposicion(r.tolist(), at=int(ep.inicio), omega=[9.0], d=0)
    txt = " ".join(captura[-1])
    assert "observation" in txt.lower()
    assert "Q1/20" not in txt
