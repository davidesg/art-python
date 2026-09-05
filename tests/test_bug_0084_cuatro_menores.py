"""BUG-0084 — cuatro defectos menores de la sesión guiada sobre FOOD_UEM.

§1 σ̂ salía ×100 en la figura de residuos y no en la ecuación.
§2 el R² de `intervention_plot` se diluía con el ruido de la ventana.
§3 `confirm_and_estimate` no creaba su directorio de salida.
§4 la escalera decía que subió de peldaño mientras elegía el más bajo.
"""
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.pipeline import _RESCALE_FACTOR, _write_inp


# ═══════════════ §1 — la σ̂ de la figura de residuos ═══════════════

def test_los_residuos_van_a_pyfug_en_fraccion():
    """`pyfug` rotula multiplicando por 100, lo que es correcto si recibe una
    FRACCIÓN. Los residuos de la suite vienen en 100·log, así que ya están en
    tanto por ciento: el ×100 los dejaba cien veces más grandes.

    Sobre FOOD_UEM, el mismo modelo y el mismo número: la ecuación decía
    σ̂ₐ=0.2124%, el `.out` 0.212417, y la figura σ̂_w=21.24%.
    """
    from art.describe import _residuos_en_fraccion

    class _M:
        refactor = 100.0

        class residuals:
            data = [1.0, -2.0, 3.0]

    assert list(_residuos_en_fraccion(_M())) == [0.01, -0.02, 0.03]


def test_sin_refactor_no_se_toca_nada():
    from art.describe import _residuos_en_fraccion

    class _M:
        refactor = 1.0

        class residuals:
            data = [1.0, -2.0]

    assert list(_residuos_en_fraccion(_M())) == [1.0, -2.0]


def test_dividir_no_cambia_el_dibujo_solo_el_rotulo():
    """`plot_combined` TIPIFICA la serie antes de pintarla, así que un factor
    constante sólo mueve el pie de figura — que es justo lo que estaba mal."""
    x = np.array([1.0, -2.0, 3.0, 0.5])
    z1 = (x - x.mean()) / x.std(ddof=0)
    y = x / 100.0
    z2 = (y - y.mean()) / y.std(ddof=0)
    assert np.allclose(z1, z2)


# ═══════════════ §2 — el R² de la superposición ═══════════════

def _serie_con_episodio(n=120, at=60, seed=2):
    """Ruido limpio, un episodio de dos períodos, y OTRO anómalo lejos."""
    rng = np.random.default_rng(seed)
    y = rng.standard_normal(n) * 0.2
    y[at - 1] += 3.0
    y[at] += -1.5
    y[at - 12] += 3.4          # ajeno al suceso, dentro de la ventana ±12
    return y


def test_el_r2_del_soporte_es_mayor_que_el_de_la_ventana():
    """El ruido ordinario de la ventana pone un techo al R² por perfecto que
    sea el ajuste EN el incidente."""
    from art.ltf import superpone
    y = _serie_con_episodio()
    sp = superpone(y, at=60, omega=[3.0, 1.5], d=0, ventana=12)
    assert sp.r2_soporte > sp.r2


def test_el_soporte_incluye_un_vecino_a_cada_lado():
    """Y no es un margen de cortesía: es la regla de Treadway — lo que la forma
    no modeliza cae entero en el vecino, así que tiene que entrar en la
    medida."""
    import inspect

    from art import ltf
    from _fuente import fuente_de
    src = fuente_de(ltf.superpone)
    assert "at - 1" in src and "fin_sop + 1" in src


def test_se_señala_cuando_el_mayor_resto_es_ajeno_al_suceso():
    """En 12/2004 el mayor resto de la ventana era OTRO anómalo conocido, siete
    meses después. Cargárselo a la hipótesis que se prueba es un error de
    atribución."""
    from art.ltf import superpone
    y = _serie_con_episodio()
    sp = superpone(y, at=60, omega=[3.0, 1.5], d=0, ventana=12)
    assert sp.el_resto_grande_es_ajeno
    assert sp.resto_max_en != 0


def test_el_veredicto_se_lee_sobre_el_soporte():
    from art.ltf import Superposicion
    sp = Superposicion(k=np.arange(1, 4), observado=np.zeros(3),
                       simulado=np.zeros(3), resto=np.zeros(3), at=2,
                       escala=1.0, r2=0.30, z_resto=2.9, sd=1.0,
                       entrada="escalon", r2_soporte=0.95,
                       z_resto_soporte=0.4, resto_max_en=5)
    assert sp.la_forma_explica, "el veredicto sigue leyendo la ventana"


def test_el_informe_publica_los_dos_r2():
    """La ventana está para MIRARLA: su R² se sigue dando, pero etiquetado."""
    from art.ltf import describe_superposicion
    d = describe_superposicion(_serie_con_episodio(), at=60,
                               omega=[3.0, 1.5], d=0, ventana=12)
    assert "SOPORTE" in d.summary
    assert "r2_soporte" in d.data and "r2" in d.data


# ═══════════════ §3 — el directorio de salida ═══════════════

