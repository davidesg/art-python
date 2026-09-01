#!/usr/bin/env python3
"""BUG-0065 — la nula de Shin-Fuller no era la de Shin-Fuller.

H0 de SF es UNA raiz en rho_m = 1-4/n **con el resto de la estructura AR libre**:
es la forma aumentada de Dickey-Fuller. El codigo hacia otra cosa — recorria
TODOS los factores poniendo el primer coeficiente de cada uno en rho_m y los
demas en cero.

(a) NO ERA INVARIANTE A LA PARAMETRIZACION. El mismo modelo ajustado, con
    identica verosimilitud, daba estadisticos distintos segun como se escribiera
    el AR:
        (1 - 1.6390B + 0.6668B^2)     nula [rho, 0]     Phi = 25.746
        (1 - 0.8890B)(1 - 0.7500B)    nula [rho][rho]   Phi =  7.632
    La segunda impone DOS raices casi unitarias, que no es H0.

(b) AL ANULAR EL RESTO, el contraste medía «¿el AR completo ajusta mejor que un
    AR(1) en rho_m?» en vez de «¿la raiz dominante es 1?». Con una raiz cerca de
    1 y otra claramente estacionaria, la segunda infla el estadistico y tapa a la
    primera.

Con la nula correcta el mismo modelo da Phi = 0.298, por debajo del critico al
10% (1.07): NO se rechaza la raiz unitaria, o sea d=1.

Y no es academico: en el RUN 4 de la replica un analista se quedo en d=0 sobre
PGAS apoyandose en este veredicto, con un modelo cuya Q fallaba en cuatro
retardos.

Uso:  python repro.py
"""
import sys, os, io, warnings
warnings.filterwarnings("ignore")

M14 = ("/home/david/Dropbox/TFM_UCM/Tesis_Michael_DS/replica/run4/"
       "PGAS/PGAS_m14.pre")


def factorizado(destino):
    """El MISMO modelo, escrito como dos AR(1) en vez de un AR(2)."""
    s = io.open(M14, encoding="utf-8").read()
    viejo = ("**Number and orders of regular AR operators:\n1 2\n**\n"
             "1.6390 1\n-0.6668 1")
    nuevo = ("**Number and orders of regular AR operators:\n2 1 1\n**\n"
             "0.8890 1\n**\n0.7500 1")
    assert s.count(viejo) == 1
    io.open(destino, "w", encoding="utf-8").write(s.replace(viejo, nuevo))
    return destino


def main():
    if not os.path.exists(M14):
        print("datos de la replica no disponibles"); return 0

    import tempfile
    import fue
    from art.formal_tests import shin_fuller

    tmp = tempfile.mkdtemp(prefix="bug0065_")
    fac = factorizado(os.path.join(tmp, "fact.inp"))

    print("El MISMO modelo, escrito de dos formas:\n")
    print(f"{'parametrizacion':22s} {'logL':>10s} {'Phi_1u':>9s} {'df':>3s}  veredicto")
    vals = []
    for etq, p in (("AR(2) conjunto", M14), ("AR(1) x AR(1)", fac)):
        ts, m = fue.load(p); m.fit()
        r = shin_fuller(m)
        ver = ("estacionario" if r.phi_1u > r.crit_5pct
               else "NO rechaza la raiz unitaria -> d+1")
        print(f"{etq:22s} {r.loglik_free:10.3f} {r.phi_1u:9.3f} {r.df:3d}  {ver}")
        vals.append((round(r.loglik_free, 6), round(r.phi_1u, 6), r.df))

    invariante = vals[0] == vals[1]
    print(f"\n1) ¿es INVARIANTE a la parametrizacion?  "
          f"{'si' if invariante else 'NO  <- el bug'}")

    # 2) la nula tiene que restringir UNA cosa
    ts, m = fue.load(M14); m.fit()
    r = shin_fuller(m)
    un_grado = (r.df == 1)
    print(f"2) ¿restringe UNA raiz (df=1)?            "
          f"{'si' if un_grado else f'NO: df={r.df}  <- el bug'}")

    # 3) y el veredicto sobre este caso tiene que ser d+1
    pide_d1 = r.phi_1u < r.crit_10pct
    print(f"3) ¿pide d+1 en el caso del RUN 4?        "
          f"{'si' if pide_d1 else 'NO  <- el bug'}   "
          f"(Phi={r.phi_1u:.3f} < crit 10%={r.crit_10pct})")

    ok = invariante and un_grado and pide_d1
    print("\n" + ("ARREGLADO: una raiz, resto libre, y el mismo modelo da el "
                  "mismo contraste" if ok else "BUG PRESENTE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
