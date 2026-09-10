"""BUG-0150 — las configuraciones y la escalera tiraban las intervenciones del base.

`evalua_configuraciones` y `escalera_de_ockham` filtraban las intervenciones del
modelo base quedándose sólo con `cos`, `sin` y `alter`. El docstring prometía
«el modelo ajustado SIN la intervención» —la que se estudia— y el código hacía
algo más fuerte: **sin NINGUNA**.

Las dos cosas coinciden en la PRIMERA intervención de una serie, que es donde se
escribió y se probó. Con la segunda ya no, y entonces cada candidato se evalúa
contra un modelo que no es el del analista.

El síntoma es visible sin saber nada del código: sobre ITCER, la llamada 2 en
Q2/2009 sobre un base que ya llevaba la caída de 2008 daba los tres candidatos
en AIC ≈396 cuando el propio base estaba en **381,93**. Añadir un parámetro
«empeoraba» el ajuste, que es imposible.
"""
import numpy as np
import pytest

fue = pytest.importorskip("fue")
from art.configuracion import arranques_candidatos, evalua_configuraciones
from art.escalera import escalera_de_ockham, hereda_del_base
from art.episodes import agrupa_episodios


def _base(n=120, semilla=5):
    """Un modelo con UNA intervención ya estimada y un segundo suceso fuera.

    Las magnitudes están elegidas para que el defecto se vea por su SÍNTOMA y
    no sólo por el recuento: el escalón de 2010 explica mucho más que el pico
    de 2020, así que perderlo hunde el ajuste del candidato y su AIC sale POR
    ENCIMA del base. Con un escalón pequeño el candidato mejora igualmente y la
    inversión no aparece — que es justo por qué esto sobrevivió: en la primera
    intervención de una serie no hay nada que perder.
    """
    rng = np.random.default_rng(semilla)
    y = np.cumsum(rng.standard_normal(n)) * 0.4 + 100.0
    y[40:] -= 25.0                      # suceso 1: escalón permanente, GRANDE
    y[80] += 6.0                        # suceso 2: el que se va a estudiar
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="X")
    itv = fue.Intervention("step", at=40, omega=[0.0], omega_free=[True])
    m = fue.Model(ts, d=1, boxlam=1.0, mu=0.0, estimate_mu=False,
                  interventions=[itv])
    m.fit()
    return ts, m


def _episodio(m):
    r = np.asarray(m._result.residuals, dtype=float)
    z = r / r.std(ddof=0)
    ext = [(i + 1, float(z[i])) for i in range(len(z)) if abs(z[i]) > 2.5]
    grupos = agrupa_episodios(ext, ventana=2, d=m.d)
    assert grupos, "el caso tiene que dejar un episodio"
    ep = max(grupos, key=lambda e: e.z_max)
    idx = [i - 1 for i, _v in ext if ep.inicio <= i <= ep.fin]
    return ep, z, idx


# ────────── el reparto, aislado ──────────

def test_hereda_las_intervenciones_de_suceso_del_base():
    _ts, m = _base()
    hereda, retira = hereda_del_base(m, at_estudiado=80, ventana=2)
    assert len(hereda) == 1, "se ha tirado la intervención de 2008"
    assert hereda[0].at == 40
    assert not retira


def test_retira_SOLO_la_que_cae_sobre_el_mismo_suceso():
    """El caso legítimo: rehacer la forma de un suceso ya intervenido."""
    _ts, m = _base()
    hereda, retira = hereda_del_base(m, at_estudiado=40, ventana=2)
    assert not hereda, hereda
    assert len(retira) == 1 and retira[0].at == 40


def test_la_estructura_estacional_sobrevive_siempre():
    ts = fue.TimeSeries(list(np.random.default_rng(1).standard_normal(120)),
                        freq=4, start=(2000, 1), name="X")
    itvs = [fue.Intervention("cos", at=0, omega=[0.0], omega_free=[True]),
            fue.Intervention("alter", at=0, omega=[0.0], omega_free=[True]),
            fue.Intervention("step", at=40, omega=[0.0], omega_free=[True])]
    m = fue.Model(ts, d=1, boxlam=1.0, mu=0.0, estimate_mu=False,
                  interventions=itvs)
    hereda, retira = hereda_del_base(m, at_estudiado=40, ventana=1)
    assert {i.type for i in hereda} == {"cos", "alter"}
    assert [i.type for i in retira] == ["step"]


# ────────── LA prueba: el candidato no puede empeorar el base ──────────

def test_cada_candidato_MEJORA_el_base_y_lleva_sus_intervenciones():
    """Añadir un parámetro a un modelo anidado no puede subir la verosimilitud
    a peor. Si el AIC del candidato sale por encima del base, es que se está
    comparando contra otro modelo."""
    _ts, m = _base()
    ep, z, idx = _episodio(m)
    cands = arranques_candidatos(z, idx, d=m.d)
    conj = evalua_configuraciones(m, cands, d=m.d, freq=4,
                                  start_year=2000, start_per=1)
    vivos = [c for c in conj.vivos if c.aic is not None]
    assert vivos, "ningún candidato se estimó"
    for c in vivos:
        assert len(c.model.interventions or []) == 2, (
            f"{c.etiqueta}: el candidato lleva "
            f"{len(c.model.interventions or [])} intervenciones, no 2 — se ha "
            f"perdido la del base")
        assert c.aic < m.aic, (
            f"{c.etiqueta}: AIC {c.aic:.2f} PEOR que el base {m.aic:.2f}; "
            f"añadir un parámetro no puede empeorar un modelo anidado. Es el "
            f"síntoma exacto del defecto: sin el arreglo este caso daba 537,52 "
            f"contra un base de 304,05, y sobre ITCER 396 contra 381,93")


def test_la_escalera_tambien_hereda():
    _ts, m = _base()
    ep, _z, _idx = _episodio(m)
    esc = escalera_de_ockham(m, ep)
    vivos = [p for p in esc.peldanos if p.estimado]
    assert vivos, "ningún peldaño se estimó"
    for p in vivos:
        assert len(p.model.interventions or []) >= 2, (
            f"peldaño {p.nivel}: perdió la intervención del base")
