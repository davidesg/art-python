"""BUG-0239: el AICc del identificador, de columna a AVISO.

Salamanca y Villaverde (precio €/m², d = 1): el AICc prefería un ARMA(1,1) con
φ ≈ 0,95, la señal de que el orden de integración estaba abierto, y la lista lo
enseñaba como un ΔAICc junto a la similitud, sin decir qué significaba. Sale 1
mientras la lista lleve ΔAICc o falte el aviso en alguna de las dos.

    PYTHONPATH=src python3 bugs/BUG-0239-repro/repro.py
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
os.environ.setdefault("ART_NO_VIEWER", "1")
import fue
from art.describe import describe_identification
HERE = os.path.dirname(os.path.abspath(__file__))
ok = True
for nombre, inp in [("Salamanca", "BUG-0232-repro/Salamanca.inp"),
                    ("Villaverde", "BUG-0235-repro/Villaverde.inp")]:
    ts, _ = fue.load(os.path.join(HERE, "..", inp))
    t = describe_identification(ts, d=1, D=0, lam=0.0, estacional=False).summary
    columna = "ΔAICc" in t
    aviso = next((l for l in t.splitlines() if "Aviso del AICc" in l), "")
    print(f"{nombre}: ΔAICc en la lista: {columna} · aviso: {aviso[:110] or '—'}")
    ok = ok and not columna and bool(aviso)
sys.exit(0 if ok else 1)
