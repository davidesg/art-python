#!/usr/bin/env python3
"""fase2_resumen.py — tablas del piloto de la fase 2 (fase2_orden_integracion.py).

1. Por celda: % de acierto en d de la REGLA DEL ÁRBOL (docs/ARBOL-orden-de-integracion.md),
   de la política ADF+KPSS de art y de pmdarima (ndiffs KPSS y ADF), y el reparto de la
   regla en «ambiguo» / «indeterminado».
2. Por celda y d estimada: tasa de «no rechaza su nula» de cada contraste —SF (raíz unitaria),
   DCD de sobrediferenciación (se cancela), DCD de subdiferenciación (se cancela)—, LR
   negativos y testigos negativos, y modelos verdaderos declarados «no adecuados».

La regla del árbol, en cada frontera, con la tabla de verdad:
    SF rechaza (ρ<1) + DCD no rechaza (θ→1)  → la d de abajo
    SF no rechaza   + DCD rechaza            → la d de arriba
    los dos rechazan                          → ambiguo (banda de cuasi-cancelación)
    ninguno rechaza                           → indeterminado
  Sin SF (sin AR), manda el DCD solo. La frontera 1/2 usa el DCD de subdiferenciación del
  modelo con d=2 si existe (el par cruzado, BUG-0235) y si no el de sobrediferenciación del
  modelo con d=1. Las celdas con d verdadera 2 no estiman d=0: se da la frontera 0/1 por
  superada.

Uso:  python research/fase2_resumen.py [CSV]
"""
import csv, os, sys
from collections import defaultdict, Counter

CSV = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fase2_piloto.csv")


def frontera(sfv, dcd_cancela, abajo, arriba):
    """sfv: 'estac.' | 'raíz' | ''; dcd_cancela: True | False | None."""
    if dcd_cancela is None and not sfv:
        return None
    if not sfv:
        return abajo if dcd_cancela else arriba
    if dcd_cancela is None:
        return abajo if sfv == "estac." else arriba
    if sfv == "estac." and dcd_cancela:
        return abajo
    if sfv == "raíz" and not dcd_cancela:
        return arriba
    return f"amb{abajo}{arriba}" if sfv == "estac." else f"ind{abajo}{arriba}"


def cancela(v):
    return {"cancela": True, "cancelada": True, "genuina": False}.get(v)


def regla(filas):
    por_d = {int(f["d_est"]): f for f in filas if f["ok"] == "1"}
    f0, f1, f2 = por_d.get(0), por_d.get(1), por_d.get(2)
    r01 = frontera(f0["SFv"], cancela(f0["DCD+v"]), 0, 1) if f0 else 1
    if r01 == 0:
        return "0"
    if f1 is None:
        return str(r01)
    dcd2 = cancela(f2["DCD-v"]) if f2 and f2["DCD-v"] else cancela(f1["DCD+v"])
    r12 = frontera(f1["SFv"], dcd2, 1, 2)
    if r12 is None:
        r12 = 1
    if isinstance(r01, str) and r01.startswith(("amb", "ind")) and r12 == 1:
        return r01
    return str(r12)


def main():
    filas = list(csv.DictReader(open(CSV)))
    series = defaultdict(list)
    for f in filas:
        series[(f["celda"], int(f["d_v"]), int(f["rep"]))].append(f)
    porc = defaultdict(lambda: {"n": 0, "reg": Counter(), "pol": 0, "kpss": 0, "adf": 0})
    for (celda, dv, rep), fs in series.items():
        c = porc[(celda, dv)]
        c["n"] += 1
        c["reg"][regla(fs)] += 1
        f = fs[0]
        c["pol"] += int(f["d_pol"]) == dv
        c["kpss"] += int(f["d_kpss"]) == dv
        c["adf"] += int(f["d_adf"]) == dv
    print("# 1. La d elegida: % de acierto (y reparto de la regla del árbol)\n")
    print(f"{'celda':<32}{'d':>2}{'n':>4} | {'árbol':>6}{'ADF+KPSS art':>13}{'kpss':>6}{'adf':>6} | reparto de la regla")
    tot = Counter(); m = 0
    for (celda, dv), c in sorted(porc.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        n = c["n"]; ok = c["reg"].get(str(dv), 0)
        p = lambda v: 100.0 * v / n                                    # noqa: E731
        rep = ", ".join(f"{k}:{v}" for k, v in c["reg"].most_common())
        print(f"{celda:<32}{dv:>2}{n:>4} | {p(ok):5.0f}%{p(c['pol']):12.0f}%{p(c['kpss']):5.0f}%{p(c['adf']):5.0f}% | {rep}")
        tot["arb"] += p(ok); tot["pol"] += p(c["pol"]); tot["kpss"] += p(c["kpss"]); tot["adf"] += p(c["adf"]); m += 1
    if m:
        print(f"{'MEDIA':<38} | {tot['arb']/m:5.0f}%{tot['pol']/m:12.0f}%{tot['kpss']/m:5.0f}%{tot['adf']/m:5.0f}%")

    print("\n# 2. Cada contraste, por d estimada (% de series)\n"
          "#    SF raíz = no rechaza ρ=1 · DCD+ cancela = no rechaza θ=1 en ∇^{d+1} ·"
          " DCD− cancela = no rechaza θ=1 en ∇^d\n")
    print(f"{'celda':<32}{'d':>2}{'est':>4} | {'SF':>5}{'raíz':>6} | {'DCD+':>5}{'canc':>6} | "
          f"{'DCD−':>5}{'canc':>6} | {'LR<0':>5}{'tst<0':>6} | {'no adec':>7} | fallos")
    grupos = defaultdict(list)
    for f in filas:
        grupos[(f["celda"], int(f["d_v"]), int(f["d_est"]))].append(f)
    for (celda, dv, de), fs in sorted(grupos.items(), key=lambda kv: (kv[0][1], kv[0][0], kv[0][2])):
        ok = [f for f in fs if f["ok"] == "1"]
        n = len(ok) or 1
        sf = [f for f in ok if f["SFv"]]
        dp = [f for f in ok if f["DCD+v"]]
        dm = [f for f in ok if f["DCD-v"]]
        r = lambda a, b: f"{100.0 * a / b:5.0f}%" if b else "    —"            # noqa: E731
        fallos = Counter(f["falla"].split(":")[0][:28] for f in ok if f["no_adecuado"] == "1")
        print(f"{celda:<32}{dv:>2}{de:>4} | {len(sf):>5}{r(sum(f['SFv']=='raíz' for f in sf), len(sf))} | "
              f"{len(dp):>5}{r(sum(f['DCD+v']=='cancela' for f in dp), len(dp))} | "
              f"{len(dm):>5}{r(sum(f['DCD-v']=='cancelada' for f in dm), len(dm))} | "
              f"{r(sum(f['lr_neg']=='1' for f in ok), n)}{r(sum(f['testigo_neg']=='1' for f in ok), n)} | "
              f"{r(sum(f['no_adecuado']=='1' for f in ok), n):>7} | "
              + ", ".join(f"{k}:{v}" for k, v in fallos.most_common(3))
              + (f" · errores {len(fs) - len(ok)}" if len(fs) > len(ok) else ""))


if __name__ == "__main__":
    main()
