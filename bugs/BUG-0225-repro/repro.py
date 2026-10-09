"""Repro de BUG-0225…0231: el carril GUIADO de IPC_ES (P02, 8-oct-2026).

Recorre los mismos pasos que el analista, con guion, en un directorio temporal,
e imprime la evidencia de cada defecto. Uso:  ART_NO_VIEWER=1 python repro.py
"""
import os, re, shutil, tempfile
os.environ.setdefault("ART_NO_VIEWER", "1")
import art.mcp_server as s

HERE = os.path.dirname(os.path.abspath(__file__))
def T(r): return r if isinstance(r, str) else "\n".join(
    t for c in r if isinstance(t := getattr(c, "text", None), str))
def grep(pat, t): return [l.strip() for l in t.splitlines() if re.search(pat, l)]

w = tempfile.mkdtemp(); shutil.copy(os.path.join(HERE, "IPC_ES.inp"), w)
inp, g = os.path.join(w, "IPC_ES.inp"), os.path.join(w, "g.json")
GI = dict(guion_path=g, domain="price_index")

t1 = T(s.guided_identification(inp, expectativas="índice; inercia de 1-2 meses", **GI))
print("0225", grep(r"varianza homogénea|dispersión CAE", t1))

t2 = T(s.guided_identification(inp, lam=0, razon="dominio", **GI))
print("0226", grep(r"Punto de partida: d = 1", t2)[:1], grep(r"\*\*d\*\* pendiente", t2))
t3 = T(s.guided_identification(inp, lam=0, d=1, razon="tendencia", **GI))
print("0226", grep(r"n3: \*\*d = 1\*\*", t3))
print("0227", grep(r"único orden con consenso", t3), grep(r"recomendación de la tabla es d=0", t3),
      "fila d=0 en el paso 3:", "| 0 | ln |" in t3.split("¿Hace falta una diferencia más?")[-1])

t4 = T(s.guided_identification(inp, lam=0, d=1, D=0, razon="sin estac.", **GI))
print("0228", grep(r"\d\. ARIMA\(\d,1,\d\)", t4))

kw = dict(lam=0, d=1, D=0, n_harmonics=0, seasonal=False, estimate_mu=True,
          domain="price_index", guion_path=g)
m1 = T(s.confirm_and_estimate(inp, os.path.join(w, "m01.inp"), p=0, q=1, guion_name="m01 MA(1)", **kw))
print("0229", grep(r"guion n5: \*\*ordenes", m1))
m2 = T(s.confirm_and_estimate(inp, os.path.join(w, "m02.inp"), p=1, q=0, parent=5, guion_name="m02 AR(1)", **kw))
m3 = T(s.confirm_and_estimate(inp, os.path.join(w, "m03.inp"), p=2, q=0, parent=7, guion_name="m03 AR(2)", **kw))
print("0230", grep(r"0\.0693|\(0\.0680\)", m3)[:2], grep(r"Adoptar este modelo", m3), grep(r"Quitar lo que sobra", m3)[:1])
print("0231", grep(r"Ruido blanco \(Q\)", m3), "Q(12) citada:", bool(re.search(r"Q\(12", m3)), "Q(24) citada:", bool(re.search(r"Q\(24", m3)))
print("0229", grep(r"ordenes", T(s.guion_node(g, "ordenes", "AR(1) (m02)", razon="empate; dominio",
                                             criterio="dominio", parent=7)))[:1])
mp = T(s.guion_map(g))
print("0229", grep(r"sin modelo estimado detrás|el analista corrigió", mp))
print("tmp:", w)
