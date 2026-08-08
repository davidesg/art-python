"""Aparato teórico completo: Φ̂_f estacional, tabla de c(n) y críticos por frecuencia
y por construcción del determinista (ESCALAR vs correcto = HOMOGÉNEA de dim s).

Frecuencias:
  f=0  raíz real 1−ρB           s=1  determinista = constante   (AR(1) mean-estimated)
  f=1..5 par complejo           s=2  determinista = A cosωt+B sinωt (armónico 2-dim)
  f=6  raíz real 1+ρB (Nyquist) s=1  determinista = (−1)^t alternador

Dos construcciones por frecuencia:
  ESCALAR : resta una media escalar (lo que usa tab:arcrit; mis-especifica en interiores)
  HOMOG.  : resta la solución homogénea del factor (dim = s) — lo correcto

Cada celda: dos pasadas — (1) mediana de ρ̂ → ρ_m=1−c/n (pile-up ½); (2) Φ̂ → críticos 10/5/1%.
Verifica: interiores comparten c (invariancia freq); f=6 homog ≈ AR(1); f=0 = AR(1) Tabla II.
"""
import warnings; warnings.filterwarnings("ignore")
import sys, json, time
import numpy as np
from scipy.optimize import minimize_scalar

REPS = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
NS = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [100, 250]
SEED = 4242
OUT = "/tmp/claude-1000/-home-david-Dropbox-SF-MEG/3834c50f-6fbd-4539-9810-5fbba787c80e/scratchpad/arf_table.json"

# ---------- núcleo AR(2) complejo (validado en shinfuller_meanest) ----------
def Bform(a, b, phi1, phi2, Minv):
    init = Minv[0,0]*a[0]*b[0] + Minv[0,1]*(a[0]*b[1]+a[1]*b[0]) + Minv[1,1]*a[1]*b[1]
    fa = a[2:]-phi1*a[1:-1]-phi2*a[:-2]; fb = b[2:]-phi1*b[1:-1]-phi2*b[:-2]
    return init + np.sum(fa*fb)

def _cplx(rho, cw):
    phi1 = 2*cw*rho; phi2 = -rho*rho
    den = (1+phi2)*((1-phi2)**2-phi1**2)
    if den <= 0: return None
    v0 = (1-phi2)/den; v1 = v0*phi1/(1-phi2); detM = v0*v0-v1*v1
    if detM <= 0: return None
    return phi1, phi2, np.array([[v0,-v1],[-v1,v0]])/detM, detM

def g_cplx(rho, y, cw, X):
    """X: None→escalar(constante); (C,S)→armónico. Verosimilitud unconditional perfilada."""
    if rho <= 0 or rho >= 1: return np.inf
    r = _cplx(rho, cw)
    if r is None: return np.inf
    phi1, phi2, Minv, detM = r
    if X is None:
        one = np.ones_like(y)
        mu = Bform(one, y, phi1, phi2, Minv)/Bform(one, one, phi1, phi2, Minv)
        z = y - mu
    else:
        C, S = X
        Scc=Bform(C,C,phi1,phi2,Minv); Scs=Bform(C,S,phi1,phi2,Minv); Sss=Bform(S,S,phi1,phi2,Minv)
        Scy=Bform(C,y,phi1,phi2,Minv); Ssy=Bform(S,y,phi1,phi2,Minv)
        try: b = np.linalg.solve([[Scc,Scs],[Scs,Sss]], [Scy,Ssy])
        except np.linalg.LinAlgError: return np.inf
        z = y - b[0]*C - b[1]*S
    return y.size*np.log(Bform(z,z,phi1,phi2,Minv)) + np.log(detM)

# ---------- AR(1) real (mean-estimated, validado en shinfuller_ar1) ----------
def g_ar1(rho, y, detr):
    """detr: 'const' resta media GLS; 'none' zero-mean."""
    if abs(rho) >= 1: return np.inf
    if detr == 'const':
        u = y[1:]-rho*y[:-1]
        mu = ((1-rho)*u.sum()+(1-rho*rho)*y[0])/((1-rho)**2*(y.size-1)+(1-rho*rho))
        z = y-mu
    else:
        z = y
    Qu = np.sum((z[1:]-rho*z[:-1])**2)+(1-rho*rho)*z[0]**2
    return y.size*np.log(Qu)-np.log(1-rho*rho)

