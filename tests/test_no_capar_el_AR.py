"""Nunca se capa un AR sin factorizar y contrastar antes (BUG-0103).

La escuela no sustituye un AR(6) por (1 − φ₆B⁶) porque la PACF enseñe un pico en
el retardo 6. Un operador en B^N impone que las N raíces tengan el MISMO módulo
y las frecuencias CLAVADAS en 2πk/N — N−1 restricciones, ninguna contrastada— y
un AR(6) puede ser perfectamente un AR(1)×AR(5) con amortiguamientos distintos.

Y hay una consecuencia que no es de gusto: **capar de entrada elimina la
posibilidad de contrastar Shin-Fuller**, porque la ruta MEG/DCD_f necesita
factores con su `d ± SE` y su `periodo ± SE`, y un operador ya restringido no
los tiene.

Ocurrió en UEM_HCPI_0219 y quedó registrado en el nodo v4 del guion: el
asistente propuso el AR disperso apelando al BIC y a las t, y hubo que
corregirlo a mano. El propio caso mide lo que se estaba imponiendo: la
factorización libre daba periodos 3.03 y 6.67 frente a los 3.00 y 6.00 que el
operador en B⁶ fija por decreto — 11.1% de desvío en el segundo.
"""
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.mcp_server import UMBRAL_MODULOS_PARECIDOS
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar

_AF = getattr(srv.ar_factorization, "fn", srv.ar_factorization)


