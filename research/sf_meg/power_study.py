import numpy as np, warnings
warnings.filterwarnings("ignore")
from scipy.linalg import cholesky_banded, cho_solve_banded
from scipy.optimize import minimize_scalar
S=12; f=3; w=2*np.pi*f/S
def neg2ll(x,c1,c2):
    n=x.size; g0=1+c1*c1+c2*c2; g1=c1+c1*c2; g2=c2
    ab=np.zeros((3,n)); ab[0,2:]=g2; ab[1,1:]=g1; ab[2,:]=g0
    cb=cholesky_banded(ab,lower=False); return 2*np.log(cb[-1,:]).sum()+n*np.log((x@cho_solve_banded((cb,False),x))/n)
def lr(x):
    o=lambda r: neg2ll(x,-2*np.cos(w)*r,r*r); Lc=o(1.0)
    r=minimize_scalar(o,bounds=(0.02,0.99999),method='bounded',options={'xatol':1e-6}); return max(0.0,Lc-r.fun)
def gen(r,n,rng):  # invertible MA_f with modulus r: x = a_t -2cos(w) r a_{t-1} + r^2 a_{t-2}
    a=rng.standard_normal(n+2); return a[2:]-2*np.cos(w)*r*a[1:-1]+r*r*a[:-2]
for n,reps in ((120,4000),(240,4000)):
    rng=np.random.default_rng(7)
    null=np.array([lr(gen(1.0,n,rng)) for _ in range(reps)])
    c05=np.quantile(null,0.95); c10=np.quantile(null,0.90)
    print(f"n={n}  c.10={c10:.3f}  c.05={c05:.3f}")
    print(f"   {'r':>5} {'pow@10%':>9} {'pow@5%':>9}")
    for r in (1.0,0.95,0.90,0.85,0.80,0.70,0.50):
        rng=np.random.default_rng(100)
        v=np.array([lr(gen(r,n,rng)) for _ in range(reps)])
        print(f"   {r:>5} {np.mean(v>c10):>9.3f} {np.mean(v>c05):>9.3f}")
