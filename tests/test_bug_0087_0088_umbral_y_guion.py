"""BUG-0087 y BUG-0088 — dos defectos de la sesión FOOD_UEM (escalera Ucrania).

**0087.** `check_intervention_fit` aplicaba la regla de Treadway —«un vecino
anómalo es evidencia de que la representación elegida es errónea»— con el umbral
de los anómalos SUELTOS (3.0), no con el de la regla (>2σ). Quedaba un punto
ciego en (2, 3)σ: los tres peldaños de Ucrania dejaban el vecino a 2.37 / 2.39 /
2.18σ y los tres se daban por exitosos.

**0088.** `estimate_and_diagnose` persistía `.pre`/`.out` —su docstring lo
prometía con esas palabras— y no el guion, que está declarado obligatorio. El
guion se desincronizaba en silencio.
"""
import inspect
import json
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.interventions import InterventionFitCheck, check_intervention_fit
from art.pipeline import _RESCALE_FACTOR, _write_inp
from art.policy import THRESHOLDS


def _chk(z_despues, umbral):
    return InterventionFitCheck(
        itv_index=0, itv_type="step", at_0based=243, fechas=[243],
        z_en_fechas=[0.0], z_antes=1.34, z_despues=z_despues,
        umbral_vecino=umbral, umbral_absorcion=1.5)


# ═══════════════ BUG-0087 — el umbral del vecino ═══════════════

def test_el_umbral_del_vecino_esta_en_la_politica():
    """Estaba clavado en tres sitios con tres números distintos —3.0 en la
    escalera, 3.0 en el check, 2.5 en las configuraciones— y ninguno era el de
    la regla. Es una decisión del método: vive en `policy`."""
    assert THRESHOLDS["intervention_vecino"] == 2.0


def test_el_default_efectivo_no_deja_punto_ciego():
    """Lo que importa es el umbral que se APLICA, no el literal de la firma."""
    firma = inspect.signature(check_intervention_fit).parameters["umbral_vecino"]
    assert firma.default is None
    assert THRESHOLDS["intervention_vecino"] <= 2.0


@pytest.mark.parametrize("z", [2.3664, 2.3896, 2.1763])
def test_el_vecino_de_ucrania_ya_no_pasa(z):
    """Los tres peldaños de FOOD_UEM 4/2022, medidos."""
    c = _chk(z, THRESHOLDS["intervention_vecino"])
    assert not c.funciona
    assert c.vecino_anomalo == "después"


def test_un_vecino_tranquilo_sigue_siendo_tranquilo():
    """Bajar el umbral no puede convertir cualquier cosa en anómalo: bajo ruido
    blanco un |z|>2 en una posición concreta pasa el 4,6% de las veces, y ése es
    el precio que se acepta a cambio de no perder la forma."""
    assert _chk(1.1, THRESHOLDS["intervention_vecino"]).funciona


def test_ya_no_quedan_defaults_literales():
    import pathlib
    for f in ("src/art/interventions.py", "src/art/escalera.py",
              "src/art/configuracion.py", "src/art/mcp_server.py"):
        t = pathlib.Path(f).read_text()
        for pat in ("umbral_vecino: float = 3.0", "umbral_vecino: float = 2.5",
                    "umbral_vecino=3.0", "umbral_vecino=2.5"):
            assert pat not in t, f"{f} conserva {pat}"


def test_el_analista_puede_seguir_declarandolo(tmp_path):
    """La política es el defecto, no una imposición."""
    assert _chk(2.37, 3.0).funciona
    assert not _chk(2.37, 2.0).funciona


def test_la_escalera_usa_el_umbral_de_la_politica():
    """`umbral_vecino=0` significa «el de la política», el mismo idioma que
    `ventana=0` en este nodo."""
    from _fuente import fuente_de
    from art.escalera import escalera_de_ockham
    src = fuente_de(escalera_de_ockham)
    assert "umbral_vecino: float = 0.0" in src
    assert "umbral_vecino or None" in src


# ═══════════════ BUG-0088 — el guion de la vía limpia ═══════════════

@pytest.fixture
def base(tmp_path):
    rng = np.random.default_rng(4)
    y = np.cumsum(rng.standard_normal(80) * 0.3) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="R88")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
    f = str(tmp_path / "R88.inp")
    _write_inp(ts, m, f)
    return f, str(tmp_path)


