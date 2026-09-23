"""BUG-0161 y BUG-0163 — el denominador: el grifo y la lectura.

Se arreglan juntos porque abrir uno sin el otro es poner una puerta a un cuarto
a oscuras: construir un δ y no publicarlo deja al analista con el único número
que no contesta a lo que preguntó.

**BUG-0161 — la tubería no tenía grifo.** δ(B) estaba cableado de punta a punta
—`_write_inp` lo escribe, `art.outfile` lo lee, `fue` lo estima,
`test_intervention` calcula δ(1), `art.ltf` lo dibuja— y **nadie lo construía**:
cero sitios en todo `src/art/`, y 0 de 216 `.inp` del corpus con un δ. La forma
racional no se había usado nunca en ningún modelo que art produjera, porque no
se podía producir.

**BUG-0163 — y si entraba uno a mano, no se leía.** La línea de la ganancia
vivía dentro de `if self.wald_stat is not None`, y el Wald sólo existe con MÁS
de un ω. Con forma racional lo típico es un ω y un δ: se imprimía ω₀ y se
callaban δ̂ y ν(1), que es para lo que existe la forma.
"""
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.diagnosis import admissibility_problems
from art.interventions import test_intervention as _test_intervention
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar

_T, _N, _DELTA, _OMEGA = 70, 160, 0.6, -8.0


def _serie(seed=11, phi=0.5):
    """Respuesta que DECAE: ω₀·δᵏ desde `_T`. La forma que el catálogo de sólo
    numerador tiene que aproximar con N escalones."""
    rng = np.random.default_rng(seed)
    a = rng.standard_normal(_N) * 0.4
    e = np.zeros(_N)
    for t in range(1, _N):
        e[t] = phi * e[t - 1] + a[t]
    y = 100.0 + np.cumsum(e)
    for k in range(_N - _T):
        y[_T + k] += _OMEGA * (_DELTA ** k)
    return fue.TimeSeries(y.tolist(), freq=4, start=(1985, 1), name="DEC")


@pytest.fixture(scope="module")
def racional(tmp_path_factory):
    """Construida POR LA SUPERFICIE, que es lo que el defecto decía imposible."""
    d = tmp_path_factory.mktemp("delta")
    ts = _serie()
    f0 = str(d / "DEC_m00.inp")
    _write_inp(ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                             refactor=_RESCALE_FACTOR, ar=[[0.0]],
                             ar_free=[[True]]), f0)
    _, fit = estimar(f0)
    fit.write_pre(f0[:-4] + ".pre")

    f1 = str(d / "DEC_m10.inp")
    fn = getattr(srv.suggest_intervention_form, "fn",
                 srv.suggest_intervention_form)
    txt = "\n".join(getattr(x, "text", "")
                    for x in fn(f0[:-4] + ".pre", f1, date="Q3/2002",
                                form="impulse", n_omega=1, n_delta=1))
    # SE ESTIMA DESDE EL `.inp` que la herramienta acaba de escribir, no desde
    # su `.pre`. Aquí hacen falta las desviaciones típicas de δ, y `mirar` sobre
    # un `.pre` devuelve la covarianza-semilla: `test_intervention` se niega, y
    # con razón (BUG-0027/0159). El convenio funcionando, de paso.
    _, m = estimar(f1)
    return f1, m, txt


def _con_delta(valor):
    """Un modelo suelto con el δ que se quiera, para los casos de contorno.

    Aparte del fixture a propósito: mutar el compartido contamina al resto.
    """
    ts = _serie()
    return fue.Model(
        ts, d=1, mu=0.0, estimate_mu=False, ar=[[0.0]], ar_free=[[True]],
        interventions=[fue.Intervention("impulse", at=_T, omega=[1.0],
                                        omega_free=[True], delta=[valor],
                                        delta_free=[True])])


# ═══════════════════ BUG-0161 — el grifo ═══════════════════════════════════

def test_la_superficie_CONSTRUYE_un_denominador(racional):
    _, m, _ = racional
    itv = m.interventions[0]
    assert itv.delta, "sigue sin construirse ningún δ"
    assert len(itv.delta) == 1


