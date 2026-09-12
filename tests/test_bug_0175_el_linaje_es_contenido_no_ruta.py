"""BUG-0175 — el linaje es un CONTENIDO, no una ruta.

`infer_parent` emparejaba al padre por la RUTA del `.pre` semilla, y su propio
docstring prometía otra cosa: «la versión que produjo ESE fichero». Lo que
devolvía era *la última entrada cuya ruta coincide* —el `reversed` lo
garantiza—, o sea quien lo REESCRIBIÓ. Con dos estimaciones en la misma ruta,
los hijos de la primera quedaban colgando de la segunda, y `guion_map` dibujaba
ese árbol sin una sola reserva.

No hace falta una segunda sesión para provocarlo: basta reestimar dos veces en
el mismo sitio dentro de un solo guion.
"""
import json
import os

import pytest

from art.guion import (Guion, GuionEntry, infer_parent, linaje_dudoso,
                       pre_hermano, sha_del_fichero, save_guion, load_guion)


def _entrada(version, name, inp_path, **kw):
    return GuionEntry(
        version=version, name=name, inp_path=inp_path,
        timestamp=f"2026-09-12T10:0{version}:00", spec={}, stats=None,
        equation="", decision="", rationale="", problems_found="",
        next_version="", **kw)


def _pre(tmp_path, nombre, texto):
    """Un `.pre` de mentira: para la huella sólo cuentan los bytes."""
    p = tmp_path / nombre
    p.write_text(texto, encoding="utf-8")
    return str(p)


# ── la huella ─────────────────────────────────────────────────────────────

def test_la_huella_distingue_dos_contenidos(tmp_path):
    a = _pre(tmp_path, "a.pre", "phi = 0.0\n")
    b = _pre(tmp_path, "b.pre", "phi = -0.96\n")
    assert sha_del_fichero(a) != sha_del_fichero(b)
    assert len(sha_del_fichero(a)) == 64


def test_un_fichero_que_no_esta_no_tiene_huella_y_no_revienta(tmp_path):
    """`""` significa NO CONSTA. Un guion tiene que poder registrarse aunque el
    fichero falte; lo que no puede es afirmar un linaje que no comprobó."""
    assert sha_del_fichero(str(tmp_path / "no-existe.pre")) == ""
    assert sha_del_fichero("") == ""


def test_el_pre_es_el_hermano_del_inp():
    assert pre_hermano("/w/S_m03.inp").endswith("/w/S_m03.pre")


# ── el defecto: dos versiones en la MISMA ruta ────────────────────────────

@pytest.fixture
def guion_con_ruta_reescrita(tmp_path):
    """v1 y v2 estiman en la misma ruta. v2 pisa el `.pre` de v1."""
    inp = str(tmp_path / "S_m01.inp")
    pre = pre_hermano(inp)

    open(pre, "w").write("el .pre de v1\n")
    sha_v1 = sha_del_fichero(pre)
    g = Guion(series="S", analyst="", created="2026-09-12")
    g.entries.append(_entrada(1, "v1", inp, pre_sha=sha_v1))

    open(pre, "w").write("el .pre de v2, que pisa al de v1\n")
    sha_v2 = sha_del_fichero(pre)
    g.entries.append(_entrada(2, "v2", inp, pre_sha=sha_v2, parent=1))
    return g, pre, sha_v1, sha_v2


def test_el_hijo_de_la_primera_no_cuelga_de_la_segunda(guion_con_ruta_reescrita):
    """EL DEFECTO. Encadenar con la huella de v1 no puede devolver v2."""
    g, pre, sha_v1, sha_v2 = guion_con_ruta_reescrita
    assert infer_parent(g, pre, sha_v1) == 1, (
        "empareja por ruta y devuelve al que PISÓ el fichero, no al que lo produjo")


def test_encadenar_con_la_huella_de_la_segunda_devuelve_la_segunda(
        guion_con_ruta_reescrita):
    g, pre, sha_v1, sha_v2 = guion_con_ruta_reescrita
    assert infer_parent(g, pre, sha_v2) == 2


def test_una_huella_que_no_conoce_nadie_no_nombra_padre(guion_con_ruta_reescrita):
    """El fichero lo escribió algo que este guion no registró. Devolver el
    último sería nombrar padre a un impostor."""
    g, pre, _, _ = guion_con_ruta_reescrita
    assert infer_parent(g, pre, "f" * 64) is None


# ── lo que ya funcionaba tiene que seguir funcionando ────────────────────

def test_sin_encadenar_el_padre_sigue_siendo_la_ultima(guion_con_ruta_reescrita):
    g, _, _, _ = guion_con_ruta_reescrita
    assert infer_parent(g) == 2


def test_un_guion_sin_huellas_se_empareja_por_ruta_como_antes(tmp_path):
    """Compatibilidad: los guiones escritos antes del campo no se rompen."""
    inp = str(tmp_path / "S_m01.inp")
    g = Guion(series="S", analyst="", created="2026-01-01")
    g.entries.append(_entrada(1, "v1", inp))
    g.entries.append(_entrada(2, "v2", str(tmp_path / "S_m02.inp"), parent=1))
    assert infer_parent(g, pre_hermano(inp)) == 1


def test_el_primer_registro_no_tiene_padre():
    g = Guion(series="S", analyst="", created="2026-09-12")
    assert infer_parent(g, "/w/loquesea.pre", "a" * 64) is None


# ── linaje_dudoso ─────────────────────────────────────────────────────────

