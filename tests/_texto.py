"""Comparar texto de docstrings sin que el FORMATO decida el resultado.

Muchas pruebas de esta suite afirman «esto tiene que estar dicho» buscando una
subcadena en un docstring. Es la forma correcta de guardar una regla que vive
en el texto —no hay compilador que avise de que se ha ido—, y tiene un modo de
fallo propio que apareció tres veces al acortar las descripciones en ORDEN 1.2:

    **No hace falta que hagas la resta**      la frase está entera en la página
    **No hace falta                           …y partida por el ajuste de línea
    que hagas la resta**                      así que como subcadena NO existe

La prueba falla, el texto está bien, y quien lo arregla mueve palabras hasta
que pasa. Eso convierte una prueba de CONTENIDO en una de maquetación.

`dice(doc, frase)` compara colapsando los espacios, así que un salto de línea
en medio de la frase deja de importar. Lo que sigue importando —que la frase
esté, con esas palabras y en ese orden— es exactamente lo que se quería guardar.
"""
import re


def normaliza(t: str) -> str:
    """Colapsa todo blanco —saltos incluidos— en un solo espacio."""
    return re.sub(r"\s+", " ", t or "").strip()


def dice(doc: str, frase: str) -> bool:
    """¿Dice `doc` la frase, sin que el ajuste de línea decida?"""
    return normaliza(frase) in normaliza(doc)


def dice_todas(doc: str, *frases: str) -> list[str]:
    """Las que NO dice. Vacío = las dice todas."""
    return [f for f in frases if not dice(doc, f)]
