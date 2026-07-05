import numpy as np, warnings
warnings.filterwarnings("ignore")
from scipy.optimize import minimize_scalar
# Seasonal AR_f Shin-Fuller: AR(2) complex unit root, phi1=2cos(w)rho, phi2=-rho^2.
# Exact unconditional ML (zero/sample-mean), Phi_1u with truncation rho_hat<=1-4/n.
def g(rho, y, cw):
    if rho<=0 or rho>=1: return np.inf
    phi1=2*cw*rho; phi2=-rho*rho
    den=(1+phi2)*((1-phi2)**2-phi1**2)
    if den<=0: return np.inf
    v0=(1-phi2)/den; v1=v0*phi1/(1-phi2)
    detM=v0*v0-v1*v1
    if detM<=0: return np.inf
    z=y-y.mean(); n=z.size
    # initial 2x2 quad form
    z1,z2=z[0],z[1]
    qf0=(v0*(z1*z1+z2*z2)-2*v1*z1*z2)/detM
    pred=z[2:]-phi1*z[1:-1]-phi2*z[:-2]
    QF=qf0+np.sum(pred*pred)
    return n*np.log(QF)+np.log(detM)
def phi1u(y,cw,n):
    res=minimize_scalar(lambda r: g(r,y,cw),bounds=(0.02,0.999999),method="bounded",options={"xatol":1e-8})
    rho_hat=res.x; rho_m=1-4.0/n
    if rho_hat>rho_m: return 0.0
    return 0.5*(g(rho_m,y,cw)-res.fun)
def gen(n,cw,rng):  # H0: complex seasonal unit root, rho=1, with burn-in
    nb=40; e=rng.standard_normal(n+nb); y=np.zeros(n+nb)
    for t in range(2,n+nb): y[t]=2*cw*y[t-1]-y[t-2]+e[t]
    return y[nb:]
for f,reps in ((3,6000),):
    w=2*np.pi*f/12; cw=np.cos(w)
    for n in (100,250):
        rng=np.random.default_rng(5)
        v=np.array([phi1u(gen(n,cw,rng),cw,n) for _ in range(reps)])
        q=np.quantile(v,[.90,.95,.99])
        print(f"AR_f f={f} (w={w:.3f})  n={n}: P(Phi=0)={np.mean(v<1e-9):.3f}  10/5/1% = {q[0]:.3f} {q[1]:.3f} {q[2]:.3f}")
print("AR(1) Shin-Fuller ref: pile-up 0.55 | 1.07/1.75/3.41")

# Diagnostic: distribution of n(rho_hat - 1) for the complex case (no truncation)
print("\n--- n(rho_hat-1) distribution (complex f=3, no truncation) ---")
for n in (100,250):
    w=2*np.pi*3/12; cw=np.cos(w); rng=np.random.default_rng(9)
    rh=[]
    for _ in range(5000):
        y=gen(n,cw,rng)
        res=minimize_scalar(lambda r: g(r,y,cw),bounds=(0.02,0.999999),method="bounded",options={"xatol":1e-8})
        rh.append(n*(res.x-1))
    rh=np.array(rh)
    print(f"n={n}: n(rho_hat-1) median={np.median(rh):.2f}  mean={rh.mean():.2f}  q10/50/90={np.quantile(rh,[.1,.5,.9]).round(2)}  (AR(1): median ~ -4)")
