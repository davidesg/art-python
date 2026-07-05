import numpy as np
from deterministic_effect import simulate
import sys
n=int(sys.argv[1]); reps=int(sys.argv[2])
allc=[]
for f in (1,2,3,4,5):
    lr=simulate(f,"full",n,reps,seed=500+f)
    allc.append(lr)
np.savez(f"out/det_n{n}.npz", **{f"lr_f{f}":allc[i] for i,f in enumerate((1,2,3,4,5))})
lr=np.concatenate(allc); q=np.quantile(lr,[.9,.95,.99])
print(f"det full pooled f1-5  n={n} reps={reps}: pileup {np.mean(lr<1e-6):.3f}  10/5/1% {q.round(3)}",flush=True)
