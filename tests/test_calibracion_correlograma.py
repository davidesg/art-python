"""La calibración del correlograma — cuánto de lo que ves es el anómalo.

Dos funciones, dos decisiones: **la PACF decide el orden AR y la ACF el MA**.
Calibrar sólo una deja media identificación a ciegas, y no porque una prediga a
la otra sino porque NO la predice: pueden cambiar de veredicto en sentidos
opuestos en el mismo retardo.

Las pruebas fijan además la elección de método —sustituir por la media, no
borrar los pares— porque es una decisión de diseño que se validó contra un
modelo realmente calibrado y que se equivocaría de dirección si se cambiara.
"""
import numpy as np
import pytest

from art.calibracion import (calibra_correlograma, describe_calibracion,
                             Distorsion)


def _ar1_con_atipico(phi=0.6, n=200, at=100, golpe=-6.0, semilla=7):
    rng = np.random.default_rng(semilla)
    a = rng.standard_normal(n)
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = phi * x[t-1] + a[t]
    x[at] += golpe
    return x


# ───────────────── lo que la herramienta tiene que ver ─────────────────

def test_detecta_que_el_atipico_cambia_la_identificacion():
    cal = calibra_correlograma(_ar1_con_atipico(), umbral=2.5)
    assert cal.extremos, "el golpe de 6σ tiene que salir"
    assert cal.cambia_la_identificacion


def test_sin_atipicos_no_hay_nada_que_calibrar():
    rng = np.random.default_rng(3)
    cal = calibra_correlograma(rng.standard_normal(300) * 0.5, umbral=4.0)
    assert cal.extremos == []
    assert not cal.cambia_la_identificacion
    assert cal.veredicto == "sin extremos"


def test_calibra_las_DOS_funciones_no_solo_la_acf():
    """La razón de ser del rediseño: antes sólo se calibraba la ACF."""
    cal = calibra_correlograma(_ar1_con_atipico(), umbral=2.5)
    d = cal.distorsiones[0]
    for campo in ("acf_obs", "acf_cal", "pacf_obs", "pacf_cal"):
        assert isinstance(getattr(d, campo), float)
    assert any(x.pacf_obs != x.pacf_cal for x in cal.distorsiones)


def test_el_atipico_infla_sigma_y_la_calibracion_lo_corrige():
    cal = calibra_correlograma(_ar1_con_atipico(), umbral=2.5)
    assert cal.sigma_cal < cal.sigma_obs


# ───────────────── el método, que es una decisión de diseño ─────────────────

def test_calibrar_es_la_desviacion_a_CERO_sobre_lo_retenido():
    """El estimador, fijado — y la historia de por qué es éste (BUG-0142).

    Esta prueba fijaba antes la ELIMINACIÓN POR PARES, con este argumento:
    sustituir el residuo por la media equivale a un impulso con ω libre —la
    condición de primer orden—, y la herramienta que informa la elección de
    forma no puede suponer una para calcularse.

    El argumento cayó por donde no se miraba. Cada r(k) por pares retenidos se
    estima sobre un subconjunto DISTINTO, así que la secuencia no es una función
    de autocovarianza, la Toeplitz no es definida positiva y Durbin-Levinson
    diverge: sobre `RATIO_m10` la PACF calibrada llegó a **+3,394**. Y la
    disyuntiva no era la que parecía: cualquier estimador que quite la
    contribución de una observación a TODOS los retardos y siga siendo admisible
    tiene que poner su desviación a cero.

    Se fija reproduciendo el cálculo: μ̂ sobre lo retenido, desviación cero en lo
    omitido, y de ahí el estimador de Bartlett —el mismo de `fue.acf`—.
    """
    x = _ar1_con_atipico()
    cal = calibra_correlograma(x, umbral=2.5)
    n = len(x); mu0, sd0 = x.mean(), x.std(ddof=0)
    om = {i for i in range(n) if abs((x[i]-mu0)/sd0) > 2.5}
    keep = np.array([i for i in range(n) if i not in om])
    mu = x[keep].mean()
    z = np.array([0.0 if i in om else x[i] - mu for i in range(n)])
    esperado = float(z[1:] @ z[:-1]) / float(z @ z)
    assert cal.distorsiones[0].acf_cal == pytest.approx(esperado, abs=1e-12)


