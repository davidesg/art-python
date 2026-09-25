"""
BUG-0191 — lo que art usa tiene que estar en sus dependencias, no llegar de rebote.

En una instalación limpia de la 0.2.1 publicada, `generate_forecast`,
`update_and_forecast` y `sps_dashboard` fallaban: escriben su informe con
`fue.write_forecast_report`, que necesita jinja2 —el extra `fue[report]`— y art
no lo declaraba. pandas y openpyxl (la lectura de Excel de `load_data`) llegaban
sólo porque pyfug los trae. En los entornos de desarrollo todo estaba instalado
por otra vía, y nada lo delataba.

Estas pruebas miran el `pyproject.toml`, que es lo que pip lee, y el código,
que es lo que se importa.
"""

import ast
import pathlib
import re
import sys

try:
    import tomllib
except ModuleNotFoundError:          # Python 3.10
    import tomli as tomllib

RAIZ = pathlib.Path(__file__).resolve().parents[1]

#: nombre del módulo importado → nombre de la distribución que lo trae
_DISTRIBUCION = {"yaml": "pyyaml", "PIL": "pillow", "sklearn": "scikit-learn"}

#: lo que se necesita en EJECUCIÓN sin que ningún import lo nombre
_EN_EJECUCION = {
    "openpyxl": "pandas lo carga para leer .xlsx (load_data, preview_data)",
}


def _dependencias():
    """{distribución: {extras}} de `[project] dependencies`."""
    deps = tomllib.loads((RAIZ / "pyproject.toml").read_text())["project"]["dependencies"]
    out = {}
    for d in deps:
        m = re.match(r"\s*([A-Za-z0-9_.-]+)\s*(?:\[([^\]]*)\])?", d)
        out[m.group(1).lower().replace("_", "-")] = {
            e.strip() for e in (m.group(2) or "").split(",") if e.strip()}
    return out


def _importados():
    """Módulos de terceros importados en src/art, también dentro de funciones."""
    mods = set()
    for f in (RAIZ / "src" / "art").rglob("*.py"):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                mods.add(n.module.split(".")[0])
    return {m for m in mods if m not in sys.stdlib_module_names and m != "art"}


def test_todo_lo_que_art_importa_esta_declarado():
    deps = _dependencias()
    falta = sorted(m for m in _importados()
                   if _DISTRIBUCION.get(m, m).lower() not in deps)
    assert not falta, (
        f"art importa {falta} y no los declara: llegan de rebote o no llegan "
        f"(BUG-0191)")


def test_lo_que_se_carga_en_ejecucion_esta_declarado():
    deps = _dependencias()
    falta = {m: por for m, por in _EN_EJECUCION.items() if m not in deps}
    assert not falta, f"sin declarar: {falta} (BUG-0191)"


def test_el_informe_de_prevision_trae_jinja2():
    """generate_forecast/update_and_forecast/sps_dashboard → fue[report]."""
    usa = any("write_forecast_report" in f.read_text(encoding="utf-8")
              for f in (RAIZ / "src" / "art").rglob("*.py"))
    assert usa, "si art deja de usar el informe de fue, esta prueba sobra"
    assert "report" in _dependencias().get("fue", set()), (
        "art usa fue.write_forecast_report, que necesita jinja2: la dependencia "
        "tiene que ser fue[report] (BUG-0191)")