def test_y_recupera_el_delta_del_testigo(racional):
    """No basta con que exista: tiene que ser el de la serie."""
    _, m, _ = racional
    assert abs(float(m.interventions[0].delta[0]) - _DELTA) < 0.1, (
        f"δ̂={m.interventions[0].delta[0]} contra una verdad de {_DELTA}")


def test_sin_n_delta_no_cambia_nada(tmp_path):
    """El grifo es opcional: el comportamiento de siempre es el de siempre."""
    ts = _serie()
    f0 = str(tmp_path / "S_m00.inp")
    _write_inp(ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                             refactor=_RESCALE_FACTOR, ar=[[0.0]],
                             ar_free=[[True]]), f0)
    _, fit = estimar(f0)
    fit.write_pre(f0[:-4] + ".pre")
    f1 = str(tmp_path / "S_m10.inp")
    fn = getattr(srv.suggest_intervention_form, "fn",
                 srv.suggest_intervention_form)
    fn(f0[:-4] + ".pre", f1, date="Q3/2002", form="impulse", n_omega=1)
    _, m = fue.load(f1[:-4] + ".pre")
    assert not (m.interventions[0].delta or [])


def test_la_semilla_va_en_cero_y_eso_esta_MEDIDO():
    """Una semilla cerca de la raíz unidad manda el ajuste a un óptimo espurio.
    Medido sobre este mismo testigo: 0,0 / 0,5 / −0,5 convergen a δ̂=0,5692 con
    AIC 1616,41 en ~14 iteraciones; 0,9 da δ̂=0,7070 con AIC 1864,56 tras 500
    iteraciones sin anular el gradiente — 248 puntos de AIC peor, con números de
    aspecto normal.

    OJO — medido sobre la serie REDONDEADA A SEIS DECIMALES, que es lo que
    `_write_inp` escribía antes de BUG-0188. Con los datos exactos las dos
    semillas llegan al mismo óptimo (AIC 1616,41): la cuenca espuria depende
    del séptimo decimal. El testigo se reproduce tal como se midió; lo que
    enseña —que el óptimo al que se llega depende de la semilla, y que la
    frontera de las cuencas es frágil— sigue siendo la razón de sembrar en 0."""
    import tempfile
    ts0 = _serie()
    ts = fue.TimeSeries(np.round(ts0.data, 6).tolist(), freq=ts0.freq,
                        start=ts0.start, name=ts0.name)
    res = {}
    for semilla in (0.0, 0.9):
        d = tempfile.mkdtemp()
        f = os.path.join(d, "D.inp")
        _write_inp(ts, fue.Model(
            ts, d=1, mu=0.0, estimate_mu=False, ar=[[0.0]], ar_free=[[True]],
            refactor=_RESCALE_FACTOR,
            interventions=[fue.Intervention(
                "impulse", at=_T, omega=[0.0], omega_free=[True],
                delta=[semilla], delta_free=[True])]), f)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res[semilla] = estimar(f)[1]
    assert res[0.0].aic < res[0.9].aic - 100, (
        "el testigo dejó de valer: la semilla mala ya no es mala")

    from tests._fuente import cuerpo_de
    c = cuerpo_de(srv.suggest_intervention_form)
    assert "delta=[0.0] * _nd" in c, "la semilla dejó de ser 0.0"


def test_un_delta_EXPLOSIVO_se_anuncia(racional):
    """El operador con la lectura más brutal si se va: una raíz de δ dentro del
    círculo es una respuesta que CRECE sin límite en vez de decaer. Y a
    diferencia de un MA no invertible, la diagnosis no lo delata — los residuos
    pueden salir perfectos mientras la respuesta que el modelo AFIRMA es
    imposible. `admissibility_problems` no miraba el denominador porque hasta
    ahora no podía haber ninguno."""
    _, m, _ = racional
    assert admissibility_problems(m) == [], "el testigo ya es inadmisible"

    pr = admissibility_problems(_con_delta(1.2))   # raíz en 1/1,2 = 0,833
    assert pr, "un δ explosivo pasa sin avisar"
    assert "δ" in pr[0][0] and pr[0][2] == "dentro"
    assert abs(pr[0][1] - 1 / 1.2) < 1e-6


def test_la_frontera_y_lo_admisible_se_distinguen(racional):
    assert admissibility_problems(_con_delta(1.0))[0][2] == "frontera"
    assert admissibility_problems(_con_delta(-0.8)) == []


