#!/usr/bin/env python3
"""fase2_orden_integracion.py — tamaño, potencia y la regla del árbol (piloto).

Plan: docs/PLAN-bateria-orden-integracion-fase2.md. Para cada celda (modelo verdadero)
y réplica se simula una serie y se estiman, con los órdenes VERDADEROS (brazo
oráculo), los modelos con d = d_v − 1, d_v, d_v + 1 (dentro de 0…2). Sobre cada uno:
`confirm_and_estimate` + `formal_tests(subdiferenciacion=True, run_meg=False)`, y se
guarda lo que dice cada contraste (lectura de `bateria_contrastes_d.lee`). Sobre la
serie: la política ADF+KPSS de art (un paso cada vez) y `ndiffs` de pmdarima.

Una fila por (celda, réplica, d estimada) en un CSV; reanudable: lo que ya está en el
CSV no se repite. El resumen lo hace `fase2_resumen.py`.

Fase 2b (foco): FASE2_FOCO="nombre|d;nombre|d;…" restringe las celdas (los índices
de CELDAS no cambian, así que la semilla de cada réplica es la del piloto y sus filas
se pueden reutilizar), y FASE2_BRAZO=identificado estima en cada d los órdenes que
art pone primero (`suggest_orders`, opción B) en vez de los verdaderos.

Uso:  ART_NO_VIEWER=1 python research/fase2_orden_integracion.py [REPS] [N] [PROCS] [CSV]
"""
import csv, math, os, sys, tempfile, warnings
from multiprocessing import Pool
import numpy as np
from scipy.signal import lfilter
warnings.filterwarnings("ignore")
os.environ.setdefault("ART_NO_VIEWER", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPS = int(sys.argv[1]) if len(sys.argv) > 1 else 50
N = int(sys.argv[2]) if len(sys.argv) > 2 else 200
PROCS = int(sys.argv[3]) if len(sys.argv) > 3 else 4
CSV = sys.argv[4] if len(sys.argv) > 4 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fase2_piloto.csv")
SEED = 2026
FOCO = {tuple(c.rsplit("|", 1)) for c in os.environ.get("FASE2_FOCO", "").split(";") if c}
BRAZO = os.environ.get("FASE2_BRAZO", "oraculo")

AR7_VILLAVERDE = [0.1771, 0.0586, 0.1992, -0.0116, -0.0036, -0.0390, 0.2380]
AR4_SALAMANCA = [0.334, 0.136, 0.111, 0.187]


def _cplx(per, r):
    return [2 * r * math.cos(2 * math.pi / per), -r * r]


# celda: (nombre, φ, θ, d verdadera, extra)
CELDAS = []
for d in (0, 1, 2):
    CELDAS += [("ruido", [], [], d, ""), ("AR(1) .5", [0.5], [], d, ""),
               ("MA(1) .5", [], [0.5], d, ""), ("ARMA(1,1) .6/.3", [0.6], [0.3], d, ""),
               ("AR(2) reales .5,.3", [0.5, 0.3], [], d, ""),
               ("AR(2) cplx corto p8 r.7", _cplx(8, 0.7), [], d, ""),
               ("AR(2) cplx largo p36 r.97", _cplx(36, 0.97), [], d, "")]
for d in (1, 2):
    CELDAS += [(f"AR(1) {f}", [f], [], d, "") for f in (0.8, 0.9, 0.95, 0.98)]
    CELDAS += [("ARMA(1,1) señal+ruido .95/.7", [0.95], [0.7], d, ""),
               ("MA(1) .9", [], [0.9], d, ""), ("MA(1) .95", [], [0.95], d, "")]
CELDAS += [("I(0) + tendencia", [0.5], [], 0, "tendencia"),
           ("AR(1) .5 + 3 escalones", [0.5], [], 1, "escalones"),
           ("AR(1) .5 + cambio de varianza", [0.5], [], 1, "varianza"),
           ("AR(4) Salamanca", AR4_SALAMANCA, [], 1, ""),
           ("IMA θ.75 Salamanca", [], [0.75], 2, ""),
           ("AR(7) Villaverde", AR7_VILLAVERDE, [], 1, "")]

CAMPOS = ["celda", "d_v", "rep", "d_est", "ok", "SF", "SFv", "DCDi", "DCD+", "DCD+v",
          "DCD-", "DCD-v", "par", "no_adecuado", "falla", "cierre_adecuado",
          "lr_neg", "testigo_neg", "d_pol", "d_kpss", "d_adf", "brazo", "p_est", "q_est"]


def simula(phi, theta, d, extra, rng):
    a = rng.normal(size=N + 300)
    if extra == "varianza":
        a[300 + N // 2:] *= 0.4
    w = lfilter(np.r_[1, -np.array(theta, float)], np.r_[1, -np.array(phi, float)], a)[300:]
    for _ in range(d):
        w = np.cumsum(w)
    if extra == "tendencia":
        w = w + 0.05 * np.arange(N)
    if extra == "escalones":
        for t0 in (N // 5, N // 2, 4 * N // 5):
            w[t0:] += 4.0 if t0 != N // 2 else -4.0
    return w - w.min() + 100.0


def _T(r):
    return r if isinstance(r, str) else "\n".join(
        t for c in r if isinstance(t := getattr(c, "text", None), str))


def trabajo(args):
    ic, rep = args
    nombre, phi, theta, dv, extra = CELDAS[ic]
    import art.mcp_server as s
    import pmdarima as pm
    import fue
    from art.describe import describe_unit_root
    from art import policy as pol
    from bateria_contrastes_d import lee
    rng = np.random.default_rng([SEED, ic, rep])
    x = simula(phi, theta, dv, extra, rng)
    ts = fue.TimeSeries(list(map(float, x)), freq=12, start=(2000, 1), name="S")
    try:
        urt = describe_unit_root(ts, lam=1.0)
        dp = pol.decide_d(urt.data, seasonal=False)
        if dp >= 1:
            dp = pol.decide_d(describe_unit_root(ts, lam=1.0, max_d=dp + 1, current_d=dp).data,
                              seasonal=False, current_d=dp)
    except Exception:
        dp = -1
    dk = int(pm.arima.ndiffs(x, test="kpss", max_d=2))
    da = int(pm.arima.ndiffs(x, test="adf", max_d=2))
    filas = []
    with tempfile.TemporaryDirectory() as tmp:
        inp = os.path.join(tmp, "S.inp")
        s.create_inp([float(v) for v in x], inp, name="S", freq=12,
                     start_year=2000, start_period=1)
        for de in sorted({dv - 1, dv, dv + 1} & {0, 1, 2}):
            fila = dict(celda=nombre, d_v=dv, rep=rep, d_est=de, d_pol=dp, d_kpss=dk, d_adf=da,
                        brazo=BRAZO)
            try:
                p_e, q_e = len(phi), len(theta)
                if BRAZO == "identificado":
                    from art import suggest_orders
                    sp = suggest_orders(ts, d=de, D=0, lam=1.0, top_n=5, P_max=0, Q_max=0)
                    p_e, q_e = (sp[0].p, sp[0].q) if sp else (0, 0)
                fila.update(p_est=p_e, q_est=q_e)
                out = os.path.join(tmp, f"m{de}.inp")
                _T(s.confirm_and_estimate(inp, out, lam=1.0, d=de, D=0, p=p_e,
                                          q=q_e, n_harmonics=0, seasonal=False,
                                          estimate_mu=(de == 0), domain="generic",
                                          modo="autonomo"))
                ft = _T(s.formal_tests(out.replace(".inp", ".pre"), run_meg=False,
                                       subdiferenciacion=True))
                o = lee(ft)
                import re
                lrs = [float(v) for v in re.findall(r"LR=(-?[\d.]+|-inf|inf)", ft)
                       if v not in ("inf", "-inf")]
                fila.update(ok=1, SF=o["SF"], SFv=o["SFv"], DCDi=o["DCDi"],
                            **{"DCD+": o["DCD+"], "DCD+v": o["DCD+v"],
                               "DCD-": o["DCD−"], "DCD-v": o["DCD−v"]},
                            par=o["par"], no_adecuado=int(o["no_adecuado"]),
                            falla=o.get("falla", ""), cierre_adecuado=int(o["cierre_adecuado"]),
                            lr_neg=int(any(v < -1e-3 for v in lrs) or "LR=-inf" in ft),
                            testigo_neg=int(bool(re.search(r"sobre-diferenciación regular.*?\n- θ̂=-", ft, re.S))))
            except Exception as e:                      # noqa: BLE001
                fila.update(ok=0, falla=f"{type(e).__name__}: {e}"[:80])
            filas.append(fila)
    return filas


def main():
    hechos = set()
    if os.path.exists(CSV):
        with open(CSV) as f:
            for r in csv.DictReader(f):
                hechos.add((r["celda"], int(r["d_v"]), int(r["rep"])))
    tareas = [(ic, rep) for ic, c in enumerate(CELDAS) for rep in range(REPS)
              if (c[0], c[3], rep) not in hechos
              and (not FOCO or (c[0], str(c[3])) in FOCO)]
    print(f"[{BRAZO}] {len(FOCO) or len(CELDAS)} celdas × {REPS} réplicas, n={N}: {len(tareas)} series pendientes "
          f"({len(hechos)} hechas) → {CSV}", flush=True)
    nuevo = not os.path.exists(CSV)
    with open(CSV, "a", newline="") as f, Pool(PROCS) as pool:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if nuevo:
            w.writeheader()
        for k, filas in enumerate(pool.imap_unordered(trabajo, tareas), 1):
            for fila in filas:
                w.writerow({c: fila.get(c, "") for c in CAMPOS})
            f.flush()
            if k % 25 == 0:
                print(f"  {k}/{len(tareas)}", flush=True)
    print("hecho", flush=True)


if __name__ == "__main__":
    main()
