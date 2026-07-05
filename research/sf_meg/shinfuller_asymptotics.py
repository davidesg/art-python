import numpy as np, warnings, time
warnings.filterwarnings("ignore")
from scipy.optimize import minimize_scalar
from scipy.signal import lfilter
def Bform(a,b,phi1,phi2,Minv):
    init=Minv[0,0]*a[0]*b[0]+Minv[0,1]*(a[0]*b[1]+a[1]*b[0])+Minv[1,1]*a[1]*b[1]
    fa=a[2:]-phi1*a[1:-1]-phi2*a[:-2]; fb=b[2:]-phi1*b[1:-1]-phi2*b[:-2]
    return init+np.sum(fa*fb)
def g_cplx(rho,y,cw):
    if rho<=0 or rho>=1: return np.inf
    phi1=2*cw*rho; phi2=-rho*rho
    den=(1+phi2)*((1-phi2)**2-phi1**2)
    if den<=0: return np.inf
    v0=(1-phi2)/den; v1=v0*phi1/(1-phi2); detM=v0*v0-v1*v1
    if detM<=0: return np.inf
    Minv=np.array([[v0,-v1],[-v1,v0]])/detM
    one=np.ones_like(y)
    mu=Bform(one,y,phi1,phi2,Minv)/Bform(one,one,phi1,phi2,Minv)
    z=y-mu
    return y.size*np.log(Bform(z,z,phi1,phi2,Minv))+np.log(detM)
def rh(y,cw):
    return minimize_scalar(lambda r:g_cplx(r,y,cw),bounds=(0.02,0.999999),method="bounded",options={"xatol":1e-8}).x
def gen(n,cw,rng,nb=80):
    e=rng.standard_normal(n+nb)
    y=lfilter([1.0],[1.0,-2*cw,1.0],e)   # AR(2) rho=1
    return y[nb:]
def med(f,n,reps,seed=9):
    cw=np.cos(2*np.pi*f/12); rng=np.random.default_rng(seed)
    return np.median([n*(rh(gen(n,cw,rng),cw)-1) for _ in range(reps)])
t0=time.time()
print("f=3 n(rho_hat-1) median vs n (test 1/sqrt(n) convergence to L):")
ns=[100,250,500,1000,2000,4000]; reps=[6000,5000,4000,3000,2000,1200]
ms=[]
for n,r in zip(ns,reps):
    m=med(3,n,r); ms.append(m); print(f"  n={n:>4}: {m:.3f}")
# fit L + c/sqrt(n)
A=np.column_stack([np.ones(len(ns)),1/np.sqrt(ns)]); L,c=np.linalg.lstsq(A,ms,rcond=None)[0]
print(f"  fit L + c/sqrt(n):  L={L:.3f}  c={c:.2f}")
print("frequency invariance (median at n=1000):")
for f in (1,2,3,4,5): print(f"  f={f}: {med(f,1000,2500):.3f}")
print(f"[{time.time()-t0:.0f}s]")
