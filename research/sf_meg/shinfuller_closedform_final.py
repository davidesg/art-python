import numpy as np
# derived pooled functional A = [Xi - sqrt(Xi^2+4 Gamma)]/(2 Gamma)
def funcA_pooled(reps,m=4000,seed=7):
    rng=np.random.default_rng(seed); out=np.empty(reps)
    for i in range(reps):
        W=np.cumsum(rng.standard_normal((2,m)),axis=1)/np.sqrt(m)
        G=(W**2).mean(axis=1); xi=0.5*(W[:,-1]**2-1.0)
        Gam=G.sum(); Xi=xi.sum()
        out[i]=(Xi-np.sqrt(Xi*Xi+4*Gam))/(2*Gam)
    return out
# also single-subseries variants to settle the factor
def funcA_single(form,reps,m=4000,seed=3):
    rng=np.random.default_rng(seed); out=np.empty(reps)
    for i in range(reps):
        W=np.cumsum(rng.standard_normal(m))/np.sqrt(m)
        G=(W**2).mean(); xi=0.5*(W[-1]**2-1.0)
        if form=="SF":      out[i]=(xi-np.sqrt(xi*xi+G/2))/G          # eq 2.4
        elif form=="mine":  out[i]=(xi-np.sqrt(xi*xi+2*G))/(2*G)     # my single derivation
    return out
P=funcA_pooled(30000); q=np.quantile(P,[.1,.5,.9])
print(f"POOLED derived  A=[Xi-sqrt(Xi^2+4G)]/(2G): median={np.median(P):.3f}  q10/50/90={q.round(3)}")
print("   target (sim zero-mean complex n=3000): median=-1.243  q10/50/90=[-3.763 -1.243 -0.437]")
for form in ("SF","mine"):
    S=funcA_single(form,30000); q=np.quantile(S,[.1,.5,.9])
    print(f"single {form:4s}: median={np.median(S):.3f}  q10/50/90={q.round(3)}")
print("   target (sim zero-mean AR(1)): ~ -1.3..-1.5 (drifts)")
