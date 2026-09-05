"""BUG-0093 y BUG-0096 — dos defectos del nodo de intervención, ambos de UNIDADES.

**0093.** `guided_intervention` documentaba `n_omega` como «orden del numerador
ω(B)» y el parámetro cuenta COEFICIENTES. Su Call 3 informaba además «de orden ω
{n_omega−1}», reforzando la lectura falsa. Un analista al que Treadway le
ordenaba subir de peldaño pasaba `n_omega=1` creyendo pedir la escalera de dos y
recibía un escalón simple. No se le ignoraba: se le había documentado otra cosa.

Gana la semántica de CONTAR, porque es la de las otras cuatro piezas del nodo:
`suggest_intervention_form`, `incident_configurations`, la escalera y la propia
Call 2, que devuelve el `n_omega` listo para pegar.

**0096.** El vecino sub-umbral no decía nada. Ahora hay una NOTA, con tres
restricciones que son la decisión del analista y no la petición del reporte: la
regla de Treadway **sigue en 2σ**, la nota sale **sólo con ARMA**, y **no entra
en `razones_para_subir`** — porque bajo la nula un |z|>1.5 pasa el 13% de las
veces y la sobre-intervención no se detiene sola.
"""
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.interventions import InterventionFitCheck
from art.pipeline import _RESCALE_FACTOR, _load_ts_model, _write_inp
from art.policy import THRESHOLDS

GI = getattr(srv.guided_intervention, "fn", srv.guided_intervention)


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    d = tmp_path_factory.mktemp("b9396")
    rng = np.random.default_rng(17)
    y = np.cumsum(rng.standard_normal(120) * 0.4) + 100.0
    y[60] += 5.0
    y[61] += 3.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1995, 1), name="R93")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
    f = str(d / "R93.inp")
    _write_inp(ts, m, f)
    return f, str(d)


def _gi(*a, **k):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return "\n".join(getattr(c, "text", "") for c in GI(*a, **k))


# ═══════════════ BUG-0093 — una sola semántica ═══════════════

@pytest.mark.parametrize("k", [1, 2, 3])
def test_n_omega_cuenta_escalones(base, k):
    f, d = base
    out = os.path.join(d, f"k{k}.inp")
    _gi(f, date="Q1/2010", form="step", n_omega=k, output_path=out)
    _, m = _load_ts_model(out)
    itv = [i for i in m.interventions if i.type == "step"][-1]
    assert len(itv.omega) == k


@pytest.mark.parametrize("k", [1, 2, 3])
def test_la_cabecera_habla_en_ESCALONES(base, k):
    """La lengua del nodo. Informar en «orden» es lo que enseñó al analista la
    semántica equivocada."""
    f, d = base
    t = _gi(f, date="Q1/2010", form="step", n_omega=k,
            output_path=os.path.join(d, f"c{k}.inp"))
    cab = next(l for l in t.split("\n") if "Se construye" in l)
    assert f"{k} escalón(es)" in cab
    assert f"orden {k - 1}" in cab, "el orden se dice, pero entre paréntesis"


def test_el_docstring_ya_no_documenta_lo_contrario():
    import inspect
    d = inspect.getdoc(GI) or ""
    i = d.index("n_omega")
    entrada = d[i:i + 400]
    assert "cuántos ω" in entrada or "cuántos escalones" in entrada
    assert "orden del numerador" not in entrada


def test_la_equivalencia_esta_escrita():
    """Para quien venga del operador: N escalones ⇔ ω(B) de orden N−1."""
    import inspect
    d = inspect.getdoc(GI) or ""
    assert "orden N−1" in d or "orden N-1" in d


def test_el_bucle_se_cierra(base):
    """Lo que la Call 2 sugiere, la Call 3 lo construye. Es la prueba de
    aceptación: sigue el consejo de la herramienta y obtienes lo que pediste."""
    import re
    f, d = base
    t2 = _gi(f, date="Q1/2010", threshold=2.5)
    m = re.search(r"n_omega=(\d+)", t2)
    assert m, "la Call 2 no sugiere n_omega"
    n = int(m.group(1))
    out = os.path.join(d, "cierre.inp")
    _gi(f, date="Q1/2010", form="step", n_omega=n, output_path=out)
    _, mm = _load_ts_model(out)
    assert len([i for i in mm.interventions if i.type == "step"][-1].omega) == n


# ═══════════════ BUG-0096 — la nota, con sus tres restricciones ═══════════════

def _chk(z, arma):
    return InterventionFitCheck(
        itv_index=0, itv_type="step", at_0based=243, fechas=[243],
        z_en_fechas=[0.0], z_antes=0.19, z_despues=z,
        umbral_vecino=THRESHOLDS["intervention_vecino"], umbral_absorcion=1.5,
        con_arma=arma, umbral_cola=THRESHOLDS["intervention_cola_activa"])


def test_la_nota_sale_con_arma():
    assert _chk(-1.60, True).cola_activa == "después"


def test_la_nota_NO_sale_sin_arma():
    """Sin ARMA el residuo crudo del vecino ES el contraste exacto, así que un
    vecino sub-umbral es exactamente lo que dice ser: ruido."""
    assert _chk(-1.60, False).cola_activa is None


@pytest.mark.parametrize("z", [-1.60, -1.90, 1.55])
def test_la_REGLA_de_treadway_no_cambia(z):
    """2σ, con ARMA y sin él. La nota es una nota."""
    for arma in (True, False):
        c = _chk(z, arma)
        assert c.funciona
        assert c.vecino_anomalo is None


def test_la_regla_sigue_disparando_a_2_sigma():
    c = _chk(-2.40, True)
    assert not c.funciona
    assert c.vecino_anomalo == "después"
    assert c.cola_activa is None, "por encima de 2σ manda la regla, no la nota"


def test_la_banda_arranca_en_1_5_no_en_1_0():
    """El número lo decide la nula: a 1.0σ la nota saldría en un tercio de las
    intervenciones y no diría nada (p=0.317, uno de cada 3)."""
    assert THRESHOLDS["intervention_cola_activa"] == 1.5
    assert _chk(-1.40, True).cola_activa is None
    assert _chk(-1.20, True).cola_activa is None


def test_el_aviso_dice_cuan_probable_es_que_sea_ruido():
    """Sin la probabilidad, una nota se lee como un hallazgo."""
    t = _chk(-1.60, True).summary()
    assert "13%" in t or "13 %" in t
    assert "nula" in t and "nota" in t.lower()


def test_la_nota_no_entra_en_las_razones_para_subir():
    """La restricción que impide que esto abra la puerta a sobre-intervenir."""
    from tests._fuente import fuente_de
    from art.escalera import escalera_de_ockham
    assert "cola_activa" not in fuente_de(escalera_de_ockham)


def test_la_escalera_la_publica_como_nota():
    from tests._fuente import fuente_de
    from art.escalera import describe_escalera
    src = fuente_de(describe_escalera)
    assert "cola_activa" in src
    assert "no razón para subir" in src


def test_el_umbral_de_la_nota_vive_en_la_politica():
    """Lección de BUG-0087: un umbral repartido en literales es cuatro
    umbrales."""
    from tests._fuente import fuente_de
    from art.interventions import check_intervention_fit
    src = fuente_de(check_intervention_fit)
    assert "intervention_cola_activa" in src
    assert "1.5" not in src.replace("umbral_absorcion: float = 1.5", "")
