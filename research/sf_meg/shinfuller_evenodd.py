import numpy as np, warnings
warnings.filterwarnings("ignore")
from scipy.optimize import minimize_scalar
from scipy.signal import lfilter

# complex AR(2) f=3 (phi1=0, phi2=-rho^2), zero-mean unconditional -2logL
def g_cplx(rho,y):
    if rho<=0 or rho>=1: return np.inf
    phi2=-rho*rho; v0=1.0/(1-phi2*phi2)   # for phi1=0: v0=1/(1-phi2^2), v1=0
    z=y; N=y.size
    qf0=(z[0]**2+z[1]**2)/v0
    pred=z[2:]-phi2*z[:-2]                 # y_t - phi2 y_{t-2}, phi1=0
    return N*np.log(qf0+np.sum(pred*pred))+np.log(v0*v0)

# pooled two AR(1) (the (-1)^k-flipped even/odd subseries), shared beta=rho^2, zero-mean uncond ML
def g_ar1_sub(beta,s):   # -2logL contribution (NOT +const) for one AR(1) subseries
    m=s.size
    Qu=(1-beta*beta)*s[0]**2+np.sum((s[1:]-beta*s[:-1])**2)
    return m*np.log(Qu)-np.log(1-beta*beta)   # note: returns m*log(Qu); pooling needs care
def g_pooled(rho,e_sub,o_sub):
    beta=rho*rho
    if beta>=1: return np.inf
    # joint: concentrate ONE sigma^2 across both subseries
    def parts(beta,s):
        m=s.size; Qu=(1-beta*beta)*s[0]**2+np.sum((s[1:]-beta*s[:-1])**2)
        return Qu, -np.log(1-beta*beta), m
    Qe,le,me=parts(beta,e_sub); Qo,lo,mo=parts(beta,o_sub)
    M=me+mo
    return M*np.log((Qe+Qo))+(le+lo)   # joint concentrated, common sigma^2

def rh(gfun,*a):
    return minimize_scalar(lambda r: gfun(r,*a),bounds=(0.02,0.999999),method="bounded",options={"xatol":1e-9}).x
def gen(n,rng,nb=80):
    e=rng.standard_normal(n+nb); y=lfilter([1.0],[1.0,0.0,1.0],e); return y[nb:]  # phi1=0,phi2=-1 -> a=[1,0,1]

rng=np.random.default_rng(3); n=200
diffs=[]
for _ in range(300):
    y=gen(n,rng)
    r_ar2=rh(g_cplx,y)
    ev=((-1.0)**np.arange(y[0::2].size))*y[0::2]   # (-1)^k flip
    od=((-1.0)**np.arange(y[1::2].size))*y[1::2]
    r_pool=rh(g_pooled,ev,od)
    diffs.append(abs(r_ar2-r_pool))
print(f"even/odd reduction check (n={n}, 300 draws): max |rho_AR2 - rho_pooled| = {max(diffs):.2e}, mean={np.mean(diffs):.2e}")