def _ed(*a, **k):
    fn = getattr(srv.estimate_and_diagnose, "fn", srv.estimate_and_diagnose)
    return "\n".join(getattr(c, "text", "") for c in fn(*a, **k))


def test_con_output_path_escribe_tambien_el_guion(base):
    f, d = base
    _ed(f, os.path.join(d, "R88_m00.inp"))
    g = os.path.join(d, "R88_guion.json")
    assert os.path.exists(g), "artefactos sin registro"
    with open(g) as fh:
        assert json.load(fh)["entries"]


def test_el_guion_se_deriva_si_no_se_da(base):
    """El guion es obligatorio, no opcional: no hace falta pedirlo."""
    f, d = base
    _ed(f, os.path.join(d, "R88_m01.inp"))
    assert os.path.exists(os.path.join(d, "R88_guion.json"))


def test_sin_output_path_no_escribe_nada(base):
    """Sin artefactos no hay nada que registrar: sigue siendo sólo pantalla."""
    f, d = base
    _ed(f)
    assert not [x for x in os.listdir(d) if x.endswith("guion.json")]


def test_acepta_la_decision_como_confirm_and_estimate(base):
    f, d = base
    _ed(f, os.path.join(d, "R88_m02.inp"),
        guion_decision="modelo base sin ARMA",
        guion_rationale="punto de partida")
    with open(os.path.join(d, "R88_guion.json")) as fh:
        e = json.load(fh)["entries"][0]
    assert e["decision"] == "modelo base sin ARMA"
    assert e["rationale"] == "punto de partida"


def test_respeta_un_guion_path_explicito(base, tmp_path):
    f, d = base
    otro = str(tmp_path / "sub" / "mio.json")
    os.makedirs(os.path.dirname(otro), exist_ok=True)
    _ed(f, os.path.join(d, "R88_m03.inp"), guion_path=otro)
    assert os.path.exists(otro)


def test_dos_llamadas_encadenan_versiones(base):
    f, d = base
    _ed(f, os.path.join(d, "R88_m00.inp"))
    _ed(f, os.path.join(d, "R88_m01.inp"))
    with open(os.path.join(d, "R88_guion.json")) as fh:
        assert len(json.load(fh)["entries"]) == 2


def test_las_dos_vias_exponen_los_mismos_parametros_de_guion():
    """La paridad que el docstring ya prometía para los artefactos."""
    def ps(n):
        fn = getattr(getattr(srv, n), "fn", getattr(srv, n))
        return {p for p in inspect.signature(fn).parameters
                if p.startswith("guion_")}
    assert ps("estimate_and_diagnose") == ps("confirm_and_estimate")


def test_si_el_registro_falla_se_dice(base, monkeypatch):
    """Documentar no puede tumbar una estimación válida — pero tampoco puede
    fallar en silencio, que es el defecto que este arreglo cierra."""
    f, d = base

    def revienta(**kw):
        raise RuntimeError("disco lleno")

    monkeypatch.setattr(srv, "_record_to_guion", revienta)
    t = _ed(f, os.path.join(d, "R88_m04.inp"))
    assert "guion NO registrado" in t
    assert "MODELO ESTIMADO" in t or "Diagnosis" in t


# ═══════ el umbral, dicho como el contraste que es (BUG-0089 §1) ═══════

def test_el_umbral_es_el_contraste_al_5_por_ciento():
    """No es una convención heredada: `z=2` es `χ²(1)=4`, p=0.0455.

    La condición de primer orden deja los residuos ortogonales a los regresores
    filtrados de la intervención, así que preguntar si queda masa del suceso en
    el vecino es el contraste de puntuación de un ω más. Sin ARMA el regresor
    filtrado es una FICTICIA y el estadístico colapsa en `z²`.
    """
    from scipy import stats
    z = THRESHOLDS["intervention_vecino"]
    assert abs(stats.chi2.sf(z * z, 1) - 0.0455) < 0.001


def test_se_publica_el_p_valor_del_vecino():
    """«2.37 pasa de 2.0» dice menos que «p=0.018»."""
    c = _chk(2.3664, THRESHOLDS["intervention_vecino"])
    assert c.p_vecino is not None
    assert 0.01 < c.p_vecino < 0.03
    assert "p=" in c.summary()
    assert "un ω más" in c.summary()


