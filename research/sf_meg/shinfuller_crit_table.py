import numpy as np, warnings, time
warnings.filterwarnings("ignore")
from scipy.optimize import minimize_scalar
from scipy.signal import lfilter
S=12
def Bform(a,b,phi1,phi2,Minv):
    init=Minv[0,0]*a[0]*b[0]+Minv[0,1]*(a[0]*b[1]+a[1]*b[0])+Minv[1,1]*a[1]*b[1]
    fa=a[2:]-phi1*a[1:-1]-phi2*a[:-2];fb=b[2:]-phi1*b[1:-1]-phi2*b[:-2]
    return init+np.sum(fa*fb)
def g_ar(rho,y,cw):
    if rho<=0 or rho>=1:return np.inf
    phi1=2*cw*rho;phi2=-rho*rho
    den=(1+phi2)*((1-phi2)**2-phi1**2)
    if den<=0:return np.inf
    v0=(1-phi2)/den;v1=v0*phi1/(1-phi2);detM=v0*v0-v1*v1
    if detM<=0:return np.inf
    Minv=np.array([[v0,-v1],[-v1,v0]])/detM;one=np.ones_like(y)
    mu=Bform(one,y,phi1,phi2,Minv)/Bform(one,one,phi1,phi2,Minv);z=y-mu
    return y.size*np.log(Bform(z,z,phi1,phi2,Minv))+np.log(detM)
def gen(n,cw,rng,nb=80):
    e=rng.standard_normal(n+nb); return lfilter([1.0],[1.0,-2*cw,1.0],e)[nb:]
def boot_se(v,q,nb=500,seed=0):
    rng=np.random.default_rng(seed);n=v.size;out=np.empty((nb,len(q)))
    for b in range(nb): out[b]=np.quantile(v[rng.integers(0,n,n)],q)
    return out.std(0)
print("Seasonal AR_f Shin-Fuller Phi_1u critical values (complex freqs f1-5 pooled, mean-est)")
print(f"{'n':>5} {'c(n)':>6} {'pileup':>7} {'10%':>12} {'5%':>12} {'1%':>12}")
for n,reps in ((100,2500),(250,2000),(500,1400)):
    rhos=[]; ys=[]
    for f in (1,2,3,4,5):
        cw=np.cos(2*np.pi*f/S); rng=np.random.default_rng(300+f+n)
        for _ in range(reps):
            y=gen(n,cw,rng); r=minimize_scalar(lambda rr:g_ar(rr,y,cw),bounds=(0.02,0.999999),method="bounded",options={"xatol":1e-8}).x
            rhos.append(r); ys.append((y,cw,r))
    rhos=np.array(rhos); rho_m=np.median(rhos); cn=n*(1-rho_m)
    phis=np.array([0.0 if r>rho_m else 0.5*(g_ar(rho_m,y,cw)-g_ar(r,y,cw)) for (y,cw,r) in ys])
    q=np.quantile(phis,[.9,.95,.99]); se=boot_se(phis,[.9,.95,.99])
    print(f"{n:>5} {cn:>6.2f} {np.mean(phis<1e-9):>7.3f} "
          f"{q[0]:>6.2f}({se[0]:.2f}) {q[1]:>6.2f}({se[1]:.2f}) {q[2]:>6.2f}({se[2]:.2f})")
print("AR(1) Shin-Fuller Table II (real root): c=4 | 1.07 / 1.75 / 3.41")
