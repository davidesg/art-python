"""Los tres defectos de PRESENTACIÓN del nodo de intervención — 0152, 0153, 0154.

Van juntos porque son la misma pantalla: arreglarlos por separado obliga a
releerla tres veces. Y los tres son la misma familia — no hay un número mal
calculado en ninguno; lo que falla es lo que la salida AFIRMA con los números
que tiene bien.

    0152  el rótulo toma como sujeto la BANDA y la decisión es sobre el MODELO
    0153  el pie de la figura y el veredicto dicen cosas OPUESTAS
    0154  el mismo veredicto, TRES veces, en la respuesta más larga del nodo
"""
import os
import tempfile

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.calibracion import Distorsion, calibra_correlograma, describe_calibracion


# ═════════════════════ BUG-0152 — nombrar lo que se decide ═════════════════

def test_el_flip_habla_del_MODELO_no_de_la_banda():
    """«ENTRA»/«SALE» tomaban como sujeto la banda: «entra EN LA BANDA». Lo que
    el analista decide con la fila va al revés — una señal que entra en la banda
    es un orden que SALE del modelo. El cálculo estaba bien; el nombre invertía
    la conclusión, y el analista lo anotó corriendo ITCER."""
    d = Distorsion(lag=2, banda=0.2, acf_obs=0.10, acf_cal=0.30,
                   pacf_obs=-0.30, pacf_cal=-0.10)
    assert d.acf_flip == "enmascarada"    # dentro → fuera: el anómalo la tapaba
    assert d.pacf_flip == "fabricada"     # fuera → dentro: el anómalo la inventaba
    assert d.acf_flip not in ("entra", "sale")


def test_la_direccion_es_la_que_es_y_no_la_contraria():
    """Lo que la prueba tiene que fijar es la DIRECCIÓN, no el texto: para un
    retardo fuera de banda que al calibrar entra, el anómalo la FABRICABA."""
    fabricada = Distorsion(lag=1, banda=0.2, acf_obs=0.50, acf_cal=0.05,
                           pacf_obs=0.0, pacf_cal=0.0)
    assert fabricada.acf_flip == "fabricada"
    enmascarada = Distorsion(lag=1, banda=0.2, acf_obs=0.05, acf_cal=0.50,
                             pacf_obs=0.0, pacf_cal=0.0)
    assert enmascarada.acf_flip == "enmascarada"


def _con_flip():
    """Serie AR(1) con un atípico que fabrica señal en algún retardo."""
    rng = np.random.default_rng(4)
    n = 160
    y = np.zeros(n)
    for t in range(1, n):
        y[t] = 0.55 * y[t - 1] + rng.standard_normal() * 0.5
    y[80] += 9.0
    return y


def test_la_tabla_se_lee_sin_glosa():
    cal = calibra_correlograma(_con_flip(), umbral=3.0)
    txt = describe_calibracion(cal).summary
    assert "FABRICADA" in txt or "ENMASCARADA" in txt, (
        "ningún retardo cambió de veredicto: el testigo dejó de valer")
    # la glosa dice lo que pasa CON EL MODELO, que es lo que se decide
    assert "sobra" in txt and "falta" in txt
    # y ya no se nombra la banda como sujeto
    assert "«SALE» = estaba dentro" not in txt


def test_el_veredicto_no_dice_la_palabra_dos_veces_en_la_misma_linea():
    """Llevaba el rótulo entre paréntesis y la frase completa a continuación:
    «(fabricada) — una señal AR que el anómalo fabricaba»."""
    cal = calibra_correlograma(_con_flip(), umbral=3.0)
    txt = describe_calibracion(cal).summary
    for linea in txt.splitlines():
        if linea.startswith("- **PACF(") or linea.startswith("- **ACF("):
            bajo = linea.lower()
            assert bajo.count("fabricada") + bajo.count("fabricaba") <= 1, linea
            assert bajo.count("enmascarada") + bajo.count("enmascaraba") <= 1, linea


# ═════════ BUG-0153 — el pie y el veredicto salen del mismo sitio ═══════════

def test_una_Q_que_PASA_no_puede_decir_que_falta_estructura():
    """«Falta estructura» sólo significa algo cuando hay estructura que falte.
    Sobre ITCER m00 el pie lo decía con Q(15)=10,4 —adecuada— mientras el
    veredicto de la tabla decía que el anómalo FABRICABA la señal."""
    from art.describe import _lectura_de_la_q
    l = _lectura_de_la_q(q_obs=10.4, q_p=0.79, efecto=-3.0)
    assert l.clave == "q_adecuada"
    assert "missing" not in l.pie and "falta estructura" not in l.texto
    assert "ya pasa" in l.texto


def test_con_la_Q_rechazando_los_diagnosticos_siguen_igual():
    """El arreglo no puede callar donde sí hay algo que decir."""
    from art.describe import _lectura_de_la_q
    assert _lectura_de_la_q(40.0, 0.001, -70.0).clave == "la_ponian_los_anomalos"
    assert _lectura_de_la_q(40.0, 0.001, +30.0).clave == "enmascaraba"
    assert _lectura_de_la_q(40.0, 0.001, -5.0).clave == "falta_estructura"
    assert _lectura_de_la_q(40.0, 0.001, -30.0).clave == "mixto"


def test_sin_efecto_no_se_inventa_una_lectura():
    from art.describe import _lectura_de_la_q
    assert _lectura_de_la_q(10.0, 0.5, None).clave == "sin_datos"
    assert _lectura_de_la_q(None, None, -50.0).clave == "sin_datos"