def _ajusta(tmp_path, nombre, w, orden=6):
    y = 100.0 + np.cumsum(w)
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2000, 1), name=nombre)
    m = fue.Model(ts, d=1, ar=[[0.0] * orden], ar_free=[[True] * orden],
                  mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
    f = str(tmp_path / f"{nombre}.inp")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _write_inp(ts, m, f)
        estimar(f)
    return f


def _serie_b6(seed, n=300, th=0.78):
    """Generada POR un operador en B⁶: el caso donde el aviso debe salir."""
    rng = np.random.default_rng(seed)
    a = rng.standard_normal(n) * 0.3
    w = np.zeros(n)
    for t in range(6, n):
        w[t] = th ** 6 * w[t - 6] + a[t]
    return w


def _serie_libre(seed, n=300):
    """Amortiguamientos genuinamente distintos: no debe salir."""
    rng = np.random.default_rng(seed)
    a = rng.standard_normal(n) * 0.3
    w = np.zeros(n)
    for t in range(6, n):
        w[t] = 0.9 * w[t - 1] - 0.2 * w[t - 2] + 0.05 * w[t - 3] + a[t]
    return w


def test_avisa_cuando_los_modulos_son_casi_iguales(tmp_path):
    f = _ajusta(tmp_path, "b6", _serie_b6(3))
    t = _AF(f)[0].text
    assert "casi iguales" in t
    assert "la hipótesis, no el hallazgo" in t


def test_el_aviso_cuenta_las_restricciones(tmp_path):
    """Sin el recuento el aviso es una opinión; con él es un argumento."""
    f = _ajusta(tmp_path, "b6b", _serie_b6(3))
    t = _AF(f)[0].text
    assert "5 restricciones" in t and "4" in t
    assert "ninguna" in t.lower()


def test_el_aviso_nombra_la_ruta_correcta(tmp_path):
    """Un aviso que sólo prohíbe deja al asistente sin salida — y entonces
    impone igual, porque es lo único que puede hacer."""
    f = _ajusta(tmp_path, "b6c", _serie_b6(3))
    t = _AF(f)[0].text
    assert "FACTORIZADO" in t
    assert "exactamente identificada" in t
    assert "verosimilitudes" in t


def test_NO_avisa_con_amortiguamientos_distintos(tmp_path):
    """El falso positivo importa: si salta siempre, se ignora siempre."""
    f = _ajusta(tmp_path, "libre", _serie_libre(0))
    assert "casi iguales" not in _AF(f)[0].text


def test_la_tasa_de_acierto_se_sostiene(tmp_path):
    """SE FIJA LA TASA MEDIDA, NO UNA ABSOLUTA. Sobre 8 réplicas el aviso salta
    en 7: con n=300 la dispersión estimada de un proceso B⁶ va del 2.8% al 26%,
    y alguna réplica se sale del umbral.

    Exigir 8 de 8 sería fijar las semillas que funcionan y llamarlo garantía.
    Un aviso que falla una de cada ocho sigue siendo infinitamente mejor que
    ninguno — y quien lo lea no debe creer que es un detector infalible."""
    aciertos = sum("casi iguales" in _AF(
        _ajusta(tmp_path, f"b6_{s}", _serie_b6(s)))[0].text for s in range(8))
    assert aciertos >= 6, f"sólo {aciertos}/8: el umbral se ha estrechado"


def test_no_hay_falsos_positivos(tmp_path):
    """Éste sí se exige entero: si salta con amortiguamientos genuinamente
    distintos, se ignora siempre y deja de servir."""
    falsos = sum("casi iguales" in _AF(
        _ajusta(tmp_path, f"lb_{s}", _serie_libre(s)))[0].text for s in range(8))
    assert falsos == 0, f"{falsos}/8 falsos positivos"


def test_el_umbral_esta_medido_y_es_generoso():
    """Medido: el proceso B⁶ da dispersiones de 2.8% a 26.0% y los
    amortiguamientos libres de 22.8% a 83.7%. Se solapan, así que ningún umbral
    separa limpiamente — y no hace falta, porque esto avisa, no dictamina.

    La asimetría decide: un falso positivo cuesta un párrafo que el analista
    salta; un falso negativo cuesta imponer N−1 restricciones sin contrastar."""
    assert 0.10 <= UMBRAL_MODULOS_PARECIDOS <= 0.30


def test_un_AR_corto_no_dispara_nada(tmp_path):
    """Con menos de 4 raíces no hay «operador en B^N» que confundir."""
    rng = np.random.default_rng(4)
    a = rng.standard_normal(200) * 0.3
    w = np.zeros(200)
    for t in range(2, 200):
        w[t] = 0.5 * w[t - 1] + a[t]
    f = _ajusta(tmp_path, "corto", w, orden=2)
    assert "casi iguales" not in _AF(f)[0].text


# ── la doctrina, donde el LLM la lee ──────────────────────────────────

def test_la_doctrina_esta_en_las_instrucciones():
    """El asistente propuso capar creyendo que hacía lo correcto, y no estaba
    escrito en ninguna parte que no se hace."""
    ins = srv._INSTRUCTIONS
    assert "NUNCA SE CAPA UN AR" in ins
    assert "AR(1)×AR(5)" in ins, "el caso concreto que se pierde al capar"
    assert "Shin-Fuller" in ins, "lo que capar de entrada hace imposible"


def test_la_doctrina_da_el_procedimiento_completo():
    """Prohibir sin dar la ruta no sirve: el asistente impone igual porque es
    lo único que puede hacer."""
    ins = srv._INSTRUCTIONS
    for paso in ("COMPLETO", "ar_factorization", "FACTORIZADO",
                 "razón de verosimilitudes", "MEG"):
        assert paso in ins, paso


def test_la_doctrina_dice_que_el_BIC_no_autoriza():
    """Fue el argumento con el que se propuso: BIC mejor y t no significativas."""
    assert "Ni el BIC ni las t autorizan" in srv._INSTRUCTIONS


# ══════ La ruta correcta EXISTE: los cinco pasos, desde la superficie ══════

def _factoriza(coefs):
    """Los factores reales y complejos conjugados de un AR estimado."""
    raices = np.roots([1.0] + [-float(c) for c in coefs])
    facs, usados = [], set()
    for i, r in enumerate(raices):
        if i in usados:
            continue
        if abs(r.imag) < 1e-9:
            facs.append([float(r.real)])
            usados.add(i)
        else:
            j = next(k for k in range(i + 1, len(raices)) if k not in usados
                     and abs(raices[k] - np.conj(r)) < 1e-8)
            usados |= {i, j}
            facs.append([float(2 * r.real), float(-(abs(r) ** 2))])
    return facs


@pytest.fixture(scope="module")
def ciclo(tmp_path_factory):
    """Serie con un ciclo real, para que la factorización tenga qué encontrar."""
    d = tmp_path_factory.mktemp("fact")
    rng = np.random.default_rng(5)
    n = 300
    a = rng.standard_normal(n) * 0.3
    w = np.zeros(n)
    for i in range(6, n):
        w[i] = 1.4 * w[i - 1] - 0.75 * w[i - 2] + 0.2 * w[i - 3] + a[i]
    y = 100.0 + np.cumsum(w * 0.3)
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2000, 1), name="C")
    f = str(d / "C.inp")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _write_inp(ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                                 refactor=_RESCALE_FACTOR), f)
    return d, f


def _ll(f):
    from art.outfile import lee_out
    o = lee_out(os.path.splitext(f)[0] + ".out")
    return o.loglik, o.npar


