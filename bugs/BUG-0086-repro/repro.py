"""BUG-0086 — la escalera de Ockham arbitra entre step (1a) e impulse (1b) por AIC.

`escalera_de_ockham` documenta que las dos lecturas escalares —1a escalón
permanente, 1b impulso transitorio— tienen «el MISMO coste —un parámetro cada
una— y no anidadas entre sí» (escalera.py) y que «el AIC no arbitra la subida de
escalón». Pero la selección del peldaño simple era literalmente:

    mejor_simple = min(simples, key=lambda p: p.aic)

Para un pico ÚNICO en la serie diferenciada —que ES un escalón permanente de
nivel— el impulso ajustó marginalmente mejor (AIC -2002.75 vs -2002.01) y la
escalera recomendó «impulse»: la forma equivocada.

Sintético y determinista, sin datos ni motor: llama a `lectura_escalar`, que es
la función que ahora decide, y comprueba las cuatro firmas del diccionario de la
FLT. La versión anterior de este repro copiaba la línea del defecto dentro de sí
misma, así que no podía validar el arreglo; ésta ejerce el código real.
"""
import sys

sys.path.insert(0, "src")

from art.episodes import Episodio
from art.escalera import TOL_CANCELA, lectura_escalar

FALLOS = []


def ep(*extremos, d=1):
    ext = list(extremos)
    return Episodio(inicio=ext[0][0], fin=ext[-1][0], extremos=ext, d=d)


def caso(titulo, episodio, d, esperado):
    nivel, razon = lectura_escalar(episodio, d)
    ok = nivel == esperado
    print(f"  {titulo}")
    print(f"     extremos={[(o, round(z, 2)) for o, z in episodio.extremos]} d={d}")
    print(f"     -> {nivel}  (esperado {esperado})  {'OK' if ok else 'FALLA'}")
    print(f"     {razon}")
    if not ok:
        FALLOS.append(titulo)


print("== El diccionario de la FLT, que es lo que debe decidir")
print("     en el NIVEL          en ∇                    suma en ∇")
print("     escalón ω en T   ->  UN impulso ω en T       ω")
print("     impulso ω en T   ->  DOS impulsos +ω, -ω     0")
print()

print("== A. Con d>=1 los residuos viven en ∇")
caso("pico único (el caso de FOOD_UEM 12/2004)",
     ep((35, 3.56)), 1, "1a")
caso("par que CANCELA: la firma de un impulso de nivel",
     ep((35, 3.50), (36, -3.40)), 1, "1b")
caso("par de signo opuesto que NO cancela: cola, no impulso",
     ep((35, 3.56), (36, -2.20)), 1, "1a")
caso("dos extremos del mismo signo",
     ep((35, 3.50), (36, 2.90)), 1, "1a")

print("\n== B. Con d=0 los residuos viven en el nivel y el diccionario se invierte")
caso("un solo extremo en el nivel = impulso",
     ep((35, 3.50), d=0), 0, "1b")
caso("racha del mismo signo en el nivel = escalón",
     ep((35, 3.50), (36, 3.10), d=0), 0, "1a")

print("\n== C. El AIC no entra en la decisión")
import ast
import inspect
# El AIC se MENCIONA en el docstring —dice justamente que no arbitra—, así que
# se mira el cuerpo sin él: lo que importa es que no lo LEA.
_fn = ast.parse(inspect.getsource(lectura_escalar)).body[0]
_cuerpo = _fn.body[1:] if (isinstance(_fn.body[0], ast.Expr)
                           and isinstance(_fn.body[0].value, ast.Constant)) \
    else _fn.body
src = "\n".join(ast.unparse(n) for n in _cuerpo)
if "aic" in src.lower():
    print("  FALLA: `lectura_escalar` menciona el AIC")
    FALLOS.append("lectura_escalar mira el AIC")
else:
    print("  `lectura_escalar` no menciona el AIC en ninguna parte: OK")

from art.escalera import escalera_de_ockham
src2 = inspect.getsource(escalera_de_ockham)
if "min(simples" in src2:
    print("  FALLA: la selección del peldaño simple sigue siendo min(..., aic)")
    FALLOS.append("min(simples, key=aic) sigue ahi")
else:
    print("  la selección del peldaño simple ya no es min(simples, key=aic): OK")

print(f"\n  (tolerancia de cancelación declarada: {TOL_CANCELA:.0%} del pico)")

print("\n" + "=" * 70)
if FALLOS:
    print("FALLA:", ", ".join(FALLOS))
    sys.exit(1)
print("OK: la lectura escalar sale de la firma del residuo, no del ajuste.")
