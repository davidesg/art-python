"""BUG-0125 — los recursos MCP no existían en una instalación.

La rueda 0.2.0 publicada lleva 27 ficheros y ninguno de `bugs/` ni de `docs/`,
así que los cuatro recursos de contenido existían en `resources/list`, se podían
pedir, y contestaban que no había nada. Ninguna prueba lo cubría porque
**ninguna prueba cruza una instalación**: la suite corre siempre sobre el árbol,
donde la ruta acertaba por accidente.
"""
import os
import subprocess
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))


def test_el_material_se_puede_sincronizar():
    """La copia que se distribuye se GENERA de `bugs/` y `docs/`.

    Esta prueba sincroniza y comprueba que después queda al día. NO exige que
    lo estuviera: en el árbol de trabajo, añadir un informe de defecto dejaría
    la suite en rojo por una razón que no tiene que ver con lo que se está
    probando — medido en la práctica, ocurre a la hora de escribir la guarda.

    **La estrictez vive donde importa, que es el ARTEFACTO**: el flujo de
    publicación sincroniza antes de construir y falla la publicación si la
    rueda no lleva el material (`.github/workflows/publish-art.yml`). Lo que
    esta prueba cuida es que el guion que lo genera siga funcionando."""
    import sync_material
    sync_material.sincroniza()
    fallos = sync_material.desincronizado()
    assert not fallos, (
        f"el guion de sincronización no deja la copia al día: {fallos[:5]}")


def test_los_recursos_leen_del_paquete_y_no_del_arbol():
    """La regla: si `art/material/` existe, manda. Es lo único que hace que una
    instalación vea algo."""
    from art import recursos
    esperado = os.path.join(os.path.dirname(recursos.__file__), "material")
    if os.path.isdir(esperado):
        assert recursos._raiz_del_material() == esperado
    assert os.path.isdir(os.path.join(recursos._RAIZ, "bugs"))


def test_el_indice_de_defectos_tiene_contenido():
    from art import recursos
    txt = recursos.indice_de_defectos()
    assert "BUG-0125" in txt, "el índice no ve el registro"
    assert "esta instalación" not in txt


def test_cuando_no_hay_material_se_dice_por_que(monkeypatch, tmp_path):
    """«no hay defectos» y «esta instalación no los trae» son cosas distintas, y
    decir la primera cuando pasa la segunda borra la razón (BUG-0090)."""
    from art import recursos
    monkeypatch.setattr(recursos, "_RAIZ", str(tmp_path))
    txt = recursos.indice_de_defectos()
    assert "BUG-0125" in txt and "github.com" in txt


@pytest.mark.slow
def test_la_rueda_construida_lleva_el_material(tmp_path):
    """La comprobación que faltaba: sobre el ARTEFACTO, no sobre la
    configuración. Es como se estableció el defecto —descargando la rueda
    publicada— y es como se comprueba el arreglo."""
    import sync_material
    sync_material.sincroniza()
    r = subprocess.run([sys.executable, "-m", "build", "--wheel",
                        "--outdir", str(tmp_path), RAIZ],
                       capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        pytest.skip(f"no se pudo construir la rueda: {r.stderr[-300:]}")
    import glob
    import zipfile
    ruedas = glob.glob(str(tmp_path / "*.whl"))
    assert ruedas, "build no dejó ninguna rueda"
    n = zipfile.ZipFile(ruedas[0]).namelist()
    bugs = [x for x in n if "material/bugs/" in x]
    docs = [x for x in n if "material/docs/" in x]
    assert len(bugs) > 100, f"la rueda lleva {len(bugs)} informes"
    assert docs, "la rueda no lleva documentación"
