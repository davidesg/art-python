"""El registro tiene que decir lo que dice su fichero (BUG-0102).

El guion es el registro científico y su `.inp` es la evidencia. Que discrepen no
es un descuadre de formato: lo que se lee en el mapa no es lo que se estimó.

Sobre el corpus real —616 entradas-modelo— hay una sola discrepancia, y pierde
3 de 4 intervenciones: las tres que la entrada venía arrastrando de su padre.
"""
import json
import os

import pytest

from art.guion import (Guion, GuionEntry, GuionStats, cifra,
                       entradas_que_no_cuadran, load_guion, save_guion)

INP = """** Frequency of time series: either 1(A), 4(Q) or 12(M):
 12
** Number of observations and starting date of time series:
 120  1 2005 S
** Number of deterministic variables (including seasonal components):
{n}
**
{nombres}
**
"""


def _inp(ruta, deterministas):
    ruta.write_text(INP.format(n=len(deterministas),
                               nombres="\n".join(deterministas)))


def _guion(tmp_path, inp, spec_itvs):
    g = Guion(series="S", analyst="", created="2026-01-01")
    g.entries.append(GuionEntry(
        version=1, name="m01", inp_path=str(inp), timestamp="t",
        spec={"interventions": spec_itvs}, stats=None, equation="",
        decision="", rationale="", problems_found="", next_version=""))
    gp = str(tmp_path / "S_guion.json")
    save_guion(g, gp)
    return load_guion(gp)


# ── (A) el detector ───────────────────────────────────────────────────

def test_ve_las_intervenciones_que_faltan(tmp_path):
    f = tmp_path / "S_m01.inp"
    _inp(f, ["cos 1", "sin 1", "alter", "step 35", "step 181", "step 222",
             "step 243"])
    g = _guion(tmp_path, f, [{"type": "step", "date": "07/2020"}])
    assert entradas_que_no_cuadran(g) == [(1, "m01", 4, 1)]


def test_no_da_falso_positivo_cuando_cuadra(tmp_path):
    f = tmp_path / "S_m01.inp"
    _inp(f, ["cos 1", "sin 1", "alter", "step 35"])
    g = _guion(tmp_path, f, [{"type": "step", "date": "01/2008"}])
    assert entradas_que_no_cuadran(g) == []


def test_los_armonicos_NO_son_intervenciones(tmp_path):
    """Van en `n_harmonics` y en `alter`, no en la lista: contarlos daría un
    descuadre en todos los modelos estacionales del corpus."""
    f = tmp_path / "S_m01.inp"
    _inp(f, ["cos 1", "sin 1", "cos 2", "sin 2", "alter"])
    assert entradas_que_no_cuadran(_guion(tmp_path, f, [])) == []


def test_el_easter_SI_cuenta(tmp_path):
    """No es estructura estacional: es un determinista más, y se registra."""
    f = tmp_path / "S_m01.inp"
    _inp(f, ["cos 1", "sin 1", "alter", "easter"])
    g = _guion(tmp_path, f, [{"type": "easter"}])
    assert entradas_que_no_cuadran(g) == []
    g2 = _guion(tmp_path, f, [])
    assert entradas_que_no_cuadran(g2) == [(1, "m01", 1, 0)]


def test_una_spec_vieja_sin_el_campo_no_afirma_nada(tmp_path):
    """No se puede acusar de contradicción a quien no dijo nada."""
    f = tmp_path / "S_m01.inp"
    _inp(f, ["step 35"])
    g = Guion(series="S", analyst="", created="2026-01-01")
    g.entries.append(GuionEntry(
        version=1, name="viejo", inp_path=str(f), timestamp="t",
        spec={"d": 1}, stats=None, equation="", decision="", rationale="",
        problems_found="", next_version=""))
    assert entradas_que_no_cuadran(g) == []


def test_un_fichero_ausente_no_es_una_contradiccion(tmp_path):
    g = _guion(tmp_path, tmp_path / "no_existe.inp", [{"type": "step"}])
    assert entradas_que_no_cuadran(g) == []


def test_el_mapa_lo_dice(tmp_path):
    import art.mcp_server as srv
    f = tmp_path / "S_m01.inp"
    _inp(f, ["step 35", "step 181", "step 222", "step 243"])
    _guion(tmp_path, f, [{"type": "step", "date": "07/2020"}])
    gm = getattr(srv.guion_map, "fn", srv.guion_map)
    t = gm(str(tmp_path / "S_guion.json"))[0].text
    assert "CONTRADICE" in t
    assert "4 intervención(es)" in t and "registra 1" in t


def test_el_caso_real():
    p = os.path.expanduser("~/Dropbox/SRC/DVR/cases/UEM_FOOD_SERV_2025/"
                           "food/work/FOOD_UEM_2025_guion.json")
    if not os.path.exists(p):
        pytest.skip("el caso no está en esta máquina")
    r = entradas_que_no_cuadran(load_guion(p))
    assert any(n.startswith("b02_covid_auto") and f == 4 and g == 1
               for _, n, f, g in r), r


# ── (B) lo que no consta ──────────────────────────────────────────────

def test_una_cifra_ausente_no_revienta():
    """Regresión propia de BUG-0098: hacer legibles los guiones viejos puso
    `None` donde no había dato, y presentar `None` con `:.2f` mata."""
    assert cifra(None) == "—"
    assert cifra(None, ".5f") == "—"
    assert cifra(-869.34) == "-869.34"
    assert cifra(0.0123, ".5f") == "0.01230"


def test_no_se_inventa_un_cero():
    """Un 0.0 en ℓ entra en las comparaciones y las gana todas."""
    assert cifra(None) != "0.00"
    assert cifra(0.0) == "0.00", "un cero REAL sí se muestra"


def test_el_mapa_dibuja_un_guion_sin_cifras(tmp_path):
    """Antes fallaba al ABRIRSE; después del arreglo fallaba al DIBUJARSE, que
    es peor porque parece que funciona hasta que lo miras."""
    import art.mcp_server as srv
    viejo = {"series": "S", "analyst": "", "created": "2025-01-01", "entries": [
        {"version": 1, "name": "m00", "inp_path": "", "timestamp": "t",
         "spec": {}, "equation": "", "decision": "", "rationale": "",
         "problems_found": "", "next_version": "",
         "stats": {"aic": 12.3, "jb_pass": True, "n_extreme": 0,
                   "q_pass": True}}]}
    gp = tmp_path / "S_guion.json"
    gp.write_text(json.dumps(viejo))
    gm = getattr(srv.guion_map, "fn", srv.guion_map)
    t = gm(str(gp))[0].text
    assert "logL=—" in t
    assert "Error" not in t


def test_export_guion_tambien(tmp_path):
    """Había cuatro sitios más con la misma bomba sin estallar."""
    from tests._fuente import fuente_de
    from art.guion import export_guion_html
    src = fuente_de(export_guion_html)
    assert "s.loglik:." not in src and "s.sigma_a:." not in src


def test_el_defecto_esta_documentado():
    assert os.path.exists("bugs/BUG-0102-repro/repro.py")