def test_sin_omitir_coincide_EXACTAMENTE_con_fue():
    """La propiedad que hace que el paquete tenga UN correlograma y no dos.

    La eliminación por pares daba r(1)=+0,5819 sobre ∇ln PGAS donde la diagnosis
    daba +0,5749, y la tabla de BUG-0048 llegó a publicar los dos números en la
    misma tabla —`ACF(1)` y `PACF(1)`— cuando son idénticos por definición.
    """
    import fue
    from art.calibracion import _acf_pacf
    x = _ar1_con_atipico()
    r, p = _acf_pacf(x, 20)
    assert np.max(np.abs(r - fue.acf(x, lags=20))) == pytest.approx(0.0, abs=1e-14)
    assert np.max(np.abs(p - fue.pacf(x, lags=20))) == pytest.approx(0.0, abs=1e-12)
    # y la identidad que antes NO se cumplía en la herramienta
    assert p[0] == pytest.approx(r[0], abs=1e-14)


def test_normalizar_con_la_sigma_CONTAMINADA_seria_otra_cosa():
    """Guarda contra la regresión que ya ocurrió una vez.

    La primera versión omitía los pares pero normalizaba con μ y σ
    contaminadas, y decía que la autocorrelación de retardo 1 BAJA al quitar el
    anómalo cuando en realidad sube.
    """
    x = _ar1_con_atipico()
    cal = calibra_correlograma(x, umbral=2.5)
    n = len(x); mu0, sd0 = x.mean(), x.std(ddof=0)
    om = {i for i in range(n) if abs((x[i]-mu0)/sd0) > 2.5}
    zz = x - mu0; c0 = float((zz@zz)/n)
    pr = zz[:-1]*zz[1:]
    ingenua = sum(pr[i] for i in range(len(pr))
                  if not (i in om or i+1 in om))/n/c0
    assert abs(cal.distorsiones[0].acf_cal - ingenua) > 1e-4


def test_la_direccion_del_efecto_depende_de_la_configuracion():
    """No hay una regla universal, y conviene que esté escrito.

    Un choque metido en la RECURSIÓN de un AR se propaga, así que dos valores
    consecutivos salen del mismo signo y su producto INFLA r(1): quitarlos la
    baja. Dos anómalos ADITIVOS consecutivos del mismo signo hacen lo contrario
    —es el caso de PGAS, donde r(1) subió de +0,575 a +0,670—. Por eso la
    herramienta reporta el movimiento y no una regla.
    """
    rng = np.random.default_rng(5)
    x = rng.standard_normal(300) * 0.5
    x[150] -= 4.0                       # aditivo, aislado
    c1 = calibra_correlograma(x, umbral=2.5)
    y = x.copy(); y[151] -= 4.0         # y ahora dos consecutivos del mismo signo
    c2 = calibra_correlograma(y, umbral=2.5)
    m1 = c1.distorsiones[0].acf_cal - c1.distorsiones[0].acf_obs
    m2 = c2.distorsiones[0].acf_cal - c2.distorsiones[0].acf_obs
    assert m2 < m1, ("dos consecutivos del mismo signo inflan r(1), así que "
                     "quitarlos la baja más que quitar uno aislado")


def test_avisa_si_la_pacf_omitida_no_es_valida():
    """Coste conocido de omitir: cada retardo usa pares distintos, así que la
    secuencia no está garantizada definida positiva. Cuando no lo es, |φ|≥1 y
    hay que decirlo en vez de publicar números que no significan nada."""
    cal = calibra_correlograma(_ar1_con_atipico(), umbral=2.5)
    assert cal.pacf_valida is True
    assert max(abs(d.pacf_cal) for d in cal.distorsiones) < 1.0


# ───────────────── los veredictos por retardo ─────────────────

