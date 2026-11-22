"""BUG-0263: the autonomous lane's protocol does not reach a client that
truncates the server's instructions, and nothing else serves it.

art's instructions are about 49,000 characters. The section that says how to
work in the autonomous lane ("EL CARRIL AUTÓNOMO — TÚ ERES EL ANALISTA": the
nodes in order, modo="autonomo", the guion, the rules) starts near character
19,000. A client that keeps only the first few thousand characters (measured:
about 4,000 on 2026-11-22) gives the model the first question and the
sentence "sigue «EL CARRIL AUTÓNOMO…», más abajo" — and no "más abajo".

Open while the section is beyond the budget AND no tool returns it.

    python3 bugs/BUG-0263-repro/repro.py   # exits 1 while open
"""
import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
import art.mcp_server as m   # noqa: E402

BUDGET = 4000                # what the client was seen to deliver
TITLE = "EL CARRIL AUTÓNOMO — TÚ ERES EL ANALISTA\n═"
txt = m._INSTRUCTIONS
at = txt.find(TITLE)
print(f"instructions: {len(txt)} characters; the autonomous section starts at {at}")
tools = {t.name for t in asyncio.run(m.mcp.list_tools())}
has_tool = "protocolo_autonomo" in tools
print("a tool serves the section (protocolo_autonomo):", has_tool)
named_early = "protocolo_autonomo" in txt[:BUDGET]
print(f"the first {BUDGET} characters name that tool:", named_early)
if at < 0:
    print("the section is not in the instructions at all")
    sys.exit(2)
if at > BUDGET and not (has_tool and named_early):
    print("OPEN: a truncating client never sees the autonomous lane's protocol")
    sys.exit(1)
if has_tool:
    out = m.protocolo_autonomo()
    body = out if isinstance(out, str) else "".join(getattr(c, "text", "") for c in out)
    if "LOS NODOS" not in body or 'modo="autonomo"' not in body:
        print("the tool does not return the section")
        sys.exit(1)
print("closed: the protocol reaches a client that truncates the instructions")
sys.exit(0)
