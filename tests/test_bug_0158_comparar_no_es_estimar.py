"""BUG-0158 — comparar dos modelos no es reestimarlos.

`compare_versions` llamaba a `_load_fitted` sobre los dos ficheros: reestimaba
teniendo el `.out` delante. El coste barato es el tiempo (25,4 ms frente a 2,9);
el caro es que si lo que se compara es un `.pre` —o un `.inp` escrito tras
ajustar, que es el caso NORMAL en una cadena de versiones— el optimizador
arranca en el óptimo, apenas itera y la covarianza se queda en la semilla del
BFGS. La herramienta cuyo trabajo es comparar era la que más fácilmente
publicaba errores típicos inválidos, justo cuando el analista los mira para
decidir si poda un parámetro.

El `.out` publica la verosimilitud con precisión completa. El campo se llama
`logelf` —«la calculada con `elf` en la última iteración», en palabras del
analista— y de ahí salen ℓ, AIC y BIC sin tocar el motor.
"""
import os
import re

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.outfile import lee_out
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar


@pytest.fixture(scope="module")
def dos_versiones(tmp_path_factory):
    """Dos modelos anidados sobre la MISMA serie: AR(1) y ARMA(1,1)."""
    d = tmp_path_factory.mktemp("cmp0158")
    rng = np.random.default_rng(7)
    w = rng.standard_normal(140)
    y = 100.0 + np.cumsum(w + 0.35 * np.r_[0.0, w[:-1]])
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1990, 1), name="CMP")

    rutas = []
    for nom, kw in (("CMP_m00", dict(ar=[[0.0]], ar_free=[[True]])),
                    ("CMP_m01", dict(ar=[[0.0]], ar_free=[[True]],
                                     ma=[[0.0]], ma_free=[[True]]))):
        f = str(d / f"{nom}.inp")
        _write_inp(ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                                 refactor=_RESCALE_FACTOR, **kw), f)
        _, fit = estimar(f)
        fit.write_pre(str(d / f"{nom}.pre"))
        fit.write_out(str(d / f"{nom}.out"))
        rutas.append(f)
    return tuple(rutas)


def _texto(res):
    return "\n".join(getattr(x, "text", "") for x in res)


def test_comparar_no_estima(dos_versiones):
    """La comprobación estructural: si vuelve a estimar, vuelve el defecto."""
    from tests._fuente import cuerpo_de
    c = cuerpo_de(srv.compare_versions)
    assert "_load_fitted(" not in c and "estimar(" not in c, \
        "compare_versions volvió a estimar"
    assert "_mirar(" in c


def test_la_verosimilitud_VIAJA_desde_el_out(dos_versiones):
    """La comprobación que no se puede fingir: se altera el `logelf` del `.out`
    a un valor imposible de reproducir estimando. Si la herramienta lo imprime,
    lo ha LEÍDO; si imprime el de verdad, lo ha recalculado."""
    f_a, f_b = dos_versiones
    out_a = f_a[:-4] + ".out"
    real = lee_out(out_a).loglik
    assert real is not None, "el `.out` no publica `logelf`"

    centinela = -424.242424
    txt = open(out_a, encoding="utf-8", errors="replace").read()
    open(out_a, "w", encoding="utf-8").write(
        re.sub(r"^logelf:.*$", f"logelf: {centinela:.10f}", txt, flags=re.M))
    try:
        salida = _texto(srv.compare_versions(f_a, f_b))
    finally:
        open(out_a, "w", encoding="utf-8").write(txt)

    assert "-424.24" in salida or "−424.24" in salida, (
        "la ℓ no viene del `.out`: la herramienta la recalculó\n" + salida[:600])


def test_y_el_AIC_se_construye_con_esa_verosimilitud(dos_versiones):
    """ℓ leída y AIC recalculado por su cuenta sería peor que no leerla: los dos
    números se presentan juntos y el analista los compara entre sí."""
    f_a, f_b = dos_versiones
    o = lee_out(f_a[:-4] + ".out")
    esperado = -2 * o.loglik + 2 * o.npar
    salida = _texto(srv.compare_versions(f_a, f_b))
    nums = [float(x) for x in re.findall(r"-?\d+\.\d+", salida)]
    assert any(abs(v - esperado) < 0.05 for v in nums), (
        f"AIC={esperado:.2f} (de logelf={o.loglik:.4f}, k={o.npar}) no aparece")


def test_sin_out_sigue_funcionando(dos_versiones, tmp_path):
    """El `.out` es el registro PREFERIDO, no un requisito: un `.inp` recién
    escrito todavía no lo tiene, y comparar tiene que seguir siendo posible."""
    import shutil
    f_a, f_b = dos_versiones
    copia = str(tmp_path / "CMP_m00.inp")
    shutil.copy(f_a, copia)                       # sin `.out` al lado
    salida = _texto(srv.compare_versions(copia, f_b))
    assert "Traceback" not in salida and "❌" not in salida
    assert "AIC" in salida
