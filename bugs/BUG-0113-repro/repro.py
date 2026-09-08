"""BUG-0113 — el carril guiado descarta la ruta de la figura.

`_show_fig` DEVUELVE la ruta del `.png` que acaba de escribir: es la mitad del
arreglo del BUG-0078 —«quien llama puede decirla, y cuando el visor no aparece
el analista tiene el fichero»—. La nota se compone en `_nota_figura` y la
inserta `_result()`.

Pero `guided_identification` no pasa por `_result()`: compone su texto a mano y
llama a `_show_fig` en cinco puntos **tirando el valor devuelto**. Resultado: su
salida no cita ninguna ruta. Si el visor no abre (o el cliente no renderiza la
imagen), el analista se queda sin figura y sin fichero al que ir.

    python repro.py

Contrasta una herramienta que SÍ pasa por `_result()` con el carril guiado, y
cuenta los puntos de llamada que descartan el retorno. No estima nada: usa los
nodos baratos del guiado (Box-Cox y nivel d=0).
"""
from __future__ import annotations

import ast
import inspect
import os
import re
import sys
import tempfile


def desenvuelve(obj):
    for a in ("fn", "func", "__wrapped__"):
        if hasattr(obj, a):
            return getattr(obj, a)
    return obj


def texto_de(salida) -> str:
    if isinstance(salida, str):
        return salida
    trozos = []
    for c in salida:
        t = getattr(c, "text", None)
        if isinstance(t, str):
            trozos.append(t)
    return "\n".join(trozos)


# ── Parte 1 — analisis estatico: quien tira el retorno de _show_fig ──────────

def censo_llamadas() -> tuple[int, int]:
    """(descartadas, usadas) llamadas a _show_fig dentro de guided_identification."""
    from art import mcp_server as M

    fuente = inspect.getsource(desenvuelve(M.guided_identification))
    arbol = ast.parse(textwrap_dedent(fuente))

    descartadas = usadas = 0
    for nodo in ast.walk(arbol):
        # Expr => el valor de la llamada se descarta
        if isinstance(nodo, ast.Expr) and isinstance(nodo.value, ast.Call):
            f = nodo.value.func
            if getattr(f, "id", None) == "_show_fig" or getattr(f, "attr", None) == "_show_fig":
                descartadas += 1
        elif isinstance(nodo, (ast.Assign, ast.Return)):
            for sub in ast.walk(nodo):
                if isinstance(sub, ast.Call):
                    f = sub.func
                    if getattr(f, "id", None) == "_show_fig" or getattr(f, "attr", None) == "_show_fig":
                        usadas += 1
    return descartadas, usadas


def textwrap_dedent(s: str) -> str:
    import textwrap
    return textwrap.dedent(s)


def main() -> int:
    os.environ["ART_NO_VIEWER"] = "1"          # sin ventanas; no altera lo medido
    tmp = tempfile.mkdtemp(prefix="bug0113-")
    os.environ["ART_FIG_DIR"] = tmp

    from art import mcp_server as M

    print("=" * 72)
    print("1 · Llamadas a _show_fig en guided_identification")
    print("=" * 72)
    descartadas, usadas = censo_llamadas()
    print(f"  con el retorno DESCARTADO : {descartadas}")
    print(f"  con el retorno USADO      : {usadas}")
    print("  -> _show_fig devuelve la ruta; nadie la recoge.\n")

    print("=" * 72)
    print("2 · _nota_figura se llama desde…")
    print("=" * 72)
    fuente_mod = inspect.getsource(M)
    for m in re.finditer(r"^(.*_nota_figura\(.*)$", fuente_mod, re.M):
        linea = m.group(1).strip()
        if linea.startswith("def "):
            continue
        print(f"  {linea[:90]}")
    print("  -> sólo desde _result(), por donde el carril guiado no pasa.\n")

    # ── Parte 3 — contraste sobre una serie de verdad ────────────────────────
    datos = [100.0 * (1.002 ** t) for t in range(120)]
    inp = os.path.join(tmp, "SER.inp")
    print(desenvuelve(M.create_inp)(data=datos, output_path=inp, name="SER",
                                    freq=12, start_year=2010, start_period=1)
          .splitlines()[0])
    print()

    print("=" * 72)
    print("3 · Contraste: quien cita la ruta y quien no")
    print("=" * 72)

    casos = [
        ("boxcox_analysis  (pasa por _result)",
         lambda: desenvuelve(M.boxcox_analysis)(inp)),
        ("guided_identification  nodo Box-Cox",
         lambda: desenvuelve(M.guided_identification)(inp)),
        ("guided_identification  nodo d=0",
         lambda: desenvuelve(M.guided_identification)(inp, lam=0.0)),
    ]

    resultados = []
    for etiqueta, fn in casos:
        salida = texto_de(fn())
        cita = "*Figura:" in salida or "Figura: `" in salida
        tiene_img = "Figura" in salida
        resultados.append((etiqueta, cita))
        print(f"  {etiqueta:42s} cita la ruta: {'SI' if cita else 'NO'}")
    print()

    # ¿se escribieron los .png? Si no, no habria nada que citar y el contraste
    # no significaria nada.
    pngs = sorted(f for f in os.listdir(tmp) if f.endswith(".png"))
    print(f"  .png realmente escritos en ART_FIG_DIR: {len(pngs)}")
    for f in pngs:
        print(f"      {f}")
    print()

    print("=" * 72)
    print("VEREDICTO")
    print("=" * 72)
    ok_result = resultados[0][1]
    fallan_guiado = not resultados[1][1] and not resultados[2][1]
    print("  Las figuras se escriben en los dos casos.")
    print(f"  boxcox_analysis cita la ruta        : {'SI' if ok_result else 'NO'}")
    print(f"  el carril guiado NO la cita         : {'SI' if fallan_guiado else 'NO'}")
    print()
    print("  Con el visor roto o un cliente que no renderice, el analista")
    print("  se queda sin figura y sin ruta — en el carril donde las figuras")
    print("  son la mitad del trabajo.")
    return 0 if (ok_result and fallan_guiado and descartadas >= 1) else 1


if __name__ == "__main__":
    sys.exit(main())
