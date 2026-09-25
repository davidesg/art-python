"""BUG-0185 — la alternativa «Intervenir <fecha>» fechaba el residuo sin el desfase.

Levantado desde el run 8 (Windows, IPC_ES guiado). `_alternativas_desde._fecha`
hacía `_at_to_date(obs, …)` con `obs` 1-based SOBRE LOS RESIDUOS, cuando
`_at_to_date` quiere el 0-based SOBRE LA SERIE. Con d=1 y sin raíces
estacionales los dos errores se cancelaban; con una raíz interior la fecha
salía 2 meses pronto, con D=1 un año — y la alternativa trae la llamada lista
para ejecutar.

El mismo defecto, sin localizar en el informe, estaba en `_resid_start`: el eje
de la figura de diagnosis de los modelos del MEG se corría hacia atrás, y los
escaneos sobre residuos fechaban mal. Y en `escalera.py`, partido en dos líneas
con `\\`, que la guardia de BUG-0172 no sabía leer.
"""
import os
import pathlib
import re
import shutil
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as M
from art.describe import _resid_start
from tests._fuente import cuerpo_de

REPRO = pathlib.Path("bugs/BUG-0185-repro")


def _texto(o):
    return "\n".join(getattr(c, "text", "") or "" for c in o) if isinstance(o, list) else str(o)


# ── el caso real ──────────────────────────────────────────────────────────

def test_el_caso_del_run8_propone_el_mes_del_out(tmp_path):
    """IPC_ES m11: d=1 + raíz en f=2 (consume 3). El `.out` dice 12/2021; la
    alternativa decía 10/2021."""
    shutil.copy(REPRO / "IPC_ES_m10p.inp", tmp_path / "m10p.inp")
    warnings.simplefilter("ignore")
    t = _texto(getattr(M.estimate_and_diagnose, "fn", M.estimate_and_diagnose)(
        inp_path=str(tmp_path / "m10p.inp"), output_path=str(tmp_path / "m11.inp")))
    mo = re.search(r"Intervenir (\d\d/\d{4})", t)
    assert mo, "no se ofreció intervenir el residuo extremo"
    out = (tmp_path / "m11.out").read_text(encoding="latin-1")
    fecha_out = re.search(r"Maximum:\s+\S+\s+at\s+(\d\d/\d{4})", out).group(1)
    assert mo.group(1) == fecha_out == "12/2021", (
        f"la alternativa propone {mo.group(1)} y el .out dice {fecha_out}")


# ── _resid_start contra una verdad independiente ─────────────────────────

def _serie(n=144):
    r = np.random.default_rng(8)
    t = np.arange(n)
    y = 100 * np.exp(0.002 * t + 0.01 * np.sin(2 * np.pi * t / 12)
                     + 0.003 * np.cumsum(r.standard_normal(n)))
    return fue.TimeSeries(y.tolist(), freq=12, start=(2008, 1), name="S")


CONFIGS = {
    "d=0":            dict(d=0, ar=[[0.5]]),
    "d=1":            dict(d=1, ar=[[0.3]]),
    "d=1 + ifadf f=2": dict(d=1, ar=[[0.3]], ifadf=[0, 0, 1, 0, 0, 0, 0]),
    "d=1, D=1":       dict(d=1, D=1, ma=[[0.3]]),
}


@pytest.mark.parametrize("nombre", list(CONFIGS))
def test_el_primer_residuo_se_fecha_bien(nombre):
    """La verdad no sale de `desfase_observaciones` —eso sería comprobar la
    función consigo misma—: sale de alinear por la COLA. El último residuo es
    la última observación, así que el primero es la `nobs − n_res + 1`."""
    ts = _serie()
    warnings.simplefilter("ignore")
    m = fue.Model(ts, **CONFIGS[nombre])
    m.fit()
    n_res = int(np.size(m._result.residuals))
    yr, per = ts._obs_to_date(ts.nobs - n_res + 1)
    assert _resid_start(m) == (yr, per), f"{nombre}: el eje de los residuos se corre"


def test_sin_modelo_no_se_fecha():
    """Sin el modelo no se sabe el desfase: mejor el índice que una fecha falsa."""
    from art.diagnosis import diagnose
    ts = _serie()
    warnings.simplefilter("ignore")
    m = fue.Model(ts, d=1, ar=[[0.3]], ifadf=[0, 0, 1, 0, 0, 0, 0]); m.fit()
    y = np.asarray(ts.data, float).copy()
    alts = M._alternativas_desde(diagnose(m), model=None, ts=ts)
    assert not any(re.search(r"Intervenir \d\d/\d{4}", a) for a in alts)


# ── las guardias ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("donde", [("mcp_server", "_alternativas_desde"),
                                   ("describe", "_resid_start")])
def test_los_dos_sitios_usan_la_cuenta_comun(donde):
    # La cuenta común bajó a fue en fue/BUG-0023 (`differencing_offset`, y
    # `residuals_start` encima); `desfase_observaciones` delega en ella. Vale
    # cualquiera de los tres nombres: lo que la guardia prohíbe es la cuenta
    # escrita a mano, que caza `test_ningun_modulo_vuelve_a_escribir…`.
    import importlib
    mod = importlib.import_module(f"art.{donde[0]}")
    cuerpo = cuerpo_de(mod, donde[1])
    assert any(n in cuerpo for n in ("desfase_observaciones",
                                     "differencing_offset", "residuals_start"))


# La guardia de BUG-0172, ampliada: también `describe.py`, objetos con punto o
# índice (`vivos[0].model`) y la forma partida en dos líneas con `\`.
_GETATTR = re.compile(
    r"""getattr\(([\w.\[\]]+),\s*["']d["'][^\n]{0,40}\)\)?\s*\\?\s*\n?\s*"""
    r"""\+\s*int\(getattr\(\1,\s*["']D["']""")
_CORTA = re.compile(r"=\s*[\w.\[\]]+\.d\s*\+\s*[\w.\[\]]+\.D\s*\*")


def test_la_guardia_caza_la_forma_que_se_le_escapaba():
    viejo = ('_desf = int(getattr(vivos[0].model, "d", 0)) \\\n'
             '                + int(getattr(vivos[0].model, "D", 0)) * _f')
    assert _GETATTR.search(viejo)
    assert _CORTA.search("n_skip = model.d + model.D * freq")


def test_ningun_modulo_vuelve_a_escribir_la_cuenta_a_mano():
    malos = []
    for f in ("src/art/interventions.py", "src/art/configuracion.py",
              "src/art/escalera.py", "src/art/mcp_server.py",
              "src/art/describe.py"):
        txt = pathlib.Path(f).read_text(encoding="utf-8")
        if _GETATTR.search(txt) or _CORTA.search(txt):
            malos.append(f)
    assert not malos, f"desfase escrito a mano, sin las raíces estacionales: {malos}"
