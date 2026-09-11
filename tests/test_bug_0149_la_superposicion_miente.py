"""BUG-0149 — la superposición dibujaba el NIVEL sobre residuos en ∇.

Es la figura a la que BUG-0138 le dio el trabajo de argumentar: al quitar la
escalera del carril guiado por defecto, la superposición pasó a llevar la
sugerencia. Estaba rota, así que el nodo se quedó sin argumento por los dos
lados.

Dos causas, y las dos son un dato que no cruza una frontera:

**a) el llamador no pasaba `d`.** Lo observado son residuos en ∇ y `superpone`
tomaba `d=0`, o sea que simulaba la respuesta al escalón EN EL NIVEL. Un escalón
permanente en el nivel no vuelve nunca a cero, y el soporte se definía como «el
último índice con respuesta ≠ 0» → la ventana entera. Sobre ITCER: 17 trimestres
de sombra, y la escala por mínimos cuadrados —que divide por la suma de 17
residuos ≈0— se iba a **×−0,0219**: una línea plana presentada como «la
hipótesis».

**b) el llamador pasaba el `at` equivocado**: `ep.inicio`, la fecha del extremo
que ABRIÓ el episodio, en vez del arranque de la configuración que se dibuja.
Para `Q2/2008×3` son dos períodos, y la hipótesis cae sobre datos que no le
corresponden.

El arreglo de fondo es el soporte: el de una intervención es el de su OPERADOR
—tantos períodos como coeficientes ω—, que vale en los dos espacios y no depende
de que la respuesta decaiga.
"""
import numpy as np
import pytest

fue = pytest.importorskip("fue")
from art.ltf import superpone, describe_superposicion


OMEGA = [-4.0, -5.0, -11.0]


def _caso(omega=None, at=40, n=120, ruido=0.3, semilla=3):
    """Ruido con la respuesta EXACTA de esos ω incrustada en ∇.

    Se genera desde `respuesta_flt` y no escribiendo los escalones a mano: el
    numerador de `fue` va con el convenio de Box-Jenkins —los retardos entran
    RESTANDO, ω(B) = ω₀ − ω₁B − ω₂B²— y una construcción a mano acaba probando
    si el que escribe la prueba se acuerda del signo, que no es lo que se
    quiere probar. Generándola desde la misma función, la hipótesis encaja por
    construcción y la escala tiene que salir ≈1.
    """
    from art.ltf import respuesta_flt
    omega = list(omega if omega is not None else OMEGA)
    rng = np.random.default_rng(semilla)
    obs = rng.standard_normal(n) * ruido
    r = respuesta_flt(omega, (), b=0, K=n, d=1)      # el camino en ∇
    for k, v in enumerate(r.srf):
        j = at - 1 + k
        if j < n:
            obs[j] += v
    return obs, at


# ────────── el soporte, que es la causa de fondo ──────────

def test_el_soporte_es_el_del_OPERADOR_y_no_la_ventana():
    """Con tres ω el soporte son tres períodos, se mire en ∇ o en el nivel.

    Antes, con `d=0`, la respuesta al escalón no volvía a cero y el soporte
    salía igual a la ventana simulada: 17 períodos de sombra sobre un incidente
    de tres.
    """
    obs, at = _caso()
    for d in (0, 1):
        sp = superpone(obs.tolist(), at, OMEGA, d=d, ventana=8)
        assert sp.soporte == 3, f"d={d}: soporte {sp.soporte}, deberían ser 3"


def test_un_impulso_con_un_solo_omega_tiene_soporte_uno():
    obs, at = _caso(omega=[-9.0])
    sp = superpone(obs.tolist(), at, [-9.0], d=1, ventana=8, entrada="impulso")
    assert sp.soporte == 1


# ────────── la escala, que es el síntoma que se vio ──────────

def test_la_escala_no_se_desploma_a_cero():
    """Con la hipótesis correcta la escala tiene que salir ≈1: es «esta forma,
    a este tamaño». La que el analista vio era ×−0,0219."""
    obs, at = _caso()
    sp = superpone(obs.tolist(), at, OMEGA, d=1, ventana=8)
    assert 0.7 < sp.escala < 1.4, f"escala {sp.escala:.4f}"
    assert sp.r2_soporte > 0.8, f"R² en el soporte {sp.r2_soporte:.3f}"


