"""El guion tiene que poder LEERSE: mañana, y desde otra carpeta.

BUG-0098 y hallazgos #4/#6 de la revisión con contexto limpio. Tres cosas que
el guion no hacía, y las tres rompen la lectura sin borrar un byte:

  (A) un guion escrito por una versión anterior levantaba TypeError — el
      registro caducaba con el instrumento;
  (B) `inp_path` se guardaba relativo al cwd de aquel día: 189 de 630 caminos
      del corpus apuntaban al vacío, **las 189 relativas y ninguna absoluta**;
  (C) `base_pre_path` —la semilla, el dato con el que se DEDUCE el padre— se
      consumía y se tiraba: 0 de 1.306 entradas lo llevaban.
"""
import json
import os

import pytest

from art.guion import (CAMPOS_DE_RUTA, Guion, GuionEntry, GuionStats,
                       load_guion, save_guion)


def _guion_viejo(inp="work/S_m01.inp"):
    """Tal como lo escribía una versión anterior: sin loglik/bic/sigma_a."""
    return {"series": "S", "analyst": "", "created": "2025-01-01",
            "entries": [{"version": 1, "name": "PC1", "inp_path": inp,
                         "timestamp": "2025-01-01T00:00:00",
                         "spec": {"lam": 0.0, "d": 1}, "equation": "",
                         "decision": "", "rationale": "", "problems_found": "",
                         "next_version": "",
                         "stats": {"aic": 12.3, "jb_pass": True,
                                   "jb_pvalue": 0.4, "n_extreme": 0,
                                   "q_pass": True}}]}


# ── (A) el registro no caduca ─────────────────────────────────────────

def test_un_guion_de_una_version_anterior_se_abre(tmp_path):
    gp = tmp_path / "S_guion.json"
    gp.write_text(json.dumps(_guion_viejo()))
    g = load_guion(str(gp))
    assert len(g.entries) == 1


def test_lo_que_no_consta_es_None_y_no_cero(tmp_path):
    """Un 0.0 inventado en ℓ entra en las comparaciones y gana todas."""
    gp = tmp_path / "S_guion.json"
    gp.write_text(json.dumps(_guion_viejo()))
    st = load_guion(str(gp)).entries[0].stats
    assert st.loglik is None and st.sigma_a is None and st.bic is None
    assert st.aic == 12.3


def test_un_campo_que_ya_no_existe_no_revienta_la_lectura(tmp_path):
    d = _guion_viejo()
    d["entries"][0]["campo_de_otra_epoca"] = "x"
    d["entries"][0]["stats"]["estadistico_retirado"] = 1.0
    gp = tmp_path / "S_guion.json"
    gp.write_text(json.dumps(d))
    assert len(load_guion(str(gp)).entries) == 1


# ── (B) los caminos ───────────────────────────────────────────────────

def test_un_camino_relativo_se_resuelve_contra_la_carpeta_del_guion(tmp_path,
                                                                    monkeypatch):
    (tmp_path / "work").mkdir()
    real = tmp_path / "work" / "S_m01.inp"
    real.write_text("x")
    gp = tmp_path / "S_guion.json"
    gp.write_text(json.dumps(_guion_viejo()))
    monkeypatch.chdir(os.path.expanduser("~"))   # otro cwd: el caso real
    e = load_guion(str(gp)).entries[0]
    assert os.path.isabs(e.inp_path) and os.path.exists(e.inp_path)
    assert os.path.samefile(e.inp_path, str(real))


def test_tambien_por_el_basename(tmp_path, monkeypatch):
    """188 de los 189 del corpus resolvían así: el fichero al lado del guion."""
    (tmp_path / "S_m01.inp").write_text("x")
    gp = tmp_path / "S_guion.json"
    gp.write_text(json.dumps(_guion_viejo(inp="otra/carpeta/S_m01.inp")))
    monkeypatch.chdir(os.path.expanduser("~"))
    assert os.path.exists(load_guion(str(gp)).entries[0].inp_path)


