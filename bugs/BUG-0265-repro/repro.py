"""BUG-0265: in the autonomous lane, a tool with no `modo` returns its figures
as images and opens them in the desktop's viewer; and even the tools with
`modo` open the viewer before their figures are taken out of the answer.

The autonomous lane is declared per call (`modo="autonomo"`) and only six
tools take it. In sima's autonomous trial run (2026-11-26) an agent redoing
an intervention called intervention_analysis on a series it was working in
the autonomous lane: its figures came back as images (tokens) and opened on
the analyst's desktop.

The lane is now remembered per series folder: a tool with `modo` sets its
folder's lane (also "guiado", its default, so the guided lane resets it at
once); a tool without `modo` follows its folder's lane. The guided lane does
not change.

Open while, after confirm_and_estimate(modo="autonomo") on a series, either
that call or intervention_analysis on the same series returns an image or
asks the viewer to open; or a guided call on the same series stops showing
its figures.

    python3 bugs/BUG-0265-repro/repro.py   # exits 1 while open
"""
import asyncio
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.pop("ART_NO_VIEWER", None)
import art.mcp_server as m   # noqa: E402

opened = []
m._abrir_visor = lambda path: opened.append(path) or ""   # record, never launch
m._BAJO_SERVIDOR = True

src = os.path.join(ROOT, "tests", "fixtures", "bug_0196_0197", "MUSKRAT.inp")
d = tempfile.mkdtemp()
inp = os.path.join(d, "MUSKRAT.inp")
shutil.copy(src, inp)


def call(tool, **kw):
    out = asyncio.run(m.mcp.call_tool(tool, kw))
    items = out[0] if isinstance(out, tuple) else out
    return sum(1 for c in items if getattr(c, "type", None) == "image")


def run(tool, **kw):
    n0 = len(opened)
    imgs = call(tool, **kw)
    return imgs, len(opened) - n0


res = {}
res["confirm autonomo"] = run("confirm_and_estimate", inp_path=inp,
                              output_path=os.path.join(d, "MUSKRAT_m00.inp"),
                              modo="autonomo")
res["intervention_analysis after autonomo"] = run(
    "intervention_analysis", inp_path=os.path.join(d, "MUSKRAT_m00.pre"))
res["confirm guiado"] = run("confirm_and_estimate", inp_path=inp,
                            output_path=os.path.join(d, "MUSKRAT_m01.inp"))
res["intervention_analysis after guiado"] = run(
    "intervention_analysis", inp_path=os.path.join(d, "MUSKRAT_m01.pre"))
for k, (imgs, views) in res.items():
    print(f"  {k}: images returned {imgs}, viewer asked {views}")

auto_ok = all(res[k] == (0, 0) for k in ("confirm autonomo",
                                          "intervention_analysis after autonomo"))
guided_ok = res["confirm guiado"][0] > 0 and res["confirm guiado"][1] > 0
if not auto_ok:
    print("OPEN: the autonomous lane returns figures or opens the viewer")
    sys.exit(1)
if not guided_ok:
    print("BROKEN: the guided lane no longer shows its figures")
    sys.exit(3)
print("FIXED")
