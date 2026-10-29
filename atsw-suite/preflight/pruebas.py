"""Pruebas de la instalación de atsw en un entorno limpio, antes del tag.

1. Procedencia: cada paquete se importa del entorno (no de otra instalación)
   con la versión de publicación, y las cotas de atsw se cumplen.
2. Motores: fue y drvarma cargan su motor C (el que trae la rueda), y drvec
   encuentra su C (drvec/_bin) y corre un bootstrap pequeño con él. En Alpine
   (musllinux) drvec no tiene rueda binaria: va la pura, y su C no se pide.
3. Asistentes: los tres servidores arrancan y los comandos responden.
4. Funcionamiento: art estima, mtram estima una transferencia, sima reproduce
   el VAR(1) restringido de Lütkepohl y Poskitt (logL -669.129921) por las
   dos rutas, y el VEC de r = 1 del E1 de Lütkepohl (logL 750.524709), con el
   rango del bootstrap que el ejemplo trae en caché.

    python pruebas.py DATA_DIR WHEELS_DIR   # sale con 1 si algo falla

Las versiones esperadas son las de las ruedas de WHEELS_DIR: lo construido es
lo que tiene que quedar instalado. Con origen PyPI, WHEELS_DIR tiene las ruedas
que `pip download` elige para esta plataforma (la última de cada paquete).
"""
import asyncio, importlib, json, os, shutil, subprocess, sys, sysconfig, tempfile, warnings
warnings.filterwarnings("ignore")
os.environ.setdefault("ART_NO_VIEWER", "1")
os.environ.setdefault("MPLBACKEND", "Agg")
DATA = os.path.abspath(sys.argv[1])
WHEELS = os.path.abspath(sys.argv[2])
fallos = []


def check(nombre, ok, detalle=""):
    print(f"  [{'OK' if ok else 'FALLA'}] {nombre}" + (f" — {detalle}" if detalle else ""))
    if not ok:
        fallos.append(nombre)


fn = lambda t: getattr(t, "fn", t)
txt = lambda o: "\n".join(c if isinstance(c, str) else getattr(c, "text", "")
                          for c in (o if isinstance(o, list) else [o]))

print("1. Procedencia y versiones")
from importlib.metadata import version, requires
from packaging.requirements import Requirement
site = os.path.realpath(sysconfig.get_paths()["purelib"])
plat = os.path.realpath(sysconfig.get_paths()["platlib"])
# la versión de cada paquete, del nombre de su rueda (art_tseries-0.2.3-...)
esperado = {}
for w in os.listdir(WHEELS):
    if w.endswith(".whl"):
        dist, v = w.split("-")[:2]
        esperado[dist.replace("_", "-").lower()] = v
for dist in ("fue", "pyfug", "drvarma", "drvec", "art-tseries", "drtran", "sima-tseries", "atsw"):
    check(f"rueda de {dist} construida", dist in esperado)
modulo = {"fue": "fue", "pyfug": "pyfug", "drvarma": "drvarma", "drvec": "drvec", "art-tseries": "art",
          "drtran": "drtran", "sima-tseries": "sima"}
for dist, v in sorted(esperado.items()):
    check(f"{dist} {v}", version(dist) == v, f"instalado {version(dist)}")
    if dist in modulo:
        f = os.path.realpath(importlib.import_module(modulo[dist]).__file__)
        check(f"{modulo[dist]} desde el entorno", f.startswith((site, plat)), f)
for spec in requires("atsw") or []:
    r = Requirement(spec)
    check(f"cota {r}", r.specifier.contains(version(r.name), prereleases=True))

print("2. Motores compilados")
import fue._engine as FE, drvarma._engine as DE
check("fue: motor C", FE.engine_backend() == "c", f"{FE.engine_backend()} {FE.engine_load_error() or ''}")
check("drvarma: motor C", DE.engine_backend() == "c", f"{DE.engine_backend()} {DE.engine_load_error() or ''}")
# drvec: su C no es una extensión sino un ejecutable dentro del paquete
# (drvec/_bin), y sólo lo usan los bootstraps; Alpine lleva la rueda pura
ALPINE = os.path.exists("/etc/alpine-release")
from drvec import c_engine as VE
if not ALPINE:
    try:
        b = VE.find()
        check("drvec: su C, el de la rueda", b.source == "bundled" and b.version == VE.C_VERSION,
              f"{b.source} {b.version} {b.path}")
    except VE.CEngineUnavailable as e:
        check("drvec: su C, el de la rueda", False, str(e)[:90])
