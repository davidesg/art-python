import numpy as np, warnings, time
warnings.filterwarnings("ignore")
from scipy.optimize import minimize_scalar
from scipy.linalg import cholesky_banded, cho_solve_banded
S=12; f=3; w=2*np.pi*f/S; cw=np.cos(w)   # pi/2 -> cw=0
# ----- DCD (MA witness) on u = theta_f(r) a -----
def neg2ll_ma(x,c1,c2):
    n=x.size;g0=1+c1*c1+c2*c2;g1=c1+c1*c2;g2=c2
    ab=np.zeros((3,n));ab[0,2:]=g2;ab[1,1:]=g1;ab[2,:]=g0
    cb=cholesky_banded(ab,lower=False);return 2*np.log(cb[-1,:]).sum()+n*np.log((x@cho_solve_banded((cb,False),x))/n)
def dcd_lr(u):
    o=lambda r:neg2ll_ma(u,-2*cw*r,r*r);Lc=o(1.0)
    return max(0.0,Lc-minimize_scalar(o,bounds=(0.02,0.99999),method="bounded",options={"xatol":1e-6}).fun)
# ----- Shin-Fuller (AR_f, mean-est) on N -----
def Bform(a,b,phi1,phi2,Minv):
    init=Minv[0,0]*a[0]*b[0]+Minv[0,1]*(a[0]*b[1]+a[1]*b[0])+Minv[1,1]*a[1]*b[1]
    fa=a[2:]-phi1*a[1:-1]-phi2*a[:-2];fb=b[2:]-phi1*b[1:-1]-phi2*b[:-2]
    return init+np.sum(fa*fb)
def g_ar(rho,y):
    if rho<=0 or rho>=1:return np.inf
    phi1=2*cw*rho;phi2=-rho*rho
    den=(1+phi2)*((1-phi2)**2-phi1**2)
    if den<=0:return np.inf
    v0=(1-phi2)/den;v1=v0*phi1/(1-phi2);detM=v0*v0-v1*v1
    if detM<=0:return np.inf
    Minv=np.array([[v0,-v1],[-v1,v0]])/detM;one=np.ones_like(y)
    mu=Bform(one,y,phi1,phi2,Minv)/Bform(one,one,phi1,phi2,Minv);z=y-mu
    return y.size*np.log(Bform(z,z,phi1,phi2,Minv))+np.log(detM)
def sf_stat(y,n):
    rho=minimize_scalar(lambda r:g_ar(r,y),bounds=(0.02,0.999999),method="bounded",options={"xatol":1e-8}).x
    rm=1-1.44/n
    return 0.0 if rho>rm else 0.5*(g_ar(rm,y)-g_ar(rho,y))
def gen(r,n,rng,nb=80):
    a=rng.standard_normal(n+nb)
    u=a.copy(); u[2:]=a[2:]-2*cw*r*a[1:-1]+r*r*a[:-2]   # theta_f(r) a
    N=np.zeros(n+nb)
    for t in range(2,n+nb): N[t]=2*cw*N[t-1]-N[t-2]+u[t]   # phi_f^{-1} u (unit root)
    return u[nb:], N[nb:]
n=240; reps=2000; rs=[1.0,0.95,0.9,0.8,0.5,0.0]
DCD={};SF={}
t0=time.time()
for r in rs:
    rng=np.random.default_rng(int(100*r)+7)
    d=[];s=[]
    for _ in range(reps):
        u,N=gen(r,n,rng); d.append(dcd_lr(u)); s.append(sf_stat(N,n))
    DCD[r]=np.array(d);SF[r]=np.array(s)
cD=np.quantile(DCD[1.0],0.95)   # DCD null = r=1 (deterministic)
cS=np.quantile(SF[0.0],0.95)    # SF null  = r=0 (pure seasonal unit root)
print(f"crit: DCD(5%,calib r=1)={cD:.3f}  SF(5%,calib r=0)={cS:.3f}   [{time.time()-t0:.0f}s]")
print(f"{'r':>5} {'nature':>14} {'DCD->stoch':>11} {'SF->det':>9}")
for r in rs:
    nat = 'determinist' if r==1.0 else ('pure unit root' if r==0.0 else 'stochastic')
    print(f"{r:>5} {nat:>14} {np.mean(DCD[r]>cD):>11.3f} {np.mean(SF[r]>cS):>9.3f}")
