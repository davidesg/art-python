"""BUG-0248: five texts that do not apply to the model just estimated.
Buffalo (flour_prices.csv, the lutkepohl_poskitt example of sima), ln, d=1:
m01 = (0,1,0), m02 = (1,1,1); m03 = m01 + step x2 in 12/1973.

    python3 bugs/BUG-0248-repro/repro.py      # exits 1 while any is present
"""
import os, sys, tempfile
from art import mcp_server as M
fn = lambda t: getattr(t, "fn", t)
txt = lambda o: "\n".join(c if isinstance(c, str) else getattr(c, "text", "")
                          for c in (o if isinstance(o, list) else [o]))
HERE = os.path.dirname(os.path.abspath(__file__))
spec = dict(lam=0.0, d=1, D=0, n_harmonics=0, seasonal=False, estimate_mu=False)
with tempfile.TemporaryDirectory() as tmp:
    inp = os.path.join(tmp, "Buffalo.inp")
    fn(M.load_data)(os.path.join(HERE, "flour_prices.csv"), inp, column="Buffalo")
    m01 = txt(fn(M.confirm_and_estimate)(inp, os.path.join(tmp, "m01.inp"), p=0, q=0, **spec))
    m02 = txt(fn(M.confirm_and_estimate)(inp, os.path.join(tmp, "m02.inp"), p=1, q=1, **spec))
    ft = txt(fn(M.formal_tests)(os.path.join(tmp, "m01.pre"), run_meg=False))
    iv = txt(fn(M.guided_intervention)(os.path.join(tmp, "m01.pre"), date="12/1973", form="step",
                                       n_omega=2, output_path=os.path.join(tmp, "m03.inp")))
found = {
    "1 m02 (ARMA(1,1)): nota «AR(2) con raíces complejas»": "AR(2) con raíces complejas" in m02,
    "2 m01 (WN elegido): escaneo «procede a la identificación ARMA»": "procede a la identificación ARMA" in m01,
    "3 formal_tests m01 (0 parámetros): aviso «desviaciones típicas NO son fiables»": "NO son fiables" in ft,
    "4 formal_tests m01 (sin AR): «Este candidato lleva el AR del modelo»": "lleva el AR del modelo" in ft,
    "5 intervención sobre m01 (sin ARMA): «este modelo lleva ARMA»": "este modelo lleva ARMA" in iv,
}
for k, v in found.items():
    print(f"{k}: {v}")
sys.exit(1 if any(found.values()) else 0)
