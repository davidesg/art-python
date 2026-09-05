"""BUG-0089 — con ARMA, mirar UN residuo deja de ser el contraste de Treadway.

La regla de Treadway sale de la condición de primer orden: los residuos quedan
ortogonales a cada regresor filtrado de la intervención,

    Σ_t a_t·x_t^(j) = 0,     x_t^(j) = π(B)·[B^j/δ(B)]·ξ_t

Preguntar «¿queda masa del suceso en el vecino?» es preguntar si hace falta un ω
MÁS, y eso es el contraste de puntuación

    LM = (Σ_t a_t·x_t^(k+1))² / (σ̂² Σ_t (x_t^(k+1))²)  ~  χ²(1)

SIN ARMA el regresor filtrado es una FICTICIA (π(B)=1): la suma colapsa en un
término, `LM = a²/σ̂² = z²`, y el residuo tipificado del vecino ES el contraste.
Ahí el umbral 2.0 es exactamente el 5%.

CON ARMA el regresor es la forma del filtro π, la suma NO colapsa, y mirar un
solo residuo pierde potencia. Este repro lo mide, y mide cuánto.

Tarda: estima 4 × K modelos. `K=200` en el reporte; con `K` menor la lectura es
la misma con más ruido.
"""
import sys

sys.path.insert(0, "src")

import numpy as np
from scipy import stats

import fue

K = int(sys.argv[1]) if len(sys.argv) > 1 else 60


def caso(seed, ar, w1, n=200, T=100, w0=4.0):
    """Suceso de dos períodos en el nivel; se ajusta UNO y se mira el vecino."""
    rng = np.random.default_rng(seed)
    e = rng.standard_normal(n)
    a = e.copy()
    if ar:
        for t in range(1, n):
            a[t] = e[t] + ar * a[t - 1]
    y = a.copy()
    y[T - 1] += w0
    y[T] += w1
    ts = fue.TimeSeries(y.tolist(), freq=1, start=(1900, 1), name="X")
    kw = dict(d=0, mu=0.0, estimate_mu=False, refactor=1.0)
    if ar:
        kw.update(ar=[[0.0]], ar_free=[[True]])

    def fit(k):
        itv = fue.Intervention("pulse", at=T - 1, omega=[0.0] * k,
                               omega_free=[True] * k)
        m = fue.Model(ts, interventions=[itv], **kw)
        m.fit()
        return m

    m1, m2 = fit(1), fit(2)
    r = np.asarray(m1._result.residuals, dtype=float)
    off = len(y) - len(r)
    z = r[T - off] / (r.std(ddof=0) or 1.0)
    return abs(z), 2.0 * (m2._result.loglik - m1._result.loglik)


FALLOS = []
resultados = {}
for ar in (None, 0.6):
    et = "sin ARMA" if ar is None else f"AR(1) phi={ar}"
    for w1, cual in ((0.0, "TAMANO"), (2.5, "POTENCIA")):
        zs, lrs = [], []
        for s in range(K):
            try:
                z, lr = caso(s + 1000, ar, w1)
                if np.isfinite(z) and np.isfinite(lr):
                    zs.append(z); lrs.append(lr)
            except Exception:
                pass
        zs, lrs = np.array(zs), np.array(lrs)
        p_z2 = float(np.mean(zs > 2.0))
        p_lr = float(np.mean(stats.chi2.sf(lrs, 1) < 0.05))
        razon = (zs ** 2) / np.maximum(lrs, 1e-9)
        resultados[(et, cual)] = (p_z2, p_lr, float(np.median(razon)))
        print(f"\n{et:14} | {cual}   n={len(zs)}")
        print(f"   z>2 marca:        {100*p_z2:5.1f}%")
        print(f"   z>3 marca:        {100*np.mean(zs>3.0):5.1f}%")
        print(f"   LR p<0.05 marca:  {100*p_lr:5.1f}%")
        print(f"   razon z^2/LR:     mediana {np.median(razon):.3f}"
              f"  [p10 {np.percentile(razon,10):.3f},"
              f" p90 {np.percentile(razon,90):.3f}]")

print("\n" + "=" * 70)
# A. sin ARMA el residuo ES el contraste
_, _, r_sin = resultados[("sin ARMA", "POTENCIA")]
if not (0.9 <= r_sin <= 1.1):
    print(f"INESPERADO: sin ARMA z^2/LR = {r_sin:.3f}, deberia ser ~1")
    FALLOS.append("la equivalencia sin ARMA no se sostiene")
else:
    print(f"OK  sin ARMA: z^2/LR = {r_sin:.3f} — el vecino ES el contraste")

# B. con ARMA se pierde potencia
pz, plr, r_ar = resultados[("AR(1) phi=0.6", "POTENCIA")]
print(f"    con ARMA: z>2 potencia {100*pz:.1f}%  vs  LR {100*plr:.1f}%"
      f"   (z^2/LR = {r_ar:.3f})")
if plr - pz > 0.10:
    print(f"FALLA: mirar UN residuo pierde {100*(plr-pz):.0f} puntos de potencia")
    print("       frente al LR, que la escalera ya tiene estimado.")
    FALLOS.append("perdida de potencia con ARMA")

if FALLOS:
    sys.exit(1)
print("OK: el veredicto usa el estadistico adecuado en los dos casos.")
