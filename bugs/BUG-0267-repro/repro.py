"""BUG-0267: the form of an intervention can be decided without the node that
decides it.

Fixture: AGPROD_ma1.inp — log silver production of New Spain, annual
1701-1810 (n=110), ARIMA(0,1,1) without intervention. Its largest residual is
1803 (z = +3.39).

Two defects, chained:
  (A) confirm_and_estimate's diagnosis prints «Intervenciones sugeridas:
      1803 ... pulse (observación aislada)» — a FORM, chosen by the old
      policy rule (pulse unless an adjacent residual is also extreme), while
      guided_intervention's Call 2 on the same model and date finds that the
      data admit a STEP (1/1803×1, permanent): the level stays up in 1804.
  (B) guided_intervention(date, form=...) builds and estimates any form it is
      given (Call 3) without Call 2 having been run for that date, and says
      nothing before estimating. In the session the pulse was built straight
      from the diagnosis's suggestion; Treadway failed only AFTERWARDS
      (residual at 1803 not absorbed, 1804 anomalous).

  (C) the call option A writes, `suggest_intervention_form(inp_path=..., date=...)`,
      has no `output_path`, which the tool requires: copied as written it
      fails, and the working path left is the shortcut (found reviewing the
      bug, 2026-11-26).

Open while
  (A) the diagnosis suggests `pulse` for 1803 while Call 2 says step; or
  (B) Call 3 with form="pulse" for 1803, without a previous Call 2, returns
      an estimated model without stating, before the estimate, the form the
      data admit (the configuration 1/1803×1 / a step); or
  (C) option A's suggest_intervention_form call, run as written, fails.

    python3 bugs/BUG-0267-repro/repro.py   # exits 1 while open
"""
import asyncio
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["ART_NO_VIEWER"] = "1"
import art.mcp_server as m   # noqa: E402


def call(tool, **kw):
    out = asyncio.run(m.mcp.call_tool(tool, kw))
    items = out[0] if isinstance(out, tuple) else out
    return "\n".join(getattr(c, "text", "") for c in items)


abierto = []
d = tempfile.mkdtemp()
inp = os.path.join(d, "AGPROD_ma1.inp")
shutil.copy(os.path.join(HERE, "AGPROD_ma1.inp"), inp)

# (A) the diagnosis's suggested form vs Call 2's verdict, same model and date.
diag = call("confirm_and_estimate", inp_path=inp, output_path=os.path.join(d, "base.inp"),
            lam=0.0, d=1, D=0, p=0, q=1, n_harmonics=0, seasonal=False, estimate_mu=False)
sug = re.search(r"1803 \(obs \d+, z=[+-][\d.]+\): (\w+)", diag)
forma_diag = sug.group(1) if sug else None
print("(A) diagnosis suggests for 1803:", forma_diag)

# (C) option A's call, run as it is written
m_a = re.search(r"`suggest_intervention_form\((.*?)\)`", diag)
c_ok = False
if m_a:
    kw = dict(re.findall(r'(\w+)="([^"]*)"', m_a.group(1)))
    try:
        r_a = call("suggest_intervention_form", **kw)
        c_ok = "MODELO ESTIMADO" in r_a
    except Exception as e:                                   # noqa: BLE001
        print("(C) error:", str(e).splitlines()[-1][:160])
print("(C) option A's call runs as written:", c_ok)
if not c_ok:
    abierto.append("C: la llamada de la opción A no se ejecuta tal cual")

base = os.path.join(d, "base.inp")
c2 = call("guided_intervention", inp_path=base, date="1803")
admite_escalon = "1/1803×1" in c2 and "escalón en el nivel" in c2
print("(A) Call 2 admits a step from 1803:", admite_escalon)
if forma_diag == "pulse" and admite_escalon:
    abierto.append("A: la diagnosis sugiere pulse y la Llamada 2 dice escalón")

# (B) Call 3 with a form, no Call 2 before, on a FRESH copy (no state from above).
d2 = tempfile.mkdtemp()
inp2 = os.path.join(d2, "AGPROD_ma1.inp")
shutil.copy(os.path.join(HERE, "AGPROD_ma1.inp"), inp2)
c3 = call("guided_intervention", inp_path=inp2, date="1803", form="pulse", n_omega=1,
          output_path=os.path.join(d2, "pulse.inp"))
estimo = "MODELO ESTIMADO" in c3
antes = c3.split("MODELO ESTIMADO")[0] if estimo else c3
# The Call 3 header says «N escalón(es) en el nivel» for ANY form (it counts ω),
# so a generic «escalón» is not a warning: look for Call 2's verdict or a
# reference to the form node.
avisa = ("1/1803×1" in antes) \
    or bool(re.search(r"Llamada 2|forma que admite|no admite|sin pasar por", antes, re.I))
print("(B) Call 3 estimated:", estimo, "| stated the admitted form before estimating:", avisa)
if estimo and not avisa:
    abierto.append("B: la Llamada 3 construye una forma sin pasar por la Llamada 2 y sin avisar")

for x in (d, d2):
    shutil.rmtree(x, ignore_errors=True)
if abierto:
    print("ABIERTO:", "; ".join(abierto))
    sys.exit(1)
print("CERRADO")
