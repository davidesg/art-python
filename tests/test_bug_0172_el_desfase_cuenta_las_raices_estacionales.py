"""BUG-0172 — el desfase de observaciones no contaba las raíces estacionales.

Los residuos de un modelo diferenciado empiezan N observaciones después de la
serie. `d` consume 1 cada una, `D` consume `s` cada una… y **cada raíz
estacional estocástica de `ifadf` consume el grado de su factor**: 2 en una
frecuencia interior `(1 − 2cos(ω)B + B²)`, 1 en el Nyquist `(1 + B)`.

Ese tercer sumando faltaba, y faltaba en **CINCO sitios**, cada uno con la
cuenta escrita a mano como `d + D·s`:

    configuracion.py   las configuraciones candidatas del incidente
    escalera.py        el arranque de los peldaños
    interventions.py   la regla de Treadway
    mcp_server.py ×2   la fecha de un episodio, y DÓNDE se coloca la
                       intervención que el analista pide

Los dos últimos son los graves: no desplazan una etiqueta, **desplazan el
modelo**. Sobre `ES_CPI_B_m11` del run 3 —dos frecuencias reformuladas, consumo
4— una intervención pedida para 03/2022 se colocaba en 07/2022.

Y Treadway publicaba «2 de 4 pasan» leyendo los residuos de cuatro meses
después. Pasan las cuatro.
"""
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.identification import desfase_observaciones
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar


def _modelo(ifadf_en=(), d=1, D=0, n=200, s=12):
    rng = np.random.default_rng(7)
    y = 100.0 + np.cumsum(rng.standard_normal(n) * 0.4)
    ts = fue.TimeSeries(y.tolist(), freq=s, start=(2002, 1), name="D")
    ifa = [0] * (s // 2 + 1)
    for f in ifadf_en:
        ifa[f] = 1
    return fue.Model(ts, d=d, D=D, mu=0.0, estimate_mu=False,
                     refactor=_RESCALE_FACTOR, ifadf=ifa)


# ── la cuenta, contra el recuento REAL de residuos ─────────────────────────

@pytest.mark.parametrize("ifadf_en,d,D,esperado", [
    ((),      1, 0, 1),
    ((),      2, 0, 2),
    ((),      1, 1, 13),
    ((3,),    1, 0, 3),     # una interior: +2
    ((2, 3),  1, 0, 5),     # dos interiores: +4
    ((6,),    1, 0, 2),     # Nyquist (s=12 → f=6): +1
    ((2, 6),  1, 0, 4),     # una interior + Nyquist: +3
])
def test_el_desfase_es_el_que_consume_de_verdad(ifadf_en, d, D, esperado, tmp_path):
    """No se argumenta: se compara con cuántos residuos devuelve el motor."""
    m = _modelo(ifadf_en, d=d, D=D)
    assert desfase_observaciones(m) == esperado
    f = str(tmp_path / f"M{len(ifadf_en)}{d}{D}.inp")
    _write_inp(m.series, m, f)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, mf = estimar(f)
    real = mf.series.nobs - len(mf._result.residuals)
    assert desfase_observaciones(mf) == real, (
        f"la cuenta dice {desfase_observaciones(mf)} y el motor consume {real}")


def test_sin_ifadf_no_cambia_nada():
    """El arreglo no puede mover los modelos que no tienen raíces estacionales,
    que son la mayoría."""
    for d, D, esp in ((0, 0, 0), (1, 0, 1), (2, 0, 2), (1, 1, 13), (0, 1, 12)):
        assert desfase_observaciones(_modelo((), d=d, D=D)) == esp


# ── y los CINCO sitios la usan ─────────────────────────────────────────────

def test_ningun_sitio_vuelve_a_escribir_la_cuenta_a_mano():
    """Escrita en cinco sitios es una costumbre: basta que alguien añada un
    operador nuevo para que vuelva a divergir. La prueba es sobre el fuente
    porque el defecto es de DUPLICACIÓN, no de valor."""
    import pathlib
    import re
    # ACOTADA a una sentencia: con `re.S` sin límite cruzaba líneas hasta una
    # `D` lejana y marcaba `d_reg = int(getattr(m, "d", 0))`, que es otra cosa
    # —el `d` que `decide_episodios` usa para agrupar extremos, no un desfase—.
    # Una prueba sobre el fuente tiene que acotar su ventana o inventa defectos.
    patron = re.compile(
        r"""=[^\n]{0,80}int\(getattr\((\w+),\s*["']d["'][^\n]{0,40}\)"""
        r"""\s*\+\s*int\(getattr\(\1,\s*["']D["']""")
    malos = []
    for f in ("src/art/interventions.py", "src/art/configuracion.py",
              "src/art/escalera.py", "src/art/mcp_server.py"):
        txt = pathlib.Path(f).read_text(encoding="utf-8")
        if patron.search(txt):
            malos.append(f)
        # la forma corta, sin getattr
        if re.search(r"=\s*\w+\.d\s*\+\s*\w+\.D\s*\*", txt):
            malos.append(f + " (forma corta)")
    assert not malos, (
        "vuelven a calcular el desfase a mano en vez de usar "
        f"`desfase_observaciones`: {malos}")


@pytest.mark.parametrize("modulo", [
    "src/art/interventions.py", "src/art/configuracion.py",
    "src/art/escalera.py", "src/art/mcp_server.py"])
def test_los_cuatro_modulos_la_IMPORTAN(modulo):
    import pathlib
    assert "desfase_observaciones" in pathlib.Path(modulo).read_text(encoding="utf-8")


# ── el caso real del run 3 ─────────────────────────────────────────────────

_B11 = os.path.expanduser(
    "~/Dropbox/SF_MEG/empirical/run3/ES_CPI_B_m11.inp")


@pytest.mark.skipif(not os.path.exists(_B11), reason="falta el caso del run 3")
def test_treadway_lee_las_fechas_INTERVENIDAS_y_no_las_de_cuatro_meses_despues():
    """El caso medido: publicaba «2 de 4 pasan» con un z de −2,91 que era el de
    09/2022, no el de 03/2022. Pasan las cuatro."""
    import warnings

    from art.interventions import check_intervention_fit
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ts, m = estimar(_B11)
    assert desfase_observaciones(m) == 5, "el testigo cambió"
    chks = check_intervention_fit(m)
    assert len(chks) == 4
    assert all(c.funciona for c in chks), (
        "sigue leyendo residuos desplazados: "
        + str([[round(z, 2) for z in c.z_en_fechas] for c in chks]))
    # y ningún z de los leídos se parece al −2.91 de 09/2022
    assert all(abs(z) < 2.0 for c in chks for z in c.z_en_fechas)