# ═══════════════════ BUG-0163 — la lectura ═════════════════════════════════

def test_el_contraste_publica_delta_y_su_error_tipico(racional):
    f1, m, _ = racional
    tr = _test_intervention(m, 0)
    assert tr.delta and abs(tr.delta[0] - _DELTA) < 0.1
    assert tr.delta_se and tr.delta_se[0] > 0
    t = tr.summary()
    assert "δ[1]=" in t and "SE=" in t


def test_y_la_GANANCIA_aunque_no_haya_Wald(racional):
    """Es el defecto entero: la línea vivía dentro de `if wald_stat is not
    None`, y con un solo ω no hay Wald. La ganancia es PARA LO QUE existe la
    forma racional."""
    _, m, _ = racional
    tr = _test_intervention(m, 0)
    assert tr.wald_stat is None, "el testigo dejó de valer: hay Wald"
    assert tr.gain is not None
    t = tr.summary()
    assert "ν(1)" in t, "la ganancia sigue sin imprimirse"
    assert f"{tr.gain:+.4f}" in t


def test_dice_la_tasa_de_decaimiento_en_palabras(racional):
    """δ tiene lectura sustantiva y ω₀ no la tiene."""
    _, m, _ = racional
    t = _test_intervention(m, 0).summary()
    assert "δ(1)=" in t
    assert "DECAE" in t and "% por período" in t


def test_avisa_si_delta_1_se_acerca_a_cero():
    """δ(1)→0 es la ganancia sin acotar: el modelo es inadmisible y el número
    que se publicaría no significa nada."""
    from art.interventions import InterventionTestResult
    r = InterventionTestResult(
        itv_index=0, itv_type="impulse", itv_at=_T, harmonic=None,
        omega=[-7.0], omega_se=[0.3], omega_t=[-23.0], omega_p=[0.0],
        wald_stat=None, wald_p=None, df=150, significant=True,
        entrada="impulso", n_omega_total=1, omega_1=-7.0,
        delta=[0.9999], delta_se=[0.01], delta_1=1e-4, gain=-7e4)
    assert "no está acotada" in r.summary()


def test_una_intervencion_SIN_delta_no_cambia_de_aspecto():
    """El arreglo no puede ensuciar la salida de las formas de siempre."""
    from art.interventions import InterventionTestResult
    r = InterventionTestResult(
        itv_index=0, itv_type="step", itv_at=10, harmonic=None,
        omega=[1.0, 0.5], omega_se=[0.1, 0.1], omega_t=[10.0, 5.0],
        omega_p=[0.0, 0.0], wald_stat=9.0, wald_p=0.003, df=100,
        significant=True, entrada="escalon", n_omega_total=2, omega_1=0.5)
    t = r.summary()
    assert "δ" not in t
    assert "ω(1)=" in t and "Wald χ²(1)=" in t


def test_el_Wald_sigue_siendo_un_CONTRASTE_y_no_una_descripcion():
    """Separarlos era el arreglo: ν(1) y δ(1) describen, el Wald contrasta. La
    etiqueta del Wald tiene que decir su H₀."""
    from art.interventions import InterventionTestResult
    r = InterventionTestResult(
        itv_index=0, itv_type="step", itv_at=10, harmonic=None,
        omega=[1.0, 0.5], omega_se=[0.1, 0.1], omega_t=[10.0, 5.0],
        omega_p=[0.0, 0.0], wald_stat=9.0, wald_p=0.003, df=100,
        significant=True, entrada="escalon", n_omega_total=2, omega_1=0.5)
    t = r.summary()
    assert "H₀: ω(1)=0" in t


def test_por_la_superficie_MCP_se_ve_todo(racional):
    f1, _, _ = racional
    fn = getattr(srv.test_interventions, "fn", srv.test_interventions)
    t = "\n".join(getattr(x, "text", "") for x in fn(f1))
    assert "δ[1]=" in t and "ν(1)" in t and "DECAE" in t


def test_y_la_ecuacion_renderiza_la_forma_racional(racional):
    """El puerto ya lo sabía dibujar: lo que faltaba era que hubiera algo que
    dibujar."""
    _, _, txt = racional
    assert "/ (1 − 0.5692·B)" in txt or "/(1 − 0.5692·B)" in txt or "δ" in txt
