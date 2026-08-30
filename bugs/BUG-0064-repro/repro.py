#!/usr/bin/env python3
"""BUG-0064 — `guion_map` volcaba los textos enteros y se pasaba del limite.

El mapa imprimia `decidido`, `evidencia`, `razon`, `descartado` y `callejon` SIN
LIMITE, uno por linea. Con nodos bien razonados eso son ~945 bytes por linea: el
RATIO del RUN 3 salia en 52.921 bytes repartidos en 56 lineas, y se truncaba a
fichero — justo la serie con mas ramas, o sea donde mas informacion habia que ver.

La intencion de diseno ya estaba escrita, en `_record_to_guion`: «el registro es
interno y la salida no debe crecer por documentar. Quien quiera ver lo
documentado llama a `export_guion`». El mapa es un MAPA; lo que faltaba era que
se comportara como tal.

Uso:  python repro.py
"""
import sys, os, json, warnings
warnings.filterwarnings("ignore")

R = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/run3/"
SERIES = [("RATIO", R + "RATIO/RATIO_guion.json"),
          ("PGAS",  R + "PGAS/PGAS_guion.json"),
          ("ITCER", R + "ITCER/ITCER_guion.json")]

LIMITE = 25_000   # orden de magnitud del limite de salida que se desbordaba


def main():
    if not os.path.exists(SERIES[0][1]):
        print("datos de la replica no disponibles"); return 0

    import art.mcp_server as M
    f = getattr(M.guion_map, "fn", M.guion_map)

    print(f"{'serie':7s} {'nodos':>6s} {'compacto':>10s} {'detalle':>10s} "
          f"{'reduccion':>10s}  ¿cabe?")
    roto = False
    for nom, p in SERIES:
        n = len(json.load(open(p, encoding="utf-8"))["entries"])
        a = len(f(p)[0].text.encode())
        b = len(f(p, detalle=True)[0].text.encode())
        cabe = a < LIMITE
        roto |= not cabe
        print(f"{nom:7s} {n:6d} {a:10,} {b:10,} {100*(1-a/b):9.0f}%  "
              f"{'si' if cabe else 'NO  <- el bug'}")

    # El recorte tiene que ANUNCIARSE, no ser silencioso.
    t = f(SERIES[0][1])[0].text
    anuncia = "textos recortados" in t and "detalle=True" in t
    print(f"\n¿anuncia el recorte y donde esta lo entero?  "
          f"{'si' if anuncia else 'NO  <- recorte silencioso'}")
    roto |= not anuncia

    # Y `detalle=True` tiene que devolver lo de antes, intacto.
    entero = f(SERIES[0][1], detalle=True)[0].text
    intacto = "[…]" not in entero
    print(f"¿detalle=True devuelve el texto intacto?     "
          f"{'si' if intacto else 'NO'}")
    roto |= not intacto

    print("\n" + ("BUG PRESENTE" if roto else
                  "ARREGLADO: el mapa cabe, dice lo que recorto, y lo entero "
                  "sigue a un parametro"))
    return 1 if roto else 0


if __name__ == "__main__":
    sys.exit(main())
