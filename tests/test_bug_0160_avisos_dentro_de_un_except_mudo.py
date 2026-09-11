"""BUG-0160 — los avisos del método vivían dentro de un `except Exception: pass`.

Un aviso envuelto en un `except` mudo es un aviso que puede desaparecer sin
dejar rastro: si el bloque que lo compone falla, la salida sale igual de bien
formada, sólo que sin la advertencia. Y como la advertencia es justo lo que el
analista no sabe todavía, su ausencia no se nota.

No es una hipótesis. **El arreglo de BUG-0158 murió exactamente así**: leía la
verosimilitud del `.out`, tropezaba con la verdad de un array de numpy y caía en
un `except Exception: pass`. La herramienta siguió reestimando durante todo ese
tiempo, con la suite en verde, porque el número recalculado es el mismo.

`_warn` existe desde §4 precisamente para esto —su docstring dice «instead of
swallowing it silently»—. Cinco sitios no lo usaban. Que la regla estuviera
escrita y no se cumpliera es la misma enfermedad que BUG-0159: una propiedad que
sólo se sostiene si todo el mundo se acuerda es una costumbre, no una propiedad.
"""
import ast
import pathlib
import re

import pytest

_FUENTES = ("src/art/mcp_server.py", "src/art/pipeline.py",
            "src/art/describe.py")

# lo que delata a un bloque que compone una ADVERTENCIA y no un dato
_HUELLA = re.compile(r"\b(aviso|AVISO|advert)|⚠|ℹ")


def _bloques_mudos(ruta):
    src = pathlib.Path(ruta).read_text(encoding="utf-8")
    lin = src.split("\n")
    arb = ast.parse(src)
    funs = [f for f in ast.walk(arb) if isinstance(f, ast.FunctionDef)]
    malos = []
    for n in ast.walk(arb):
        if not isinstance(n, ast.Try):
            continue
        for h in n.handlers:
            if len(h.body) != 1 or not isinstance(h.body[0], ast.Pass):
                continue
            cuerpo = "\n".join(lin[n.lineno - 1:n.body[-1].end_lineno])
            if _HUELLA.search(cuerpo):
                d = [f.name for f in funs if f.lineno <= n.lineno <= f.end_lineno]
                malos.append(f"{ruta}:{h.lineno} ({d[-1] if d else '?'})")
    return malos


@pytest.mark.parametrize("ruta", _FUENTES)
def test_ningun_aviso_del_metodo_se_traga_su_fallo(ruta):
    if not pathlib.Path(ruta).exists():
        pytest.skip(f"no está {ruta}")
    malos = _bloques_mudos(ruta)
    assert not malos, (
        "estos bloques COMPONEN un aviso y se tragan el fallo en silencio — "
        "usa `_warn(contexto, exc)`, que existe para esto:\n  "
        + "\n  ".join(malos))


def test_warn_sigue_escribiendo_donde_se_ve(capsys):
    """El arreglo no vale si `_warn` se vuelve mudo: tiene que ir a stderr, que
    es lo que el carril MCP recoge en su log."""
    from art.mcp_server import _warn
    _warn("prueba de BUG-0160", ValueError("motivo"))
    cap = capsys.readouterr()
    assert "prueba de BUG-0160" in cap.err
    assert "ValueError" in cap.err and "motivo" in cap.err
    assert cap.out == "", "un aviso de servidor no va a stdout"


def test_el_aviso_de_covarianza_semilla_sigue_saliendo(tmp_path):
    """La comprobación de que el arreglo no rompió lo que protegía: el aviso más
    caro de perder —«estos errores típicos NO son válidos»— sigue componiéndose.
    Es el de BUG-0027, el que el estudio de campo vio invertir un veredicto de
    significación."""
    import os
    import numpy as np
    fue = pytest.importorskip("fue")
    os.environ.setdefault("ART_NO_VIEWER", "1")
    from art.mcp_server import _equation_for_prompt, _mirar
    from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar

    rng = np.random.default_rng(3)
    y = 100.0 + np.cumsum(rng.standard_normal(120))
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1995, 1), name="PR")
    f = str(tmp_path / "PR.inp")
    _write_inp(ts, fue.Model(ts, d=1, ar=[[0.0]], ar_free=[[True]], mu=0.0,
                             estimate_mu=False, refactor=_RESCALE_FACTOR), f)
    _, fit = estimar(f)
    fit.write_pre(f[:-4] + ".pre")

    _, m = _mirar(f[:-4] + ".pre")          # niter=0 ⇒ covarianza = semilla
    txt = _equation_for_prompt(m.series, m)
    assert "`.pre`" in txt or "errores típicos" in txt.lower(), (
        "se perdió el aviso sobre la procedencia/validez de las SE:\n" + txt)