def test_write_inp_crea_su_directorio(tmp_path):
    """La ruta que el propio nodo guiado sugiere es `cases/<serie>/work/…`, que
    todavía no existe: la PRIMERA llamada del ciclo reventaba sobre una ruta que
    art acababa de proponer."""
    ts = fue.TimeSeries([float(x) for x in range(40)], freq=4,
                        start=(2000, 1), name="S")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                  refactor=_RESCALE_FACTOR)
    destino = tmp_path / "cases" / "S" / "work" / "S_m00.inp"
    _write_inp(ts, m, str(destino))
    assert destino.exists()


def test_write_inp_sin_directorio_en_la_ruta(tmp_path, monkeypatch):
    """Un nombre a secas no puede romper por intentar crear "" como directorio."""
    monkeypatch.chdir(tmp_path)
    ts = fue.TimeSeries([float(x) for x in range(40)], freq=4,
                        start=(2000, 1), name="S")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                  refactor=_RESCALE_FACTOR)
    _write_inp(ts, m, "suelto.inp")
    assert (tmp_path / "suelto.inp").exists()


# ═══════════════ §4 — el mensaje de la escalera ═══════════════

def _escalera(rec, razones):
    from art.escalera import Escalera, Peldano
    ps = [Peldano(nivel=n, nombre=f"peldaño {n}", tipo="step", n_omega=1,
                  model=object(), aic=-100.0, omega_1=0.5, wald_p=0.3,
                  q_pass=False, jb_pass=False)
          for n in ("1a", "1b", "2")]
    return Escalera(peldanos=ps, episodio=None, dominio="generic",
                    razones_para_subir=razones, recomendado=rec,
                    pregunta_extramuestral="¿?", nivel_simple="1a",
                    criterio_simple="por la firma")


def test_subio_es_falso_cuando_se_elige_el_peldano_bajo():
    assert not _escalera("1a", ["**Inadecuación**: …"]).subio
    assert _escalera("2", ["**Inadecuación**: …"]).subio


def test_ningun_peldano_se_sostiene_nombra_el_estado():
    """Es el estado que el mensaje contradictorio ocultaba, y el que el analista
    necesita saber: no es que se haya elegido bien."""
    assert _escalera("1a", ["**Inadecuación**: …"]).ningun_peldano_se_sostiene
    assert not _escalera("2", ["**Inadecuación**: …"]).ningun_peldano_se_sostiene
    assert not _escalera("1a", []).ningun_peldano_se_sostiene


def test_el_texto_no_dice_que_subio_si_eligio_el_bajo():
    """Salida literal del reporte: marcaba `1a` como elegido —el más bajo— y a
    continuación afirmaba «Se subió de peldaño por: …». O el mensaje describía
    una evaluación que no se aplicó, o la elección no era la que decía."""
    import art.mcp_server as srv
    esc = _escalera("1a", ["**Inadecuación**: no deja ruido blanco."])
    t = srv._texto_escalera(esc, "1a")
    assert "Se subió de peldaño por" not in t
    assert "aun así se recomienda" in t
    assert "ninguna forma de esta escalera resuelve el suceso" in t


def test_el_texto_si_dice_que_subio_cuando_subio():
    import art.mcp_server as srv
    esc = _escalera("2", ["**Inadecuación**: no deja ruido blanco."])
    t = srv._texto_escalera(esc, "2")
    assert "Se subió de peldaño por" in t


def test_sin_razones_el_mensaje_de_siempre():
    import art.mcp_server as srv
    t = srv._texto_escalera(_escalera("1a", []), "1a")
    assert "No hubo razón para subir" in t


def test_una_hipotesis_CORTA_se_mide_contra_todo_el_suceso():
    """La trampa del soporte propio, encontrada al correr la suite.

    Si el R² se mide sobre el soporte de la HIPÓTESIS, una hipótesis demasiado
    corta sale bien parada porque mira muy poco: un escalón de un solo ω sobre
    un episodio de tres períodos miraba tres puntos y sacaba R²=0.80, cuando la
    lectura honrada es que esa forma no es.

    Así que el soporte arranca en el de la hipótesis y se extiende mientras lo
    OBSERVADO siga activo (|y| ≥ 1σ). La forma corta queda medida contra todo el
    suceso, que es lo que tiene que explicar.
    """
    from art.ltf import superpone
    r = np.random.default_rng(3).standard_normal(120)
    r[59] += 9.0
    r[60] += -3.0
    r[61] += -6.0                      # dos impulsos de nivel vistos en ∇
    corta = superpone(r, at=60, omega=[1.0], d=1, ventana=6)
    buena = superpone(r, at=60, omega=[9.0, 3.0, 6.0], d=1, ventana=6)
    assert not corta.la_forma_explica
    assert corta.r2_soporte < 0.70
    assert buena.la_forma_explica
    # y separa mejor que la ventana: 0.975 vs 0.608 frente a 0.887 vs 0.559
    assert (buena.r2_soporte - corta.r2_soporte) > (buena.r2 - corta.r2)
