#!/usr/bin/env python3
"""bateria_contrastes_d.py — qué contrastes del orden de integración lanza art, y
cuáles debería lanzar según docs/ARBOL-orden-de-integracion.md.

Modelos simulados con d = 0, 1, 2 y siete estructuras ARMA; cada uno se estima en
art con su especificación VERDADERA (`confirm_and_estimate`) y se le pasa
`formal_tests(subdiferenciacion=True, run_meg=False)`. Se lee la salida y se anota:

  SF     Shin-Fuller directo · SFsob por sobreajuste · —
  DCDi   DCD de invertibilidad del MA del modelo
  DCD+   DCD de sobrediferenciación (y sobre qué ∇^k construye el candidato)
  DCD−   DCD de subdiferenciación
  par    el par en f=0 («coinciden», «discrepan», «sin par»)
  cierre la última conclusión de la salida

y se compara con lo que pide el árbol (sección 6):

  · SF directo si el AR tiene raíz real positiva; por sobreajuste si sólo complejas;
    ninguno sin AR.
  · DCD+ sólo con d ∈ {0, 1} (un paso: desde d=2 no hay ∇³ — BUG-0235).
  · DCD− con d ≥ 1; con AR real libre y sin MA, avisando de que no es fiable (BUG-0224).
  · Con d = 2, el par de la frontera 1/2 cruza dos modelos (SF del modelo en d=1):
    hoy no existe (BUG-0235).
  · El cierre no puede decir «adecuado» si el par no cierra (BUG-0232).

Uso:  ART_NO_VIEWER=1 python research/bateria_contrastes_d.py [N] [SEED] [REPS]
"""
import os, re, sys, tempfile, warnings
import numpy as np
from scipy.signal import lfilter
warnings.filterwarnings("ignore")
os.environ.setdefault("ART_NO_VIEWER", "1")
import art.mcp_server as s                                 # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
REPS = int(sys.argv[3]) if len(sys.argv) > 3 else 1

# nombre, φ, θ (convención Box-Jenkins)
ESTRUCTURAS = [
    ("ruido",              [],           []),
    ("AR(1) .6",           [0.6],        []),
    ("AR(1) .95",          [0.95],       []),
    ("AR(2) reales .5,.3", [0.5, 0.3],   []),
    ("AR(2) complejo 1,-.5", [1.0, -0.5], []),
    ("MA(1) .5",           [],           [0.5]),
    ("ARMA(1,1) .6/.3",    [0.6],        [0.3]),
]


def T(r):
    return r if isinstance(r, str) else "\n".join(
        t for c in r if isinstance(t := getattr(c, "text", None), str))


def sim(phi, theta, d, rng):
    a = rng.normal(size=N + 300)
    w = lfilter(np.r_[1, -np.array(theta, float)], np.r_[1, -np.array(phi, float)], a)[300:]
    for _ in range(d):
        w = np.cumsum(w)
    return w - w.min() + 100.0


def lee(ft):
    """Lo que lanzó formal_tests, leído de su texto."""
    o = {}
    o["SF"] = ("SFsob" if "recuperado por SOBREAJUSTE" in ft else
               "SF" if re.search(r"\*\*Shin-Fuller", ft) and "Φ̂₁ᵤ=" in ft else "—")
    m = re.search(r"Φ̂₁ᵤ=([\d.]+).*?→ ([^\n]+)", ft)
    o["SFv"] = ("estac." if m and "Estacionario" in m.group(2) else
                "raíz" if m and "Raíz unitaria" in m.group(2) else
                "estac." if "estacionario ✓ — d basta" in ft else
                "raíz" if "raíz unitaria → d+1" in ft else "")
    o["DCDi"] = "sí" if "DCD — no invertibilidad MA regular" in ft else "—"
    k = re.search(r"Candidato: ∇\^(\d+)", ft)
    od = re.search(r"DCD sobre-diferenciación regular.*?\n- θ̂=([+-][\d.]+), LR=([-\w.]+).*?→ ([^\n]+)",
                   ft, re.S)
    o["DCD+"] = (f"∇^{k.group(1)} θ̂{od.group(1)} LR{od.group(2)}" if od and k else
                 f"θ̂{od.group(1)} LR{od.group(2)}" if od else "—")
    o["DCD+v"] = ("cancela" if od and "sobre-diferencia" in od.group(3) else
                  "genuina" if od and "genuina" in od.group(3) else "")
    ud = re.search(r"DCD sub-diferenciación regular.*?\n- θ̂=([+-][\d.]+), LR=([-\w.]+).*?→ ([^\n]+)",
                   ft, re.S)
    o["DCD−"] = f"θ̂{ud.group(1)} LR{ud.group(2)}" if ud else "—"
    o["DCD−v"] = ("cancelada" if ud and "CANCELADA" in ud.group(3) else
                  "genuina" if ud and "genuina" in ud.group(3) else "")
    o["par"] = ("coinciden" if "Los dos coinciden" in ft else
                "discrepan" if "DISCREPAN" in ft else
                "sin par" if ("Sin par confirmatorio" in ft or "sin par" in ft) else "—")
    o["aviso224"] = bool(re.search(r"BUG-0224|AR libre|no es fiable", ft))
    o["no_adecuado"] = "todavía NO es adecuado" in ft
    m = re.search(r"La diagnosis falla en: ([^\n]+?)\.\s*\n", ft)
    o["falla"] = m.group(1)[:60] if m else ""
    o["cierre_adecuado"] = "El modelo es adecuado" in ft
    o["no_cierra"] = "no cierra" in ft or "NO está fijado" in ft
    return o


