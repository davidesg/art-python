"""BUG-0079 — la FLT que el diagnóstico identifica no se puede construir.

Determinista, sin estimar y sin datos externos: sólo firmas y round-trip del
.inp. Demuestra los tres eslabones de la cadena y dónde está cortada.

  A. NINGUNA herramienta MCP que cree o modifique una intervención admite el
     ORDEN del numerador. `suggest_intervention_form` sólo acepta
     form ∈ {pulse, step, ramp, auto}; `confirm_and_estimate` no tiene ningún
     parámetro de intervención.
  B. El motor SÍ lo soporta: `_build_model` acepta la tupla
     (at, form, n_omega), `_write_inp` escribe el orden y los coeficientes, y
     `fue.inp.load` lo relee. El eslabón de abajo está entero.
  C. Consecuencia: `test_interventions` sólo dispara el Wald de GANANCIA NULA
     para una intervención con más de un ω libre. Como el carril guiado no
     puede construir ninguna, ese contraste —el que separa transitorio de
     permanente, añadido por BUG-0071/0072— es inalcanzable desde el carril
     guiado.
"""
import inspect
import sys
import tempfile
import os

sys.path.insert(0, "src")

import numpy as np
from art import pipeline, mcp_server
import fue

FALLOS = []

# ── A. La superficie MCP no expone el orden del numerador ────────────────────
#
# El criterio se acotó al cerrar el bug, y la acotación es sustantiva: de las
# tres herramientas que tocan intervenciones, sólo UNA las crea a partir de
# argumentos de la superficie. `confirm_and_estimate` no tiene ningún parámetro
# de intervención —las HEREDA del `.pre` base—, y `build_model` tampoco: las
# decide dentro, por `policy.decide_interventions`, que ya devuelve
# (at, form, n_omega). La puerta que faltaba era `suggest_intervention_form`.
print("== A. Herramientas MCP que crean o modifican intervenciones")
CLAVES = ("n_omega", "omega", "orden", "order", "s")
ARG_ITV = ("date", "at", "form")          # crea la intervención desde la superficie

for nombre in ("suggest_intervention_form", "confirm_and_estimate", "build_model"):
    fn = getattr(mcp_server, nombre, None)
    fn = getattr(fn, "fn", fn)          # desenvuelve el decorador FastMCP si lo hay
    params = list(inspect.signature(fn).parameters)
    expone = [p for p in params if p in CLAVES]
    crea = [p for p in params if p in ARG_ITV]
    print(f"  {nombre:28} crea itv desde argumentos: {crea or 'NO'}"
          f"   expone orden de omega: {expone or 'NO'}")
    if crea and not expone:
        FALLOS.append(nombre)
    if not crea:
        print(f"     -> no la crea: la hereda (.pre) o la decide dentro (policy);"
              f" no le corresponde el orden")

fn = getattr(mcp_server, "suggest_intervention_form")
fn = getattr(fn, "fn", fn)
doc = inspect.getdoc(fn) or ""
formas = [f for f in ("pulse", "step", "ramp", "auto") if f in doc]
print(f"  formas admitidas por suggest_intervention_form: {formas}")
print("  -> el ORDEN es ortogonal a la forma: `n_omega` multiplica cualquiera")
print("     de ellas, y n_omega=0 conserva el comportamiento anterior.\n")

# ── B. El motor sí lo soporta ────────────────────────────────────────────────
print("== B. _build_model / _write_inp / fue.inp.load  (el eslabón de abajo)")
src = inspect.getsource(pipeline._make_model)
acepta = "n_omega" in src
print(f"  _make_model menciona n_omega: {acepta}")
if not acepta:
    FALLOS.append("_make_model")

rng = np.random.default_rng(7)
y = 100 + np.cumsum(rng.standard_normal(120) * 0.3)
ts = fue.TimeSeries(data=y.tolist(), freq=12, start=(2000, 1), name="SINT")

# un step en la obs 60 con numerador de orden 1  ->  (w0 - w1 B) S_t
m = pipeline._make_model(ts, lam=0.0, d=1, D=0, p=0, q=0,
                          n_harmonics=0, seasonal=False,
                          extra_itvs=[(59, "step", 2)])
