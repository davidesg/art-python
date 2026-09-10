"""El helper de `tests/_texto.py`, y el modo de fallo que existe para evitar."""
from tests._texto import dice, dice_todas, normaliza


def test_una_frase_partida_por_el_ajuste_de_linea_SIGUE_estando():
    doc = ("Pásalos tal como salen del `.out`.\n"
           "    **No hace falta\n    que hagas la resta**: la respuesta trae\n"
           "    el CAMINO DEL NIVEL.")
    assert "No hace falta que hagas la resta" not in doc      # el modo de fallo
    assert dice(doc, "No hace falta que hagas la resta")      # y su remedio


def test_lo_que_NO_dice_sigue_sin_decirlo():
    doc = "El analista decide en cada paso."
    assert not dice(doc, "el modelo decide en cada paso")
    assert not dice(doc, "decide el analista")   # otro orden es otra frase


def test_dice_todas_devuelve_las_que_faltan():
    doc = "uno dos tres"
    assert dice_todas(doc, "uno dos", "tres") == []
    assert dice_todas(doc, "uno dos", "cuatro") == ["cuatro"]


def test_normaliza_no_junta_palabras():
    assert normaliza("a\n   b") == "a b"
    assert normaliza("  a  b  ") == "a b"