# ---------- generadores nulos ----------
def gen_cplx(n, cw, rng, nb=60):
    e = rng.standard_normal(n+nb); y = np.zeros(n+nb)
    for t in range(2, n+nb): y[t] = 2*cw*y[t-1]-y[t-2]+e[t]
    return y[nb:]

def gen_rw(n, rng, nb=40):        # (1−B)y=e
    return np.cumsum(rng.standard_normal(n+nb))[nb:]

def gen_nyq(n, rng, nb=40):       # (1+B)y=e  → alternante
    e = rng.standard_normal(n+nb); y = np.zeros(n+nb)
    for t in range(1, n+nb): y[t] = -y[t-1]+e[t]
    return y[nb:]

def rhohat(gf, lo=0.02):
    return minimize_scalar(gf, bounds=(lo, 0.999999), method="bounded", options={"xatol":1e-7}).x

def cell(gfun, ys):
    rs = np.array([rhohat(lambda r: gfun(r, y)) for y in ys])
    rm = np.median(rs)
    ph = np.array([0.0 if rh > rm else 0.5*(gfun(rm, y)-gfun(rh, y)) for y, rh in zip(ys, rs)])
    q = np.quantile(ph, [.90, .95, .99])
    return dict(med_nr=float(np.median(len(ys[0])*(rs-1))), c=float(len(ys[0])*(1-rm)),
                rho_m=float(rm), pileup=float(np.mean(ph<1e-9)),
                q10=float(q[0]), q05=float(q[1]), q01=float(q[2]))

FREQS = [(f, np.cos(2*np.pi*f/12)) for f in range(1, 6)]
results = {}
t0 = time.time()
for n in NS:
    t = np.arange(n)
    results[n] = {}
    # f=0 : AR(1) mean-estimated (ancla Tabla II)
    rng = np.random.default_rng(SEED)
    ys = [gen_rw(n, rng) for _ in range(REPS)]
    results[n]['f0_const'] = cell(lambda r, y: g_ar1(r, y, 'const'), ys)
    # interiores f=1..5, escalar y armónico
    for f, cw in FREQS:
        C = np.cos(2*np.pi*f/12*t); S = np.sin(2*np.pi*f/12*t)
        rng = np.random.default_rng(SEED+f)
        ys = [gen_cplx(n, cw, rng) for _ in range(REPS)]
        results[n][f'f{f}_scalar'] = cell(lambda r, y: g_cplx(r, y, cw, None), ys)
        results[n][f'f{f}_harm']   = cell(lambda r, y: g_cplx(r, y, cw, (C, S)), ys)
    # f=6 Nyquist: escalar y alternador(=AR(1) mean sobre serie con signo cambiado)
    rng = np.random.default_rng(SEED+6)
    ys = [gen_nyq(n, rng) for _ in range(REPS)]
    alt = (-1.0)**t
    results[n]['f6_scalar'] = cell(lambda r, y: g_ar1(r, y*alt, 'none'), ys)  # escalar≈zero-mean tras flip
    results[n]['f6_alt']    = cell(lambda r, y: g_ar1(r, y*alt, 'const'), ys) # alternador = AR(1) mean
    print(f"n={n} hecho ({(time.time()-t0)/60:.1f} min)", flush=True)
    json.dump(results, open(OUT, "w"))

# ---------- impresión ----------
print("\nAR(1) Tabla II (Shin-Fuller):  n=100 1.07/1.75/3.41   n=250 1.07/1.76/3.44")
print("tab:arcrit (escalar):          n=100 0.93/1.47/2.86   n=250 1.00/1.59/3.05")
for n in NS:
    print(f"\n{'='*82}\n n={n}   (REPS={REPS})\n{'='*82}")
    print(f" {'celda':16} {'med n(ρ̂−1)':>11} {'c':>7} {'ρ_m':>8} {'pileup':>7} {'10%':>7} {'5%':>7} {'1%':>7}")
    order = ['f0_const'] + [f'f{f}_{k}' for f in range(1,6) for k in ('scalar','harm')] + ['f6_scalar','f6_alt']
    for key in order:
        r = results[n][key]
        print(f" {key:16} {r['med_nr']:>11.2f} {r['c']:>7.2f} {r['rho_m']:>8.4f} "
              f"{r['pileup']:>7.3f} {r['q10']:>7.3f} {r['q05']:>7.3f} {r['q01']:>7.3f}")
print("\nguardado", OUT)