def test_el_pie_y_el_texto_NO_pueden_divergir():
    """Eran dos clasificaciones independientes con umbrales distintos sobre la
    misma cifra. La única forma de que no vuelvan a contradecirse es que salgan
    de la misma función, y eso se comprueba estructuralmente."""
    import ast
    import pathlib
    src = pathlib.Path("src/art/describe.py").read_text()
    arbol = ast.parse(src)
    fn = next(f for f in ast.walk(arbol)
              if isinstance(f, ast.FunctionDef) and f.name == "_lectura_de_la_q")
    dentro = "\n".join(src.split("\n")[fn.lineno - 1:fn.end_lineno])

    # Las frases del diagnóstico existen EN UN SOLO SITIO, y es ése. Se cuenta
    # sobre el código, no sobre el fichero: los comentarios citan el texto
    # viejo a propósito —es la explicación del defecto— y contarlos haría que
    # documentar el arreglo rompiera la prueba.
    sin_comentarios = "\n".join(
        l for l in src.split("\n") if not l.lstrip().startswith("#"))
    for frase in ("structure is missing", "falta estructura, y una",
                  "the anomalies were making Q"):
        assert sin_comentarios.count(frase) == 1, (
            f"«{frase}» está en más de un sitio: alguien volvió a clasificar "
            f"por su cuenta")
        assert frase in dentro, f"«{frase}» no está en `_lectura_de_la_q`"


def test_el_escaneo_publica_la_Q_con_su_p():
    """Nadie miraba si la Q pasa porque la salida no publicaba la p."""
    from art.describe import describe_prelim_scan as _s
    rng = np.random.default_rng(9)
    y = np.cumsum(rng.standard_normal(150) * 0.5) + 100.0
    y[70] += 9.0
    d = _s(fue.TimeSeries(y.tolist(), freq=4, start=(1990, 1), name="Q"),
           lam=1.0, d=1, D=0)
    assert d.data.get("q_pvalue") is not None
    assert d.data.get("q_lectura")
    assert "p=" in d.summary


# ═════════════ BUG-0154 — un veredicto, una vez, donde se decide ═══════════

@pytest.fixture(scope="module")
def llamada2(tmp_path_factory):
    from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar
    import art.mcp_server as srv
    rng = np.random.default_rng(3)
    n = 120
    y = 100.0 + np.cumsum(rng.standard_normal(n) * 0.5)
    y[60:] += -1.0
    y[61:] += -5.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1995, 1), name="X")
    f = str(tmp_path_factory.mktemp("v") / "X.inp")
    _write_inp(ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                             refactor=_RESCALE_FACTOR, ar=[[0.0]],
                             ar_free=[[True]]), f)
    estimar(f)
    fn = getattr(srv.guided_intervention, "fn", srv.guided_intervention)
    return "\n".join(getattr(x, "text", "")
                     for x in fn(inp_path=f, date="Q2/2010"))


def test_el_veredicto_se_enuncia_UNA_vez(llamada2):
    """Estaba tres veces: en el bloque de la configuración, en «Veredicto» y en
    el pie de la respuesta. Repetir entierra lo que NO se repite — las
    configuraciones rivales, la lectura de dominio, el aviso de que el dato no
    identifica."""
    frase = "escalones consecutivos en el nivel"
    lineas = [l for l in llamada2.splitlines() if frase in l]
    # la leyenda de la notación NO es el veredicto: explica cómo se lee «fecha×N»
    veredictos = [l for l in lineas if "Se lee «fecha×N»" not in l]
    assert len(veredictos) == 1, (
        f"{len(veredictos)} enunciados del veredicto:\n" + "\n".join(veredictos))


def test_y_se_enuncia_donde_se_DECIDE(llamada2):
    i_ver = llamada2.index("## Veredicto")
    i_fra = llamada2.index("escalones consecutivos en el nivel**")
    assert i_fra > i_ver, "el veredicto no está en la sección que lo anuncia"


def test_el_bloque_de_configuraciones_sigue_diciendo_CUAL_gana(llamada2):
    """Quitar la repetición no puede quitar el hecho: cuál gana y con cuánto
    margen es lo que ese bloque aporta."""
    i = llamada2.index("sí** identifica la configuración")
    tramo = llamada2[i:i + 300]
    assert "×" in tramo, "ya no dice qué configuración gana"
    assert "Se construyeron" in tramo


def test_la_recomendacion_es_lo_que_TOCA_HACER(llamada2):
    assert "Construye la forma del veredicto" in llamada2
    assert "form=" in llamada2.split("---")[-1]


def test_suelto_incident_configurations_sigue_con_su_veredicto():
    """El bloque empotrado calla porque quien lo empotra habla. Suelto es lo
    único que hay, y ahí tiene que seguir enunciándolo entero."""
    from art.configuracion import (Candidato, ConjuntoCandidatos,
                                   describe_configuraciones)
    c = Candidato(arranque_resid=17, n_escalones=3, aic=381.9, omega_1=-21.2,
                  se_omega_1=3.9, wald_p=1e-7, fecha="Q2/2008",
                  fecha_fin="Q4/2008", etiqueta="Q2/2008×3", model=object())
    conj = ConjuntoCandidatos(candidatos=[c])
    def _veredictos(t):
        # la leyenda de la notación no es el veredicto
        return [l for l in t.splitlines()
                if "escalones consecutivos en el nivel" in l
                and "Se lee «fecha×N»" not in l]

    assert len(_veredictos(describe_configuraciones(conj).summary)) == 1
    empotrado = describe_configuraciones(conj, veredicto=False).summary
    assert _veredictos(empotrado) == []
    assert "Q2/2008×3" in empotrado, "el empotrado tiene que decir CUÁL gana"
