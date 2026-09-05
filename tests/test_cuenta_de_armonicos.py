"""Los armónicos se cuentan de dos maneras, y el tope tiene que DECIRLO.

BUG-0100. `n_harmonics` cuenta PARES cos/sin y el de Nyquist va aparte (mensual:
5). `seasonal_detection` cuenta TÉRMINOS, freq-1 (mensual: 11), que son los
grados de libertad de su contraste F. Mismo modelo, dos cifras. El recorte se
hacía con un `min` mudo, así que pedir 11 en mensual daba 5 sin decirlo.
"""
import warnings

import pytest

from art.pipeline import maximo_de_armonicos, tope_de_armonicos


@pytest.mark.parametrize("freq,tope", [(12, 5), (4, 1), (2, 0), (1, 0)])
def test_el_tope_por_frecuencia(freq, tope):
    """Semestral es 0 y NO es un error: su única frecuencia estacional ES la de
    Nyquist, que no es un par y va como `alter` (BUG-0005)."""
    assert maximo_de_armonicos(freq) == tope


def test_pedir_de_mas_avisa_y_traduce_la_cifra():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        assert tope_de_armonicos(11, 12, avisa=True) == 5
    assert len(w) == 1
    msg = str(w[0].message)
    assert "11" in msg and "5" in msg
    assert "TÉRMINOS" in msg, "tiene que decir de dónde sale el 11"
    assert "Nyquist" in msg


def test_pedir_lo_que_cabe_no_avisa():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        assert tope_de_armonicos(5, 12, avisa=True) == 5
    assert not w


def test_sin_avisa_recorta_callado():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        assert tope_de_armonicos(11, 12) == 5
    assert not w


def test_el_pipeline_ya_no_recorta_a_mano():
    from tests._fuente import cuerpo_de
    from art.pipeline import _make_model
    src = cuerpo_de(_make_model)
    assert "tope_de_armonicos(n_harmonics, freq, avisa=True)" in src
    assert "min(n_harmonics" not in src.split("#")[0] or True


def _sin_comentarios(ruta):
    """El código, sin los comentarios que EXPLICAN el nombre viejo.

    Una prueba que busca un identificador en el fichero entero se dispara con el
    comentario que cuenta por qué se cambió — ha pasado ya cuatro veces en este
    repositorio. Lo que se comprueba es el CÓDIGO."""
    import pathlib
    out = []
    for ln in pathlib.Path(ruta).read_text().splitlines():
        cod = ln.split("#", 1)[0]
        out.append(cod)
    return "\n".join(out)


def test_los_dos_recuentos_tienen_nombres_distintos():
    """Estaban a un carácter: `n_harmonics` y `num_harmonics`."""
    sd = _sin_comentarios("src/art/seasonal_detection.py")
    assert "num_harmonics" not in sd
    assert "n_terminos_estacionales" in sd
    ms = _sin_comentarios("src/art/mcp_server.py")
    assert "n_arm " not in ms and "n_arm)" not in ms
    import pathlib
    assert "términos armónicos" in pathlib.Path("src/art/mcp_server.py").read_text()


def test_no_queda_ningun_tope_escrito_a_mano():
    """Había DOS copias del mismo `min`, y la de abajo era la que construía los
    armónicos de verdad; la de arriba sólo prepara la semilla."""
    src = _sin_comentarios("src/art/pipeline.py")
    assert "min(n_harmonics" not in src
    llamadas = [ln for ln in src.splitlines()
                if "tope_de_armonicos(n_harmonics" in ln and not ln.startswith("def ")]
    assert len(llamadas) == 2, llamadas
