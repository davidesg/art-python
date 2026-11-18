#!/usr/bin/env python3
"""BUG-0207 · El guion del carril guiado no se escribe solo.

Recorrido guiado del IPC nacional de España (INE, 2002:01-2019:12), tal como se
hizo en la P04 de Econometría Aplicada (6-oct-2026), llamando a las herramientas
MCP de art como funciones. Cada ASSERT comprueba un defecto: pasa mientras el
defecto exista. Corre en un directorio temporal; no toca nada fuera.

    python3 repro.py
"""
import json, os, shutil, sys, tempfile
import art.mcp_server as s

HERE = os.path.dirname(os.path.abspath(__file__))
W = tempfile.mkdtemp(prefix="bug0207_")
PRESENTES = []  # los defectos D1..D7 que siguen presentes
G = os.path.join(W, "guion.json")
shutil.copy(os.path.join(HERE, "ES_CPI_2002_2019.csv"), W)
inp = os.path.join(W, "ES_CPI.inp")
s.load_data(os.path.join(W, "ES_CPI_2002_2019.csv"), inp, "ES_CPI")

def entries():
    return json.load(open(G))["entries"] if os.path.exists(G) else []

# ── D1. La identificación guiada no escribe ningún nodo ──────────────────────
# El arreglo (Resolution 2026-10-06) le da `guion_path`: cada llamada deja su
# nodo. Antes este repro llamaba sin él y comprobaba el defecto, no el arreglo.
for kw in (dict(), dict(lam=0), dict(lam=0, d=1), dict(lam=0, d=1, D=1)):
    s.guided_identification(inp, domain="price_index", guion_path=G,
                            expectativas="inercia: AR con φ>0", **kw)
if not any(e.get("kind") == "node" for e in entries()):
    PRESENTES.append("D1")
    print("D1 ✗  guided_identification (λ, d, D, órdenes) no deja nada en el guion: no admite guion_path")
else:
    print("D1 ✓  resuelto")

# ── D2. 'dominio' es obligatorio como criterio, pero nada lo pide ─────────────
r = s.guion_node(G, "lambda", "0", razon="índice de precios", criterio="dominio")
txt = r if isinstance(r, str) else str(r)
if "dominio" in txt and ("no tiene" in txt or "Error" in txt):
    PRESENTES.append("D2")
    print("D2 ✗  criterio='dominio' exige un nodo 'dominio' previo, y el flujo guiado nunca lo pide ni lo crea")
else:
    print("D2 ✓  resuelto")
s.guion_node(G, "dominio", "price_index", razon="IPC", expectativas="inercia: AR con φ>0")
s.guion_node(G, "lambda", "0", razon="índice de precios", criterio="dominio")

# ── D3. Veredicto por Q(39): m01 sale APROBADO con r1≈0,38 y Q(12) p≈0,0003 ──
m01 = os.path.join(W, "m01.inp")
s.confirm_and_estimate(inp, m01, lam=0, d=1, D=1, p=0, q=0, P=0, Q=1,
                       domain="price_index", guion_path=G, guion_name="m01")
e = entries()[-1]; st = e["stats"]
q12 = dict(zip(st["q_lags"], st["q_pvalues"]))[12]
# El arreglo: un tercer estado, «pasa con salvedad», derivado de los p-valores
# (q_pass sigue siendo el cancerbero 3s+3, por decisión del 11-09-2026).
from art.guion import load_guion, q_estado
_ult = load_guion(G).entries[-1]
if st["q_pass"] and q12 < 0.01 and q_estado(_ult.stats) != "salvedad":
    PRESENTES.append("D3")
    print(f"D3 ✗  m01: q_pass=True (lo decide Q(39)) con Q(12) p={q12:.4f}; el mapa lo pinta Q✓")
else:
    print("D3 ✓  resuelto")

# ── D4. Lo que encuentra la diagnosis no llega a la versión ──────────────────
if not e.get("problems_found"):
    PRESENTES.append("D4")
    print("D4 ✗  problems_found de m01 queda vacío; y no hay herramienta para anotarlo después")
else:
    print("D4 ✓  resuelto")

# ── D5. Dos alternativas seguidas: la segunda cuelga de la primera ───────────
m02 = os.path.join(W, "m02.inp"); m03 = os.path.join(W, "m03.inp"); m04 = os.path.join(W, "m04.inp")
s.confirm_and_estimate(inp, m02, lam=0, d=1, D=1, p=1, q=0, P=0, Q=1, domain="price_index",
                       guion_path=G, guion_name="m02")
v02 = entries()[-1]["version"]
s.confirm_and_estimate(inp, m03, lam=0, d=1, D=1, p=1, q=1, P=0, Q=1, domain="price_index",
                       guion_path=G, guion_name="m03 = m02 + MA(1)")
v03 = entries()[-1]["version"]
s.confirm_and_estimate(inp, m04, lam=0, d=1, D=1, p=1, q=0, P=1, Q=1, domain="price_index",
                       guion_path=G, guion_name="m04 = m02 + AR(1)12",
                       parent=v02)        # el arreglo: el padre se declara
e04 = entries()[-1]
if e04["parent"] == v03:
    PRESENTES.append("D5")
    print(f"D5 ✗  m04 (sale de m02, v{v02}) queda con parent=v{v03} (m03); en modo nuevo no se puede declarar el padre")
else:
    print("D5 ✓  resuelto")

# ── D6. No se puede adoptar ──────────────────────────────────────────────────
s.record_version(m02.replace(".inp", ".pre"), G, name="m02 ADOPTADO", decision="adoptado",
                 base_pre_path=m02.replace(".inp", ".pre"))
ad = entries()[-1]
n_m02 = sum(1 for x in entries() if x.get("inp_path", "").endswith("m02.pre") or x.get("name", "").startswith("m02"))
if ad["status"] != "adopted" and n_m02 >= 2:
    PRESENTES.append("D6")
    print(f"D6 ✗  'adoptar' = una entrada nueva duplicada (status={ad['status']!r}); nunca sale ✓ en el mapa")
else:
    print("D6 ✓  resuelto")

# ── D7. Aviso espurio de instrumento sobre los nodos ─────────────────────────
mp = s.guion_map(G)
mp = mp if isinstance(mp, str) else str(mp)
if "mismo instrumento" in mp:
    PRESENTES.append("D7")
    print("D7 ✗  guion_map: «No todo se calculó con el mismo instrumento» por los NODOS, que no se calculan")
else:
    print("D7 ✓  resuelto")
print("\nguion en", G)

# Antes cada defecto era un `assert` que fallaba al ARREGLARSE («Dx resuelto»),
# así que el repro salía 1 justo con el bug cerrado. Ahora sale 1 mientras
# quede alguno presente, y 0 cuando están todos resueltos.
print("\npresentes:", ", ".join(PRESENTES) or "ninguno")
sys.exit(1 if PRESENTES else 0)
