"""Leer el código de una función SIN depender de los números de línea.

`inspect.getsource` congela `co_firstlineno` en el import y lee el fichero en el
momento de llamar. Si el fichero cambió entretanto —editar mientras la suite
corre— devuelve el trozo equivocado, y una prueba que busca una frase ahí falla
señalando a otra función.

No es hipotético: pasó **cinco veces** en una sola sesión sobre
`mcp_server.py`, y cada falso positivo cuesta ir a mirar un fallo que no existe.
Es la misma familia que BUG-0082 —ruido indistinguible de una señal real— y se
paga igual.

Aquí se localiza la función **por nombre**, parseando el fichero en el momento.
Inmune a los desplazamientos.

Dicho esto: una prueba sobre el código fuente es siempre el último recurso.
Comprueba la implementación, no el comportamiento, así que sólo vale cuando lo
que se quiere fijar ES una decisión de implementación —«la regla vive en
`policy`», «esta rama consulta al árbitro»— y no hay forma de observarla desde
fuera. Si se puede escribir como comportamiento, se escribe como comportamiento.
"""
from __future__ import annotations

import ast
import inspect
import textwrap


def fuente_de(obj, nombre: str | None = None) -> str:
    """El código de `obj`, localizado por nombre en su fichero.

    `obj` puede ser una función, o una herramienta MCP decorada (se desenvuelve
    por `.fn`). `nombre` sólo hace falta si el envoltorio cambia el `__name__`.
    """
    fn = getattr(obj, "fn", obj)
    fn = inspect.unwrap(fn)
    nombre = nombre or getattr(fn, "__name__", None)
    if nombre is None:
        raise ValueError("no hay nombre con el que buscar")
    ruta = inspect.getsourcefile(fn)
    if ruta is None:
        raise ValueError(f"{nombre}: sin fichero de origen")
    with open(ruta, encoding="utf-8") as fh:
        arbol = ast.parse(fh.read(), filename=ruta)
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and nodo.name == nombre:
            with open(ruta, encoding="utf-8") as fh:
                lineas = fh.readlines()
            return textwrap.dedent(
                "".join(lineas[nodo.lineno - 1:nodo.end_lineno]))
    raise LookupError(f"no se encontró `def {nombre}` en {ruta}")


def cuerpo_de(obj, nombre: str | None = None) -> str:
    """Como `fuente_de`, pero SIN el docstring.

    Para cuando lo que importa es qué HACE la función y no qué dice de sí misma
    — por ejemplo comprobar que no mira el AIC cuando su docstring habla
    justamente de no mirarlo (BUG-0086).
    """
    src = fuente_de(obj, nombre)
    fn = ast.parse(src).body[0]
    cuerpo = fn.body
    if cuerpo and isinstance(cuerpo[0], ast.Expr) \
            and isinstance(cuerpo[0].value, ast.Constant) \
            and isinstance(cuerpo[0].value.value, str):
        cuerpo = cuerpo[1:]
    return "\n".join(ast.unparse(n) for n in cuerpo)