itv = [i for i in m.interventions if i.type == "step"][0]
print(f"  intervención construida: type={itv.type}  n_omega={len(itv.omega)}"
      f"  -> orden {len(itv.omega) - 1}")
if len(itv.omega) != 2:
    FALLOS.append("n_omega no llega a la intervención")

d = tempfile.mkdtemp()
p = os.path.join(d, "sint.inp")
pipeline._write_inp(ts, m, p)
ordenes = None
with open(p) as fh:
    txt = fh.read().split("\n")
for k, L in enumerate(txt):
    if L.strip() == "step 60 2004" or L.strip().startswith("step"):
        ordenes = txt[k + 2].strip()
        break
print(f"  línea de órdenes de omega en el .inp: {ordenes!r}")

ts2, m2 = fue.inp.load(p)                       # round-trip
itv2 = [i for i in m2.interventions if i.type == "step"][0]
print(f"  releído por fue.inp.load: n_omega={len(itv2.omega)}")
if len(itv2.omega) != 2:
    FALLOS.append("round-trip pierde el orden")
print("  -> fue acepta la forma. El motor NO es el problema.\n")

# ── C. El contraste que queda huérfano ───────────────────────────────────────
print("== C. El Wald de ganancia nula")
from art import interventions as _itv
_src = inspect.getsource(_itv)
_i = _src.index("Joint Wald")
_gate = [L.strip() for L in _src[_i:_i + 2000].split("\n")
         if L.strip().startswith("if k >") or L.strip().startswith("k = len(")]
print("  en src/art/interventions.py, tras el bloque 'Joint Wald':")
for L in _gate[:2]:
    print(f"    {L}")
print("  k = numero de omegas libres EN UNA intervencion. La guarda sigue ahi,")
print("  y es correcta: con un solo omega no hay ganancia que contrastar. Lo")
print("  que estaba roto era el otro lado — que el carril guiado no pudiera")
print("  construir ninguna con k>1. El bloque D lo comprueba de extremo a")
print("  extremo.")
if not any(L.startswith("if k > 1") for L in _gate):
    FALLOS.append("no se localizo el gate k>1")
print()

# ── D. Aceptación: la FLT se construye y el Wald se emite ────────────────────
print("== D. De extremo a extremo por la superficie MCP")
_d = tempfile.mkdtemp()
_rng = np.random.default_rng(11)
_y = np.cumsum(_rng.standard_normal(120)) + 100
_y[60] += 4.0; _y[61] += 6.0; _y[62] += 3.0
_ts = fue.TimeSeries(_y.tolist(), freq=4, start=(2000, 1), name="EP")
_m = fue.Model(_ts, d=1, mu=0.0, estimate_mu=False, refactor=100.0)
_base = os.path.join(_d, "base.inp")
pipeline._write_inp(_ts, _m, _base)

_out = os.path.join(_d, "flt.inp")
_fn = getattr(mcp_server.suggest_intervention_form, "fn",
              mcp_server.suggest_intervention_form)
_fn(_base, _out, date="Q1/2015", form="step", n_omega=4,
    guion_path=os.path.join(_d, "g.json"), guion_decision="repro")
_, _mm = pipeline._load_ts_model(_out)
_itvs = [i for i in _mm.interventions if i.type in ("step", "pulse", "impulse")]
_k = len(_itvs[0].omega) if _itvs else 0
print(f"  intervención construida desde MCP: {_k} omegas")
if _k < 2:
    FALLOS.append("suggest_intervention_form no construyo la FLT")

_ti = getattr(mcp_server.test_interventions, "fn", mcp_server.test_interventions)
_txt = "\n".join(getattr(c, "text", "") for c in _ti(_out))
_hay_wald = ("ω(1)" in _txt and "Wald" in _txt)
print(f"  test_interventions emite el Wald de ganancia nula: {_hay_wald}")
if not _hay_wald:
    FALLOS.append("el Wald de ganancia nula sigue sin emitirse")
print()

print("=" * 70)
if FALLOS:
    print("CADENA CORTADA en la superficie MCP:", ", ".join(FALLOS))
    sys.exit(1)
print("sin fallos")
