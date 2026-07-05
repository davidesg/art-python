import numpy as np, warnings
warnings.filterwarnings("ignore")
from scipy.optimize import minimize_scalar
from scipy.signal import lfilter
def g_cplx(rho,y):
    if rho<=0 or rho>=1: return np.inf
    phi2=-rho*rho; v0=1.0/(1-phi2*phi2)
    pred=y[2:]-phi2*y[:-2]
    return y.size*np.log((y[0]**2+y[1]**2)/v0+np.sum(pred*pred))+2*np.log(v0)
def gen(n,rng,nb=80):
    e=rng.standard_normal(n+nb); return lfilter([1.0],[1.0,0.0,1.0],e)[nb:]
# FIXED: generate y once per replication
def sim_zeromean(n,reps,seed=1):
    rng=np.random.default_rng(seed); out=np.empty(reps)
    for i in range(reps):
        y=gen(n,rng)
        out[i]=n*(minimize_scalar(lambda r:g_cplx(r,y),bounds=(0.02,0.999999),method="bounded",options={"xatol":1e-9}).x-1)
    return out
def funcA(c,reps,m=3000,seed=7):
    rng=np.random.default_rng(seed); out=np.empty(reps)
    for i in range(reps):
        W=np.cumsum(rng.standard_normal((2,m)),axis=1)/np.sqrt(m)
        G=(W**2).mean(axis=1); xi=0.5*(W[:,-1]**2-1.0)
        Gs=G.sum(); xis=xi.sum()
        out[i]=(xis-np.sqrt(xis*xis+c*Gs))/Gs
    return out
for n in (1000,3000):
    s=sim_zeromean(n,4000)
    print(f"sim zero-mean complex f=3 n={n}: median={np.median(s):.3f}  q10/50/90={np.quantile(s,[.1,.5,.9]).round(3)}")
print("functional A(c):")
for c in (0.5,1.0,1.5,2.0):
    A=funcA(c,20000); print(f"  c={c}: median={np.median(A):.3f}  q10/50/90={np.quantile(A,[.1,.5,.9]).round(3)}")
