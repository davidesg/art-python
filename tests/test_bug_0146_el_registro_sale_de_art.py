"""BUG-0146 — el registro de defectos no salía de `art`.

`art.bugs` acepta `bugs_dir=` en todas sus funciones. El CLI no lo exponía en
ninguna, así que llevar el registro a otro programa de la escalera exigía copiar
el módulo — la misma capacidad en N sitios, que es la enfermedad contra la que
está escrito el plan entero.

Y había dos trampas debajo: `find_bugs_dir` se cae a la ubicación del paquete
cuando no encuentra nada, así que fuera de `art` indexaba los defectos de `art`
sin decir nada; y el nombre del proyecto estaba clavado en `render_index`, así
que el primer índice de `pyfug` salió firmado como ART.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from art import bugs as _bugs
from art.bug_cli import main as bug_main

RAIZ = Path(__file__).resolve().parent.parent
BUGS_ART = RAIZ / "bugs"


def _registro(tmp_path, n=2, proyecto=None):
    """Un registro ajeno, mínimo y válido."""
    d = tmp_path / "otroprog" / "bugs"
    d.mkdir(parents=True)
    for i in range(1, n + 1):
        (d / f"BUG-{i:04d}-cosa-{i}.md").write_text(
            f"---\nid: BUG-{i:04d}\ntitle: la cosa {i}\nstatus: open\n"
            f"severity: medium\ncomponent: nucleo\nfound_in: 1.0\nfixed_in:\n"
            f"reported: 2026-09-10\nreporter: David\ntags: []\n"
            f"references: []\n---\n\n## Summary\n\nQué pasa.\n",
            encoding="utf-8")
    if proyecto:
        (d / "PROJECT").write_text(proyecto + "\n", encoding="utf-8")
    return d


# ────────── la puerta ──────────

def test_el_cli_opera_sobre_un_registro_ajeno(tmp_path, capsys):
    d = _registro(tmp_path, n=3)
    assert bug_main(["--dir", str(d), "check"]) == 0
    assert "3 report(s)" in capsys.readouterr().out


def test_y_no_toca_el_de_art(tmp_path):
    """La prueba que importa del `--dir`: el índice ajeno se escribe en el sitio
    ajeno, y el de `art` no se mueve."""
    antes = (BUGS_ART / "README.md").read_text(encoding="utf-8")
    d = _registro(tmp_path, n=2)
    ruta = _bugs.write_index(d)
    assert Path(ruta).parent == d
    assert (BUGS_ART / "README.md").read_text(encoding="utf-8") == antes
    assert "BUG-0002" in Path(ruta).read_text(encoding="utf-8")


# ────────── el cepo ──────────

def test_un_directorio_VACIO_falla_en_vez_de_indexar_los_de_art(tmp_path):
    """LA trampa. `find_bugs_dir` se cae a la ubicación del paquete cuando no
    encuentra nada, así que sin `--dir` un repositorio con `bugs/` aún vacío
    escribía el índice de `art`, en el sitio de `art`, en silencio.

    Con `--dir` explícito no hay respaldo: si ahí no hay defectos, se dice.
    """
    vacio = tmp_path / "recien-creado" / "bugs"
    vacio.mkdir(parents=True)
    assert _bugs.list_bugs(bugs_dir=vacio) == []
    ruta = _bugs.write_index(vacio)
    texto = Path(ruta).read_text(encoding="utf-8")
    assert "0 report(s)" in texto
    # Ninguna FILA de tabla. No vale buscar «BUG-0001» a secas: la cabecera
    # del índice lo usa como ejemplo («e.g. `fix(pipeline): BUG-0001 …`»), y
    # una prueba que lo confunda con un informe real da un falso positivo.
    filas = [l for l in texto.splitlines() if l.startswith("| [BUG-")]
    assert not filas, \
        f"el índice del repositorio vacío se ha llenado con defectos de otro: {filas[:2]}"


# ────────── el nombre del proyecto ──────────

def test_el_nombre_sale_del_fichero_PROJECT(tmp_path):
    d = _registro(tmp_path, proyecto="pyfug — los gráficos")
    assert _bugs.project_name(d) == "pyfug — los gráficos"
    assert "pyfug — los gráficos" in _bugs.render_index(d)


def test_y_si_no_hay_PROJECT_sale_del_directorio(tmp_path):
    d = _registro(tmp_path)
    assert _bugs.project_name(d) == "otroprog"


def test_el_indice_de_art_no_se_firma_con_otro_nombre():
    """El otro lado: `art` dice `art` porque lo declara en `bugs/PROJECT`."""
    assert (BUGS_ART / "PROJECT").is_file(), "art debe declarar su nombre"
    assert "ART" in _bugs.project_name(BUGS_ART)
    assert "ART" in (BUGS_ART / "README.md").read_text(encoding="utf-8")


# ────────── el primer usuario ──────────

def test_pyfug_tiene_registro_si_esta_al_lado():
    """No es una prueba de `art`: es la comprobación de que el arreglo sirvió
    para lo que se hizo. Se salta si `pyfug` no está en este disco."""
    py = RAIZ.parent.parent / "atws" / "fug" / "pyfug" / "bugs"
    if not py.is_dir():
        pytest.skip("pyfug no está al lado")
    assert _bugs.list_bugs(bugs_dir=py), "pyfug tiene registro pero está vacío"
    assert "pyfug" in _bugs.project_name(py)
    assert not _bugs.validate_all(py), "los informes de pyfug no validan"