# la rueda instalada: la de esta plataforma, no la pura ni una compilada en sitio
from importlib.metadata import distribution
for dist in ("fue", "drvarma") + (() if ALPINE else ("drvec",)):
    w = distribution(dist).read_text("WHEEL") or ""
    tags = [l.split(":", 1)[1].strip() for l in w.splitlines() if l.startswith("Tag:")]
    pura = "Root-Is-Purelib: true" in w
    check(f"{dist}: rueda binaria", tags and not pura and "none-any" not in tags[0], ", ".join(tags))

print("3. Asistentes")
for mod, minimo in (("art.mcp_server", 30), ("drtran.mcp_server", 10), ("sima.mcp_server", 20)):
    n = len(asyncio.run(importlib.import_module(mod).mcp.list_tools()))
    check(f"{mod}: {n} herramientas", n >= minimo)
# los comandos del ENTORNO, no los que haya en el PATH (otra instalación)
scripts = sysconfig.get_paths()["scripts"]
for cmd, dist in ((["art-mcp", "--version"], "art-tseries"), (["mtram", "--version"], "drtran"),
                  (["sima", "--version"], "sima-tseries"), (["atsw-mcp", "--help"], None)):
    exe = shutil.which(cmd[0], path=scripts)
    try:
        p = subprocess.run([exe, cmd[1]], capture_output=True, text=True, timeout=120)
        sal = (p.stdout or p.stderr).strip()
        ok = p.returncode == 0 and (dist is None or version(dist) in sal)
        check(" ".join(cmd), ok, sal.splitlines()[0][:70] if sal else f"rc={p.returncode}")
    except Exception as e:                                   # noqa: BLE001
        check(" ".join(cmd), False, f"{exe}: {e}"[:90])

print("4. Funcionamiento")
tmp = tempfile.mkdtemp()
from art import mcp_server as A
csv = shutil.copy(os.path.join(DATA, "flour_prices.csv"), tmp)
spec = dict(lam=0.0, d=1, D=0, n_harmonics=0, seasonal=False, estimate_mu=False)
pres = {}
for nm in ("Buffalo", "Minneapolis", "KansasCity"):
    inp = os.path.join(tmp, f"{nm}.inp")
    fn(A.load_data)(csv, inp, column=nm)
    p, q = (0, 0) if nm == "Buffalo" else (1, 0)
    fn(A.confirm_and_estimate)(inp, os.path.join(tmp, f"{nm}_m.inp"), p=p, q=q, **spec)
    pres[nm] = os.path.join(tmp, f"{nm}_m.pre")
    check(f"art estima {nm}", os.path.exists(pres[nm]))
import fue
phi = fue.load(pres["Minneapolis"])[1].ar[0][0]
check("art: AR(1) de Minneapolis", abs(phi - 0.2289) < 2e-3, f"φ = {phi:.4f}")

from drtran import mcp_server as T
out = fn(T.load_pre)("t", f"{pres['KansasCity']},{pres['Buffalo']}")
check("mtram load_pre", "Error" not in out[:200], out.splitlines()[0][:70] if out else "")
fn(T.set_network)("t", json.dumps([{"out": 0, "inp": 1, "b": 0, "r": 0, "s": 0}]))
est = fn(T.estimate)("t")
check("mtram estimate", "log" in est.lower() and "Error" not in est[:200], "")

from sima import mcp_server as M
Z = ("phi_KansasCity[B^1], AR1[Buffalo<-KansasCity], "
     "AR1[Minneapolis<-KansasCity], AR1[KansasCity<-Buffalo]")
fn(M.load_pre)("u", json.dumps([os.path.join(DATA, f) for f in
                                ("Buffalo_rw.pre", "Minneapolis_ar1.pre", "KansasCity_ar1.pre")]))
