import numpy as np, warnings
warnings.filterwarnings("ignore")
from scipy.optimize import minimize_scalar

# ---- AR(1) mean-estimated (validated) ----
def gls_mu_ar1(rho,y):
    u=y[1:]-rho*y[:-1]; n=u.size
    return ((1-rho)*u.sum()+(1-rho*rho)*y[0])/((1-rho)**2*n+(1-rho*rho))
def g_ar1(rho,y):
    if abs(rho)>=1: return np.inf
    mu=gls_mu_ar1(rho,y); z=y-mu; N=y.size
    Qu=np.sum((z[1:]-rho*z[:-1])**2)+(1-rho*rho)*z[0]**2
    return N*np.log(Qu)-np.log(1-rho*rho)
def rh_ar1(y):
    return minimize_scalar(lambda r:g_ar1(r,y),bounds=(-0.99,0.999999),method="bounded",options={"xatol":1e-8}).x
def gen_ar1(n,rng,nb=60):
    a=rng.standard_normal(n+nb); return np.cumsum(a)[nb:]   # y_0..y_{n-1}? length n

# ---- complex AR_f mean-estimated (GLS) ----
def Bform(a,b,phi1,phi2,Minv):
    # a'Omega^-1 b  via prediction-error decomposition
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
    z=y-mu; N=y.size
    return N*np.log(Bform(z,z,phi1,phi2,Minv))+np.log(detM)
def rh_cplx(y,cw):
    return minimize_scalar(lambda r:g_cplx(r,y,cw),bounds=(0.02,0.999999),method="bounded",options={"xatol":1e-8}).x
def gen_cplx(n,cw,rng,nb=60):
    e=rng.standard_normal(n+nb); y=np.zeros(n+nb)
    for t in range(2,n+nb): y[t]=2*cw*y[t-1]-y[t-2]+e[t]
    return y[nb:]

cw=np.cos(np.pi/2)
print("MEAN-ESTIMATED, n(rho_hat-1) median:")
print(f"{'n':>5} {'AR(1)':>10} {'complex f=3':>12}")
for n in (100,250,500,1000):
    rng=np.random.default_rng(9)
    a=np.array([n*(rh_ar1(gen_ar1(n,rng))-1) for _ in range(4000)])
    rng=np.random.default_rng(9)
    c=np.array([n*(rh_cplx(gen_cplx(n,cw,rng),cw)-1) for _ in range(4000)])
    print(f"{n:>5} {np.median(a):>10.2f} {np.median(c):>12.2f}")

print("\nComplex AR_f f=3 Phi_1u with RECALIBRATED truncation (rho_m=median(rho_hat)):")
print(f"{'n':>5} {'pile-up':>8} {'10%':>7} {'5%':>7} {'1%':>7}   [AR(1) Table II: 1.07/1.75/3.41]")
for n in (100,250):
    rng=np.random.default_rng(21); reps=6000
    ys=[gen_cplx(n,cw,rng) for _ in range(reps)]
    rhos=np.array([rh_cplx(y,cw) for y in ys])
    rho_m=np.median(rhos)
    phis=[]
    for y,rho in zip(ys,rhos):
        if rho>rho_m: phis.append(0.0)
        else: phis.append(0.5*(g_cplx(rho_m,y,cw)-g_cplx(rho,y,cw)))
    phis=np.array(phis); q=np.quantile(phis,[.9,.95,.99])
    print(f"{n:>5} {np.mean(phis<1e-9):>8.3f} {q[0]:>7.3f} {q[1]:>7.3f} {q[2]:>7.3f}   rho_m={rho_m:.4f}")