# ────────── el cinturón: que el llamado eche en falta el dato ──────────

def test_con_d_fuera_de_rango_lo_DICE_en_vez_de_dibujar_mal():
    obs, at = _caso()
    with pytest.raises(ValueError, match="d=2"):
        superpone(obs.tolist(), at, OMEGA, d=2, ventana=8)


# ────────── y que la figura salga en el espacio correcto ──────────

def test_el_eje_dice_nabla_cuando_se_mira_en_diferencias():
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.text import Text
    import art.describe as _d

    obs, at = _caso()
    vistos = []
    real = _d._fig_b64
    _d._fig_b64 = lambda f, *a, **k: (
        vistos.append([t.get_text() for t in f.findobj(Text)]), real(f, *a, **k))[1]
    try:
        describe_superposicion(obs.tolist(), at, OMEGA, d=1,
                               ventana=8, freq=4, start=(2000, 1), desfase=1)
    finally:
        _d._fig_b64 = real
    txt = " ".join(vistos[-1])
    assert "∇" in txt, txt
    assert "level" not in txt, "el eje dice «level» sobre datos en ∇"


# ────────── el sitio de llamada, que es donde se vio ──────────

def test_es_el_SOPORTE_lo_que_desplomaba_la_escala():
    """Cuál de las dos causas producía el síntoma — medido, no supuesto.

    Al arreglarlo se vio que las dos causas no pesan igual: **el desplome de la
    escala lo producía enteramente el soporte**. Con el soporte acotado al
    operador, pasar `d=0` sobre datos en ∇ da escala 0,979 frente a 1,029 —una
    diferencia menor—; lo que daba ×−0,0219 era la ventana entera de sombra
    dividiendo por una suma de residuos que se cancela.

    `d` sigue importando por otra razón: gobierna el rótulo del eje y la forma
    simulada. Pero atribuirle el desplome sería contar mal la causa.
    """
    obs, at = _caso(ruido=0.6, n=200)
    bien = superpone(obs.tolist(), at, OMEGA, d=1, ventana=8)
    mal = superpone(obs.tolist(), at, OMEGA, d=0, ventana=8)
    assert bien.soporte == mal.soporte == 3
    assert 0.7 < bien.escala < 1.4 and 0.7 < mal.escala < 1.4, (
        f"con el soporte acotado ninguna de las dos se desploma: "
        f"{bien.escala:.4f} / {mal.escala:.4f}")
    # el soporte es lo que no puede volver a soltarse
    largo = superpone(obs.tolist(), at, OMEGA, d=1, ventana=20)
    assert largo.soporte == 3, "la ventana no puede decidir el soporte"


def test_la_llamada_2_pasa_d_y_el_arranque_de_la_CONFIGURACION():
    """Los dos datos que el llamador no pasaba.

    `at` era `ep.inicio` —la fecha del extremo que ABRIÓ el episodio— y no el
    arranque de la configuración que se dibuja; para `Q2/2008×3` son dos
    períodos de diferencia. `Candidato.arranque_resid` ya traía la posición
    buena, 1-based en residuos, que es justo el índice que `at` espera.
    """
    import ast
    import inspect
    from pathlib import Path

    import art.mcp_server as M

    src = Path(M.__file__).read_text(encoding="utf-8")
    # la llamada dentro de `guided_intervention`
    gi = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "guided_intervention")
    llamadas = [c for c in ast.walk(gi) if isinstance(c, ast.Call)
                and getattr(c.func, "id", "") == "describe_superposicion"]
    assert llamadas, "la llamada 2 ya no dibuja la superposición"
    for c in llamadas:
        kw = {k.arg: ast.unparse(k.value) for k in c.keywords}
        assert "d" in kw, "la llamada no pasa `d`: dibujará el nivel sobre ∇"
        assert "arranque_resid" in kw.get("at", ""), (
            f"`at` no sale del arranque de la configuración: {kw.get('at')}")
