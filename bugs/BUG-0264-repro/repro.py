"""BUG-0264: the autonomous lane's protocol does not send the intervention
node to art's form proposal, nor say that the forms are in LEVELS.

Node 7 says only "intervenciones si los anómalos distorsionan la
identificación, ANTES de (p,q). Una cada vez." In sima's autonomous trial run
(2026-11-25, the US monetary VAR) an agent fixed a step by hand, with no
proposal from art, reading the shape of the differenced residual. art's
suggest_intervention_form already specifies in levels (a spike in the
differences is a step in the level); the protocol has to send the agent there
first, and let it depart only with its reason.

Open while node 7 of the section does not name suggest_intervention_form,
say LEVELS, and allow departing only with a written reason.

    python3 bugs/BUG-0264-repro/repro.py   # exits 1 while open
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
import art.mcp_server as m   # noqa: E402

sec = m._seccion_autonomo()
i = sec.find("  7. intervenciones")
j = sec.find("  8. ordenes")
if i < 0 or j < 0:
    print("node 7 or node 8 not found in the autonomous section")
    sys.exit(2)
node7 = sec[i:j]
print(node7)
checks = {
    "names suggest_intervention_form": "suggest_intervention_form" in node7,
    "says the forms are in LEVELS": re.search(r"NIVEL", node7) is not None,
    "a spike in the differences is a step": re.search(r"(?i)escal[oó]n", node7) is not None,
    "departs only with a written reason": re.search(r"(?i)raz[oó]n", node7) is not None,
}
for k, v in checks.items():
    print(f"  {k}: {v}")
if not all(checks.values()):
    print("OPEN: the protocol does not send the intervention node to art's proposal")
    sys.exit(1)
print("FIXED")