def test_detecta_que_el_fichero_semilla_ha_cambiado(tmp_path):
    inp1 = str(tmp_path / "S_m01.inp")
    pre1 = pre_hermano(inp1)
    open(pre1, "w").write("el .pre de v1\n")
    sha1 = sha_del_fichero(pre1)

    g = Guion(series="S", analyst="", created="2026-09-12")
    g.entries.append(_entrada(1, "v1", inp1, pre_sha=sha1))
    g.entries.append(_entrada(2, "v2", str(tmp_path / "S_m02.inp"),
                              parent=1, base_pre_path=pre1, base_pre_sha=sha1))
    assert linaje_dudoso(g) == []

    open(pre1, "w").write("alguien reescribio el .pre de v1\n")
    assert linaje_dudoso(g) == [(2, "el fichero ha cambiado")]


def test_detecta_que_el_padre_registrado_es_otro(tmp_path):
    """La entrada dice venir de un `.pre` cuya huella no es la que su padre
    produjo. El árbol dibuja un enlace que no existe."""
    g = Guion(series="S", analyst="", created="2026-09-12")
    g.entries.append(_entrada(1, "v1", str(tmp_path / "S_m01.inp"),
                              pre_sha="a" * 64))
    g.entries.append(_entrada(2, "v2", str(tmp_path / "S_m02.inp"), parent=1,
                              base_pre_path=str(tmp_path / "S_m01.pre"),
                              base_pre_sha="b" * 64))
    assert linaje_dudoso(g) == [(2, "el padre es otro")]


def test_un_pre_borrado_no_se_denuncia(tmp_path):
    """Que un fichero de trabajo desaparezca es corriente y no contradice nada
    de lo registrado."""
    sha = "c" * 64
    g = Guion(series="S", analyst="", created="2026-09-12")
    g.entries.append(_entrada(1, "v1", str(tmp_path / "S_m01.inp"), pre_sha=sha))
    g.entries.append(_entrada(2, "v2", str(tmp_path / "S_m02.inp"), parent=1,
                              base_pre_path=str(tmp_path / "S_m01.pre"),
                              base_pre_sha=sha))
    assert linaje_dudoso(g) == []


def test_un_guion_viejo_sale_como_sin_contrastar_no_como_roto(tmp_path):
    g = Guion(series="S", analyst="", created="2026-01-01")
    g.entries.append(_entrada(1, "v1", str(tmp_path / "S_m01.inp")))
    g.entries.append(_entrada(2, "v2", str(tmp_path / "S_m02.inp"), parent=1,
                              base_pre_path=str(tmp_path / "S_m01.pre")))
    assert linaje_dudoso(g) == [(2, "sin contrastar")]


def test_sin_encadenado_no_hay_nada_que_contrastar(tmp_path):
    g = Guion(series="S", analyst="", created="2026-09-12")
    g.entries.append(_entrada(1, "v1", str(tmp_path / "S_m01.inp")))
    g.entries.append(_entrada(2, "v2", str(tmp_path / "S_m02.inp"), parent=1))
    assert linaje_dudoso(g) == []


# ── las huellas viajan en el fichero del guion ───────────────────────────

def test_las_huellas_sobreviven_al_disco(tmp_path):
    gp = str(tmp_path / "guion.json")
    g = Guion(series="S", analyst="", created="2026-09-12")
    g.entries.append(_entrada(1, "v1", str(tmp_path / "S_m01.inp"),
                              pre_sha="d" * 64))
    g.entries.append(_entrada(2, "v2", str(tmp_path / "S_m02.inp"), parent=1,
                              base_pre_path=str(tmp_path / "S_m01.pre"),
                              base_pre_sha="d" * 64))
    save_guion(g, gp)
    leido = load_guion(gp)
    assert leido.entries[0].pre_sha == "d" * 64
    assert leido.entries[1].base_pre_sha == "d" * 64
    assert json.loads(open(gp).read())["entries"][1]["base_pre_sha"] == "d" * 64


# ── el mapa lo dice ───────────────────────────────────────────────────────

def test_el_mapa_avisa_de_que_el_arbol_no_se_sostiene(tmp_path):
    import art.mcp_server as M
    from tests._texto import dice

    inp1 = str(tmp_path / "S_m01.inp")
    pre1 = pre_hermano(inp1)
    open(inp1, "w").write("")
    open(pre1, "w").write("el .pre de v1\n")
    sha1 = sha_del_fichero(pre1)

    g = Guion(series="S", analyst="", created="2026-09-12")
    g.entries.append(_entrada(1, "v1", inp1, pre_sha=sha1))
    g.entries.append(_entrada(2, "v2", str(tmp_path / "S_m02.inp"), parent=1,
                              base_pre_path=pre1, base_pre_sha=sha1))
    gp = str(tmp_path / "guion.json")
    save_guion(g, gp)

    fn = getattr(M.guion_map, "fn", M.guion_map)
    limpio = fn(gp)
    limpio = limpio[0].text if isinstance(limpio, list) else str(limpio)
    assert "no se sostienen" not in limpio

    open(pre1, "w").write("alguien lo reescribio\n")
    sucio = fn(gp)
    sucio = sucio[0].text if isinstance(sucio, list) else str(sucio)
    assert dice(sucio, "El árbol dibuja enlaces que no se sostienen")
    assert dice(sucio, "el fichero ha cambiado")
    assert "BUG-0175" in sucio