def test_el_modelo_factorizado_se_puede_estimar_desde_la_superficie(ciclo):
    """Era lo que faltaba: `p` sólo aceptaba un entero, así que el paso 3 del
    procedimiento no existía y había que construir el `.inp` a mano."""
    d, f = ciclo
    ce = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ce(f, str(d / "fac.inp"), lam=0.0, d=1, D=0, p=[2, 1, 1], q=0,
           n_harmonics=0, seasonal=False, estimate_mu=True,
           guion_decision="factorizado")
    from art.pipeline import mirar
    _, m = mirar(str(d / "fac.inp"))
    assert [len(x) for x in m.ar] == [2, 1, 1]


def test_la_reparametrizacion_reproduce_la_VEROSIMILITUD(ciclo):
    """«Exactamente identificada» significa esto y hay que comprobarlo: mismos
    parámetros reagrupados, misma ℓ, mismos grados de libertad. Si no
    coincidiera, el paso 3 no sería una reparametrización sino otro modelo."""
    d, f = ciclo
    ce = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ce(f, str(d / "p1.inp"), lam=0.0, d=1, D=0, p=4, q=0, n_harmonics=0,
           seasonal=False, estimate_mu=True, guion_decision="base")
        from art.pipeline import mirar
        _, m1 = mirar(str(d / "p1.inp"))
        facs = _factoriza(m1.ar[0])
        ce(f, str(d / "p2.inp"), lam=0.0, d=1, D=0,
           p=[len(x) for x in facs], q=0, ar_seeds=facs, n_harmonics=0,
           seasonal=False, estimate_mu=True, guion_decision="fact")
    l1, k1 = _ll(str(d / "p1.inp"))
    l2, k2 = _ll(str(d / "p2.inp"))
    assert k1 == k2, "mismos grados de libertad"
    assert abs(l1 - l2) < 1e-4, f"ℓ difiere en {l1 - l2}: no es reparametrización"


def test_SIN_semillas_la_reparametrizacion_NO_reproduce_la_verosimilitud(ciclo):
    """Y por eso `ar_seeds` no es comodidad. La identidad es ALGEBRAICA; el
    optimizador es una búsqueda local, y arrancando de semillas neutras cae en
    otro sitio. Medido: 8 puntos de ℓ peor.

    Quien haga el paso 3 sin pasar las semillas de `ar_factorization` creerá que
    la reparametrización «empeora el ajuste», que es falso y le hará descartar
    el camino correcto."""
    d, f = ciclo
    ce = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ce(f, str(d / "sinsem.inp"), lam=0.0, d=1, D=0, p=[2, 2], q=0,
           n_harmonics=0, seasonal=False, estimate_mu=True,
           guion_decision="sin semillas")
    l_sin, _ = _ll(str(d / "sinsem.inp"))
    l_con, _ = _ll(str(d / "p1.inp"))
    assert l_sin < l_con - 1.0, "sin semillas debería caer en otro óptimo"


def test_el_AR2_de_frecuencia_fija_es_estimable(ciclo):
    """El paso 4: la versión CONTRASTABLE de «este factor es estacional».
    Anidada en el factor libre, así que su LR con 1 g.l. la decide — en vez de
    imponerla, que es lo único que se podía hacer antes."""
    d, f = ciclo
    ce = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ce(f, str(d / "ffix.inp"), lam=0.0, d=1, D=0, p=[2], q=0,
           ar_f_freqs=[2], n_harmonics=0, seasonal=False, estimate_mu=True,
           guion_decision="ffix")
    from art.pipeline import mirar
    _, m = mirar(str(d / "ffix.inp"))
    assert [int(x.freq) for x in (m.ar_f or [])] == [2]
    l_lib, k_lib = _ll(str(d / "p2.inp"))
    l_fij, k_fij = _ll(str(d / "ffix.inp"))
    assert k_fij < k_lib, "restringir tiene que gastar menos parámetros"


def test_p_entero_sigue_significando_lo_mismo(ciclo):
    """El entero se conserva porque es el caso particular de un factor, no
    porque haya dos formas de decirlo: por dentro sólo hay una."""
    from art.pipeline import ordenes_ar
    assert ordenes_ar(6) == [6]
    assert ordenes_ar([1, 1, 2, 2]) == [1, 1, 2, 2]
    assert ordenes_ar(0) == [] and ordenes_ar(None) == [] and ordenes_ar([]) == []


def test_la_herramienta_documenta_las_tres_cosas():
    from tests._fuente import fuente_de
    ce = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
    src = fuente_de(ce)
    assert "LIST OF ORDERS PER FACTOR" in src
    assert "EXACTLY IDENTIFIED" in src
    assert "Shin-Fuller" in src
    assert "ar_f_freqs" in src and "NAILED" in src
