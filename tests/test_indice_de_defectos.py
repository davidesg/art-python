"""El índice de defectos tiene que estar en verde, y hay que comprobarlo.

BUG-0117. `art-bug check` llevaba tiempo en rojo —7 errores en 6 informes— y
nadie se enteraba, porque **ninguna prueba lo miraba**. `fue` sí tiene la suya
(`test_all_reports_valid`), y por eso allí el índice estaba limpio.

Un validador que lleva meses en rojo deja de ser un validador: si está en CI, ya
fallaba, y un rojo permanente vale lo mismo que un verde que nadie mira.
"""
import os

import pytest

from art import bugs

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA = os.path.join(RAIZ, "bugs")


def _informes():
    for f in sorted(os.listdir(CARPETA)):
        if f.startswith("BUG-") and f.endswith(".md"):
            yield f, bugs.load_bug(os.path.join(CARPETA, f))


def test_todos_los_informes_son_validos():
    errores = [f"{b.id}: {e}" for _, b in _informes() for e in b.problems()]
    assert not errores, "informes inválidos:\n  " + "\n  ".join(errores)


def test_ningun_identificador_repetido():
    """Hubo dos BUG-0102 el mismo día y sus carpetas de repro se pisaron,
    perdiendo una (ver BUG-0109)."""
    import collections
    c = collections.Counter(b.id for _, b in _informes())
    repes = {k: v for k, v in c.items() if v > 1}
    assert not repes, f"identificadores repetidos: {repes}"


def test_un_informe_fixed_dice_DONDE_se_arreglo():
    """`fixed_in` vacío con `status: fixed` es un informe que no se puede
    releer: no hay forma de saber si un veredicto viene de una versión con el
    defecto o sin él.

    Cuatro lo tenían vacío, y el 0088 lo tenía escrito Y ANULADO por una línea
    vacía debajo —el YAML se queda con la última—, así que el dato correcto
    estaba ahí, tapado."""
    malos = [b.id for _, b in _informes()
             if b.status == "fixed" and not (b.fixed_in or "").strip()]
    assert not malos, f"`fixed` sin `fixed_in`: {malos}"


def test_ninguna_clave_del_encabezado_esta_duplicada():
    """Lo que le pasaba al 0088: el dato bueno anulado por una repetición
    vacía. `problems()` no lo ve, porque para cuando mira ya sólo queda una."""
    import re
    malos = []
    for f, _ in _informes():
        texto = open(os.path.join(CARPETA, f), encoding="utf-8").read()
        partes = texto.split("---")
        if len(partes) < 3:
            continue
        claves = re.findall(r"(?m)^([a-z_]+):", partes[1])
        import collections
        repes = [k for k, v in collections.Counter(claves).items() if v > 1]
        if repes:
            malos.append(f"{f}: {repes}")
    assert not malos, "claves repetidas en el encabezado:\n  " + "\n  ".join(malos)


def test_los_campos_de_vocabulario_no_llevan_prosa():
    """Los dos casos de 0011 y 0020 no eran descuidos: eran matices REALES que
    el vocabulario no admite —«partially fixed, quedan dos elementos»,
    «cerrado, no era un defecto»—. Quien los escribió tenía algo que decir y no
    tenía dónde.

    La solución no fue recortarlos —eso pierde información— sino moverlos al
    cuerpo y dejar en el campo el término del vocabulario. Esto vigila que no
    vuelvan a escribirse al lado."""
    malos = []
    for _, b in _informes():
        if b.status not in bugs.STATUSES:
            malos.append(f"{b.id}: status {b.status!r}")
        if b.severity not in bugs.SEVERITIES:
            malos.append(f"{b.id}: severity {b.severity!r}")
    assert not malos, "\n  ".join(malos)


def test_cada_carpeta_de_repro_tiene_su_informe():
    ids = {b.id for _, b in _informes()}
    huerfanas = [d for d in os.listdir(CARPETA)
                 if d.endswith("-repro") and d[:8] not in ids]
    assert not huerfanas, f"repros sin informe: {huerfanas}"
