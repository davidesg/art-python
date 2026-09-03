"""El guion guarda los DATOS y con QUÉ se calcularon, no sólo el veredicto.

Lo destapó el analista mirando el mapa: sobre ITCER decía `Q✗` para un modelo
que pasa la Q holgadamente, y además decía algo absurdo — que añadir la media
EMPEORABA el ruido blanco. La causa: `q_pass` se guarda como booleano en el
momento de registrar, y el instrumento se corrigió tres veces el mismo día
sobre ese estadístico (BUG-0074, BUG-0075, BUG-0077).

Guardar los p-valores no deshace el problema —el registro sigue siendo
histórico, que es lo que un guion ES— pero permite RELEERLO. Y la versión del
instrumento dice si hace falta.
"""
import json
import numpy as np
import pytest

fue = pytest.importorskip("fue")
from art.guion import GuionStats, GuionEntry, version_instrumento, _extract_stats
from art.diagnosis import diagnose


def _modelo(n=120, semilla=3):
    y = np.cumsum(np.random.default_rng(semilla).standard_normal(n))
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="S")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                  ar=[[0.3]], ar_free=[[True]])
    m.fit()
    return m


# ───────────────── los datos, no sólo el veredicto ─────────────────

def test_guarda_los_p_valores_y_los_retardos():
    m = _modelo()
    st = _extract_stats(m, diagnose(m))
    assert st.q_lags, "sin los retardos, un p-valor no se puede releer"
    assert len(st.q_pvalues) == len(st.q_lags)
    assert st.jb_pvalue is not None


def test_guarda_la_correccion_de_grados_de_libertad_que_se_uso():
    """Es lo que cambió en BUG-0077, y sin ello los p-valores guardados no se
    pueden reinterpretar."""
    m = _modelo()
    st = _extract_stats(m, diagnose(m))
    assert st.npar == 1, "un AR(1) libre"


def test_los_p_valores_guardados_reproducen_el_veredicto():
    m = _modelo()
    dg = diagnose(m)
    st = _extract_stats(m, dg)
    assert (min(st.q_pvalues) > 0.05) == st.q_pass
    assert (st.jb_pvalue > 0.05) == st.jb_pass


# ───────────────── con QUÉ se calculó ─────────────────

def test_la_version_lleva_paquete_y_commit():
    v = version_instrumento()
    assert v.startswith("art ")
    assert v != "art ?"


def test_avisa_si_el_arbol_tiene_cambios_sin_commitear():
    """Con el árbol sucio el SHA identifica el último commit, no el código que
    corrió. Marcarlo es lo honesto: ese registro no se reproduce con el SHA."""
    import subprocess, os, art
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(art.__file__))))
    sucio = bool(subprocess.run(["git", "-C", raiz, "status", "--porcelain"],
                                capture_output=True, text=True).stdout.strip())
    assert ("+sucio" in version_instrumento()) == sucio


def test_la_version_sale_del_FUENTE_no_de_la_metadata_instalada():
    """`art.__version__` lee la metadata del paquete INSTALADO, que en
    instalación editable no se regenera al subir la versión: daba 0.1.11 sobre
    un árbol que ya iba por 0.1.12."""
    import os, art, re
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(art.__file__))))
    py = os.path.join(raiz, "pyproject.toml")
    if not os.path.exists(py):
        pytest.skip("sin árbol fuente delante")
    with open(py, encoding="utf-8") as fh:
        v_fuente = next(ln.split("=", 1)[1].strip().strip('"\'')
                        for ln in fh if ln.strip().startswith("version"))
    assert f"art {v_fuente}" in version_instrumento()


def test_una_entrada_nueva_lleva_la_version():
    e = GuionEntry(version=1, name="m00", inp_path="", timestamp="",
                   spec={}, stats=None, equation="", decision="d", rationale="r",
                   problems_found="", next_version="",
                   instrumento=version_instrumento())
    assert e.instrumento.startswith("art ")


# ───────────────── compatibilidad hacia atrás ─────────────────

def test_un_guion_viejo_sigue_cargando():
    """Los guiones de los runs 1-4 no tienen ninguno de estos campos."""
    d = dict(version=1, name="m00", inp_path="", timestamp="", spec={},
             stats=dict(loglik=-1.0, aic=2.0, bic=3.0, sigma_a=0.1,
                        q_pass=True, jb_pass=True, n_extreme=0, extreme=[]),
             equation="", decision="d", rationale="r", problems_found="",
             next_version="")
    e = GuionEntry.from_dict(d)
    assert e.instrumento == "", "sin registrar, y así se debe poder detectar"
    assert e.stats.q_lags == [] and e.stats.q_pvalues == []
    assert e.stats.npar is None


def test_el_mapa_avisa_de_entradas_sin_version():
    """Y el aviso importa: sin él, el mapa presenta como estado actual un
    veredicto que puede venir de una versión con un defecto ya corregido."""
    import inspect, art.mcp_server as srv
    cuerpo = inspect.getsource(srv.guion_map)
    assert "No todo se calculó con el mismo instrumento" in cuerpo
    assert "sin registrar" in cuerpo