def test_el_p_valor_no_cambia_ningun_veredicto():
    """Es información, no una puerta más abierta: `vecino_anomalo` se sigue
    decidiendo por el umbral."""
    for z, esperado in ((1.1, True), (2.37, False)):
        c = _chk(z, THRESHOLDS["intervention_vecino"])
        assert c.funciona is esperado


def test_el_p_valor_es_coherente_con_el_umbral():
    """Justo en el umbral, el p tiene que ser el del umbral."""
    from scipy import stats
    u = THRESHOLDS["intervention_vecino"]
    c = _chk(u + 1e-9, u)
    assert abs(c.p_vecino - stats.chi2.sf(u * u, 1)) < 1e-6


def test_se_toma_el_PEOR_de_los_dos_vecinos():
    c = InterventionFitCheck(
        itv_index=0, itv_type="step", at_0based=10, fechas=[10],
        z_en_fechas=[0.0], z_antes=-2.8, z_despues=0.3,
        umbral_vecino=2.0, umbral_absorcion=1.5)
    from scipy import stats
    assert abs(c.p_vecino - stats.chi2.sf(2.8 ** 2, 1)) < 1e-9


def test_sin_vecinos_no_hay_p():
    c = InterventionFitCheck(
        itv_index=0, itv_type="step", at_0based=0, fechas=[0],
        z_en_fechas=[0.0], z_antes=None, z_despues=None,
        umbral_vecino=2.0, umbral_absorcion=1.5)
    assert c.p_vecino is None


# ═══════ BUG-0089 §1 — la nota del ARMA es información, no norma ═══════

def test_se_detecta_si_el_modelo_lleva_arma():
    from art.interventions import _lleva_arma

    class _M:
        ar = [[0.3]]
        ma = ar_s = ma_s = None

    class _N:
        ar = ma = ar_s = ma_s = None

    assert _lleva_arma(_M())
    assert not _lleva_arma(_N())


def test_con_arma_se_dice_que_el_p_es_conservador():
    """Sin ARMA el residuo del vecino ES el contraste exacto; con ARMA el
    regresor filtrado deja de ser una ficticia y se pierde potencia (75% → 47%,
    medido). Es una razón para intervenir antes del ARMA, no una obligación:
    el analista decide."""
    c = InterventionFitCheck(
        itv_index=0, itv_type="step", at_0based=10, fechas=[10],
        z_en_fechas=[0.0], z_antes=1.2, z_despues=0.4,
        umbral_vecino=2.0, umbral_absorcion=1.5, con_arma=True)
    t = c.summary()
    assert "CONSERVADOR" in t
    assert "75%" in t and "47%" in t


def test_sin_arma_no_se_añade_la_nota():
    c = InterventionFitCheck(
        itv_index=0, itv_type="step", at_0based=10, fechas=[10],
        z_en_fechas=[0.0], z_antes=1.2, z_despues=0.4,
        umbral_vecino=2.0, umbral_absorcion=1.5, con_arma=False)
    assert "CONSERVADOR" not in c.summary()


def test_la_nota_no_manda_nada():
    """Registro: es información para decidir, no una regla. No dice «hay que»
    ni «la escuela exige» — dice qué vale el número aquí y qué valdría allá."""
    c = InterventionFitCheck(
        itv_index=0, itv_type="step", at_0based=10, fechas=[10],
        z_en_fechas=[0.0], z_antes=1.2, z_despues=0.4,
        umbral_vecino=2.0, umbral_absorcion=1.5, con_arma=True)
    t = c.summary().lower()
    for imperativo in ("hay que", "debes", "tienes que", "obligat"):
        assert imperativo not in t
    assert "no invalida el veredicto" in t


def test_la_nota_no_cambia_el_veredicto():
    def hecho(con):
        return InterventionFitCheck(
            itv_index=0, itv_type="step", at_0based=10, fechas=[10],
            z_en_fechas=[0.0], z_antes=2.4, z_despues=0.4,
            umbral_vecino=2.0, umbral_absorcion=1.5, con_arma=con)
    assert hecho(True).funciona == hecho(False).funciona
    assert hecho(True).p_vecino == hecho(False).p_vecino