def test_sale_y_entra_significan_lo_que_dicen():
    d = Distorsion(lag=2, banda=0.2, acf_obs=0.10, acf_cal=0.30,
                   pacf_obs=-0.30, pacf_cal=-0.10)
    assert d.acf_flip == "sale"      # dentro → fuera: estaba enmascarada
    assert d.pacf_flip == "entra"    # fuera → dentro: estaba fabricada


def test_un_retardo_que_no_cruza_no_es_un_flip():
    d = Distorsion(lag=3, banda=0.2, acf_obs=0.05, acf_cal=0.15,
                   pacf_obs=0.30, pacf_cal=0.40)
    assert d.acf_flip is None and d.pacf_flip is None


def test_los_flips_opuestos_se_señalan_aparte():
    """Que las dos cambien en sentidos contrarios es la prueba de que una no
    sustituye a la otra, y por eso tiene campo propio."""
    d = Distorsion(lag=2, banda=0.2, acf_obs=0.10, acf_cal=0.30,
                   pacf_obs=-0.30, pacf_cal=-0.10)
    from art.calibracion import CalibracionCorrelograma
    c = CalibracionCorrelograma(distorsiones=[d], extremos=[(5, -3.0)], n=100,
                                banda=0.2, umbral=2.5, sigma_obs=1.0,
                                sigma_cal=0.9)
    assert c.flips_opuestos == [d]
    assert c.flips_ar == [d] and c.flips_ma == [d]


# ───────────────── contra la sobre-intervención ─────────────────

def test_dice_que_NO_intervengas_cuando_el_atipico_no_decide_ordenes():
    """El otro sentido de la herramienta, y el que evita sobre-intervenir."""
    rng = np.random.default_rng(11)
    x = rng.standard_normal(400)
    x[200] += 5.0                       # un atípico en ruido blanco puro
    cal = calibra_correlograma(x, umbral=2.5)
    assert cal.extremos
    d = describe_calibracion(cal)
    if not cal.cambia_la_identificacion:
        assert "sobre-intervenir" in d.recommendation
        assert "no cambia la identificación" in d.summary


# ───────────────── presentación ─────────────────

def test_el_texto_nombra_QUE_orden_afecta_cada_flip():
    cal = calibra_correlograma(_ar1_con_atipico(), umbral=2.5)
    d = describe_calibracion(cal, "prueba")
    if cal.flips_ar:
        assert "orden AR" in d.summary
    if cal.flips_ma:
        assert "orden MA" in d.summary
    assert d.figure_b64 and len(d.figure_b64) > 1000


def test_los_numeros_llegan_en_data():
    """Claude tiene que tener las distorsiones a mano sin leer la figura."""
    cal = calibra_correlograma(_ar1_con_atipico(), umbral=2.5)
    dd = describe_calibracion(cal).data
    assert dd["cambia_la_identificacion"] in (True, False)
    assert isinstance(dd["flips_ar"], list) and isinstance(dd["flips_ma"], list)
    d0 = dd["distorsiones"][0]
    for k in ("lag", "acf_obs", "acf_cal", "pacf_obs", "pacf_cal",
              "acf_flip", "pacf_flip"):
        assert k in d0


# ───────────────── guardas ─────────────────

def test_serie_demasiado_corta():
    with pytest.raises(ValueError, match="al menos 8"):
        calibra_correlograma([1.0, 2.0, 3.0])


def test_varianza_nula():
    with pytest.raises(ValueError, match="desviación típica nula"):
        calibra_correlograma([2.0] * 40)


def test_la_linea_latente_ya_no_afirma_lo_que_no_comprueba():
    """P2: decía «no distorsionan la ACF/PACF» con distorsión moderada,
    mientras el escaneo completo decía «puede merecer la pena intervenir»."""
    import inspect
    import art.mcp_server as srv
    cuerpo = __import__("_fuente").fuente_de(srv._auto_scan_section)
    # la frase sólo puede quedar en el comentario que explica el arreglo
    codigo = "\n".join(l for l in cuerpo.splitlines()
                       if not l.lstrip().startswith("#"))
    assert "no distorsionan" not in codigo, \
        "la línea latente no puede AFIRMAR que no distorsionan: lo calibra"
    assert "cambia_la_identificacion" in codigo