def test_un_camino_que_existe_no_se_toca(tmp_path, monkeypatch):
    """La resolución no puede robarle el sitio a un fichero que está donde dice."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "aqui").mkdir(); (tmp_path / "aqui" / "S_m01.inp").write_text("A")
    sub = tmp_path / "sub"; sub.mkdir(); (sub / "S_m01.inp").write_text("B")
    gp = sub / "S_guion.json"
    gp.write_text(json.dumps(_guion_viejo(inp="aqui/S_m01.inp")))
    e = load_guion(str(gp)).entries[0]
    assert e.inp_path == "aqui/S_m01.inp"      # existe desde el cwd: intacto
    assert open(e.inp_path).read() == "A"


def test_se_escribe_absoluto(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "S_m01.inp").write_text("x")
    g = Guion(series="S", analyst="", created="2026-01-01")
    g.entries.append(GuionEntry(
        version=1, name="PC1", inp_path="S_m01.inp", timestamp="t",
        spec={}, stats=None, equation="", decision="", rationale="",
        problems_found="", next_version=""))
    gp = str(tmp_path / "S_guion.json")
    save_guion(g, gp)
    assert os.path.isabs(json.load(open(gp))["entries"][0]["inp_path"])


def test_un_camino_incomprobable_se_deja_como_esta(tmp_path):
    """Absolutizarlo contra este cwd sería INVENTAR una ubicación."""
    g = Guion(series="S", analyst="", created="2026-01-01")
    g.entries.append(GuionEntry(
        version=1, name="PC1", inp_path="no/existe/S.inp", timestamp="t",
        spec={}, stats=None, equation="", decision="", rationale="",
        problems_found="", next_version=""))
    gp = str(tmp_path / "S_guion.json")
    save_guion(g, gp)
    assert json.load(open(gp))["entries"][0]["inp_path"] == "no/existe/S.inp"


def test_las_figuras_quedan_fuera():
    """Son hermanas del guion, viven en figs/ a su lado y viajan con él;
    absolutizarlas las rompería al mover la carpeta."""
    assert "figure_path" not in CAMPOS_DE_RUTA
    assert "hist_path" not in CAMPOS_DE_RUTA
    assert "inp_path" in CAMPOS_DE_RUTA and "out_path" in CAMPOS_DE_RUTA


# ── (C) la semilla ────────────────────────────────────────────────────

def test_la_entrada_tiene_campo_para_la_semilla():
    e = GuionEntry(version=1, name="a", inp_path="", timestamp="t", spec={},
                   stats=None, equation="", decision="", rationale="",
                   problems_found="", next_version="")
    assert e.base_pre_path == ""


def test_la_semilla_sobrevive_al_viaje_de_ida_y_vuelta(tmp_path):
    g = Guion(series="S", analyst="", created="2026-01-01")
    g.entries.append(GuionEntry(
        version=1, name="PC1", inp_path="", timestamp="t", spec={}, stats=None,
        equation="", decision="", rationale="", problems_found="",
        next_version="", base_pre_path="/x/S_m00.pre"))
    gp = str(tmp_path / "S_guion.json")
    save_guion(g, gp)
    assert load_guion(gp).entries[0].base_pre_path == "/x/S_m00.pre"


def test_record_version_guarda_la_semilla_que_uso_para_el_padre():
    """El campo con el que se DEDUCE el parentesco tiene que quedar: si no, se
    puede leer de quién desciende un nodo pero no comprobarlo.

    Y no basta la RUTA. Una ruta no identifica un contenido: reescrito el `.pre`
    semilla, el hijo seguía declarando un linaje que ya no era cierto y nadie lo
    desmentía (BUG-0175). Lo que se deduce se deduce con la ruta Y con la
    huella, y las dos se guardan.
    """
    from tests._fuente import cuerpo_de
    import art.mcp_server as srv
    src = cuerpo_de(srv._record_to_guion)
    llamada = [l for l in src.splitlines() if "infer_parent(" in l]
    assert llamada, "nadie deduce el padre"
    assert all(x in llamada[0] for x in ("base_pre_path", "base_pre_sha")), (
        f"el padre se deduce sin la huella: {llamada[0].strip()}")
    for campo in ("base_pre_path=base_pre_path",
                  "base_pre_sha=base_pre_sha",
                  "pre_sha="):
        assert campo in src, f"no se guarda {campo}"


def test_los_defectos_estan_documentados():
    assert os.path.exists("bugs/BUG-0098-repro/repro.py")


# ── el mismo Dropbox, otro sistema ────────────────────────────────────

def test_un_camino_absoluto_de_OTRO_sistema_se_resuelve(tmp_path, monkeypatch):
    """El caso que importa de verdad: el mismo Dropbox abierto en Windows y en
    Linux. Los guiones guardan caminos ABSOLUTOS (BUG-0098) y el punto de
    montaje cambia — `/home/david/Dropbox/…` frente a `C:\\Users\\…\\Dropbox\\…`.

    Aquí había un cortocircuito `os.path.isabs(ruta)` que lo rompía, porque
    `ntpath.isabs("/home/david/…")` es **True** en Windows: el camino se
    declaraba absoluto, se devolvía tal cual y quedaba muerto sin llegar a
    probar el rescate. Lo que decide es si EXISTE, no si lo parece."""
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "S_m00.inp").write_text("x")
    for ajena in ("/otra/maquina/work/S_m00.inp",
                  r"C:\Users\david\Dropbox\work\S_m00.inp",
                  "/home/david/Dropbox/borrado/S_m00.inp"):
        gp = tmp_path / "work" / "S_guion.json"
        gp.write_text(json.dumps({
            "series": "S", "analyst": "", "created": "2025-01-01", "entries": [
                {"version": 1, "name": "m00", "inp_path": ajena, "timestamp": "t",
                 "spec": {}, "stats": None, "equation": "", "decision": "",
                 "rationale": "", "problems_found": "", "next_version": ""}]}))
        e = load_guion(str(gp)).entries[0]
        assert os.path.exists(e.inp_path), f"no resuelve {ajena!r}"


def test_pero_un_camino_que_SI_existe_sigue_intacto(tmp_path, monkeypatch):
    """La resolución no puede robarle el sitio a un fichero que está donde dice,
    ni siquiera ahora que ya no se salta los absolutos."""
    (tmp_path / "aqui").mkdir()
    (tmp_path / "aqui" / "S_m00.inp").write_text("EL BUENO")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "S_m00.inp").write_text("el otro")
    gp = tmp_path / "sub" / "S_guion.json"
    gp.write_text(json.dumps({
        "series": "S", "analyst": "", "created": "2025-01-01", "entries": [
            {"version": 1, "name": "m00",
             "inp_path": str(tmp_path / "aqui" / "S_m00.inp"), "timestamp": "t",
             "spec": {}, "stats": None, "equation": "", "decision": "",
             "rationale": "", "problems_found": "", "next_version": ""}]}))
    e = load_guion(str(gp)).entries[0]
    assert open(e.inp_path).read() == "EL BUENO"