def esperado(d, phi):
    """Lo que pide el árbol para un modelo con esta d y este AR."""
    if phi:
        r = np.roots(np.r_[1.0, -np.asarray(phi, float)])   # raíces inversas
        reales_pos = [z for z in r if abs(z.imag) < 1e-9 and z.real > 0]
        sf = "SF" if reales_pos else "SFsob"
    else:
        sf = "—"
    return {"SF": sf, "DCD+": d < 2, "DCD−": d >= 1,
            "aviso224": bool(phi) and d >= 1}


def main():
    rng = np.random.default_rng(SEED)
    hdr = (f"{'modelo':<24}{'d':>2} | {'SF':<6}{'esp':<6}{'v':<7}| {'DCD+':<26}{'v':<8}| "
           f"{'DCD−':<20}{'v':<10}| {'par':<10}| {'cierre':<10}| discrepancias con el árbol")
    print(f"# bateria_contrastes_d.py — N={N} SEED={SEED} REPS={REPS}")
    print(hdr); print("-" * len(hdr))
    with tempfile.TemporaryDirectory() as tmp:
        for d in (0, 1, 2):
            for nombre, phi, theta in ESTRUCTURAS:
                for rep in range(REPS):
                    x = sim(phi, theta, d, rng)
                    inp = os.path.join(tmp, f"S{d}.inp")
                    s.create_inp([float(v) for v in x], inp, name="S", freq=12,
                                 start_year=2000, start_period=1)
                    out = os.path.join(tmp, f"m{d}.inp")
                    T(s.confirm_and_estimate(
                        inp, out, lam=1.0, d=d, D=0, p=len(phi), q=len(theta),
                        n_harmonics=0, seasonal=False, estimate_mu=(d == 0),
                        domain="generic", modo="autonomo"))
                    ft = T(s.formal_tests(out.replace(".inp", ".pre"), run_meg=False,
                                          subdiferenciacion=True))
                    o, e = lee(ft), esperado(d, phi)
                    dis = []
                    if o["SF"] != e["SF"]:
                        dis.append(f"SF {o['SF']}≠{e['SF']}")
                    if (o["DCD+"] != "—") != e["DCD+"]:
                        dis.append("DCD+ " + ("lanzado con d=2 (∇³)" if d == 2 else "falta"))
                    if (o["DCD−"] != "—") != e["DCD−"]:
                        dis.append("DCD− " + ("lanzado con d=0" if d == 0 else "falta"))
                    if "LR-inf" in o["DCD−"] or "LR-inf" in o["DCD+"]:
                        dis.append("LR −inf leído como veredicto (BUG-0232)")
                    if e["aviso224"] and not theta and o["DCD−"] != "—" and not o["aviso224"]:
                        dis.append("DCD− con AR libre sin aviso (BUG-0224)")
                    if o["cierre_adecuado"] and (o["no_cierra"] or o["par"] == "discrepan"):
                        dis.append("cierra «adecuado» sin par (BUG-0232)")
                    if re.search(r"LR-\d*\.?\d*[1-9]", o["DCD+"] + o["DCD−"]):
                        dis.append("LR negativo: el libre peor que el restringido")
                    if d == 2 and o["SFv"] == "raíz":
                        dis.append("SF pide d+1 desde d=2 (d=3)")
                    if d == 2:
                        dis.append("sin par cruzado d=1/d=2 (BUG-0235)")
                    if o["no_adecuado"]:
                        dis.append("diagnosis: " + o["falla"])
                    cierre = ("no adecuado" if o["no_adecuado"] else
                              "adecuado" if o["cierre_adecuado"] else "reformular")
                    print(f"{nombre:<24}{d:>2} | {o['SF']:<6}{e['SF']:<6}{o['SFv']:<7}| "
                          f"{o['DCD+']:<26}{o['DCD+v']:<8}| {o['DCD−']:<20}{o['DCD−v']:<10}| "
                          f"{o['par']:<10}| {cierre:<10}| {'; '.join(dis)}", flush=True)
    print("\nSF: lanzado · esp: lo que pide el árbol · v: veredicto (estac. = ρ<1; raíz = ρ≈1)."
          "\nDCD+: sobrediferenciación (∇^k del candidato) · DCD−: subdiferenciación."
          "\nModelos estimados con su especificación VERDADERA; n por serie = N.")


if __name__ == "__main__":
    main()
