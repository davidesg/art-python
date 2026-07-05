import numpy as np, warnings
warnings.filterwarnings("ignore")
from scipy.optimize import minimize_scalar
# Shin-Fuller (2001) Phi_1u, MEAN-estimated AR(1), exact unconditional ML.
# Data Y=(y_0,...,y_n), N=n+1. z_t=y_t-mu, z_t=rho z_{t-1}+e_t.
# Q_u(rho,mu)=sum_{t=1}^n ((y_t-mu)-rho(y_{t-1}-mu))^2 + (1-rho^2)(y_0-mu)^2
# g(rho)= (N)*log(Q_u(mu_hat))  - log(1-rho^2) ;  L=-g/2 ; Phi=L(rho_hat)-L(1-4/n) if rho_hat<=1-4/n else 0
def gls_mu(rho,y):
    u=y[1:]-rho*y[:-1]; n=u.size
    num=(1-rho)*u.sum() + (1-rho*rho)*y[0]
    den=(1-rho)**2*n + (1-rho*rho)
    return num/den
def g(rho,y):
    if abs(rho)>=1: return np.inf
    mu=gls_mu(rho,y); z=y-mu; N=y.size
    Qu=np.sum((z[1:]-rho*z[:-1])**2) + (1-rho*rho)*z[0]**2
    return N*np.log(Qu) - np.log(1-rho*rho)
def phi1u(y,n):
    res=minimize_scalar(lambda r: g(r,y),bounds=(-0.999,0.999999),method="bounded",options={"xatol":1e-8})
    rho_hat=res.x
    rho_m=1-4.0/n
    if rho_hat > rho_m: return 0.0
    return 0.5*(g(rho_m,y) - res.fun)   # = L(rho_hat)-L(rho_m)
def gen_rw(n,rng):       # y_0..y_n with 20-step burn-in, rho=1
    a=rng.standard_normal(n+1+20); y=np.cumsum(a); return y[20:]
for n,reps in ((100,8000),(250,6000),(500,5000)):
    rng=np.random.default_rng(11)
    v=np.array([phi1u(gen_rw(n,rng),n) for _ in range(reps)])
    q=np.quantile(v,[.90,.95,.99]); atom=np.mean(v<1e-9)
    print(f"n={n:>3}  P(Phi=0)={atom:.3f}  10/5/1% = {q[0]:.3f} {q[1]:.3f} {q[2]:.3f}")
print("Shin-Fuller Table II: n=100 -> 1.07/1.75/3.41 ; n=250 -> 1.07/1.76/3.44 ; n=500 -> 1.08/1.77/3.46")