check("sima ruta U: puerta", "GATE: PASSED" in fn(M.run_gate)("u"))
e = fn(M.estimate)("u", indices="1, 1, 1", zeros=Z + ", " + ", ".join(
    [f"theta_{a}[B^1]" for a in ("Buffalo", "Minneapolis", "KansasCity")]
    + [f"MA1[{a}<-{b}]" for a in ("Buffalo", "Minneapolis", "KansasCity")
       for b in ("Buffalo", "Minneapolis", "KansasCity") if a != b]))
check("sima ruta U, forma echelon: VAR(1) de L&P", "exact log-likelihood -669.1299" in e,
      next((l for l in e.splitlines() if "exact log-likelihood" in l), "")[:60])
t = fn(M.load_example)("lutkepohl_poskitt", session="v", dest=os.path.join(tmp, "lp"))
check("sima load_example", 'characterize("v")' in t)
fn(M.characterize)("v")
fn(M.write_specs)("v")
check("sima ruta V: puerta", "GATE: PASSED" in fn(M.run_gate)("v"))
e = fn(M.estimate)("v", 1, 0, zeros=Z)
check("sima ruta V: VAR(1) de L&P", "exact log-likelihood -669.1299" in e,
      next((l for l in e.splitlines() if "exact log-likelihood" in l), "")[:60])
ev = fn(M.evaluate)("v", 1, 0, estwin=72, horizon=6, zeros=Z)
check("sima evaluate (N5) nombra la vara", "the yardstick is" in ev)

# el VEC (drvec): N1c, el rango (el ejemplo trae en caché el bootstrap de
# B = 499, el job de 30 s que no cabe aquí) y el VEC de r = 1
e1 = os.path.join(tmp, "e1")
t = fn(M.load_example)("lutkepohl_e1", session="c", dest=e1)
check("sima load_example (VEC)", "prepare_vec" in t)
check("sima VEC: puerta", "GATE: PASSED" in fn(M.run_gate)("c"))
fn(M.canonical_analysis)("c")
fn(M.prepare_vec)("c", purpose="long run", p=2, case="2")
rk = fn(M.rank_test)("c", B=499)
from sima.provenance import platform_tier
if platform_tier() == "exact":
    check("sima VEC: el rango del E1 (caché)", "Proposed r-hat, read from the bootstrap's critical values: 1" in rk,
          next((l.strip() for l in rk.splitlines() if l.strip().startswith("r=0")), "")[:70])
    ve = fn(M.estimate_vec)("c", r=1)
else:
    # la clave de la caché lleva el nivel de plataforma: fuera de linux-x86_64
    # no casa y el rango es un job nuevo. Se comprueba que arranca, se cancela
    # y el VEC de r = 1 se estima sobre teoría
    import re
    jid = re.search(r"job id: `([0-9a-f]{16})`", rk)
    check("sima VEC: el rango del E1 (job; la caché es de linux-x86_64)", jid is not None,
          jid.group(1) if jid else rk.splitlines()[0][:70])
    if jid:
        fn(M.job_cancel)(jid.group(1))
    ve = fn(M.estimate_vec)("c", r=1, theory="preflight: la caché del rango es de linux-x86_64")
check("sima VEC de r = 1 del E1", "logL 750.5247" in ve,
      next((l for l in ve.splitlines() if "logL" in l), "")[:70])
if not ALPINE:
    # un bootstrap del rango de verdad, por el C de la rueda
    import drvec
    e1pre = [os.path.join(e1, "art", f"e1{s}.pre") for s in ("invest", "income", "cons")]
    rt = drvec.rank_test(e1pre, 2, 0, case=2, bootstrap=10, engine="c",
                         folder=os.path.join(tmp, "e1boot"))
    pv = rt.provenance
    check("drvec: bootstrap por su C", pv.engine == "c" and pv.extra.get("source") == "bundled"
          and all(len(bs.reps) == 10 for bs in rt.bootstraps),
          f"{pv.engine} {pv.extra.get('source')} {pv.extra.get('elapsed', 0):.1f} s")

print()
print("TODO BIEN" if not fallos else f"FALLAN {len(fallos)}: " + "; ".join(fallos))
sys.exit(1 if fallos else 0)
