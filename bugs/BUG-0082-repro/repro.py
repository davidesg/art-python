"""BUG-0082 — la suite deja PNG en blanco en el temporal COMPARTIDO.

BUG-0078 puso la guarda para no ABRIR ventana bajo pytest, pero el fichero se
sigue escribiendo, y se escribe en `tempfile.gettempdir()`. Resultado: /tmp
acumula PNG en blanco con nombres `art_*.png`, indistinguibles de salida real.
Un analista que abra uno concluye que ART renderiza en blanco.
"""
import glob, os, tempfile, sys, subprocess

TMP = tempfile.gettempdir()
patron = os.path.join(TMP, "art_*.png")

antes = set(glob.glob(patron))
r = subprocess.run([sys.executable, "-m", "pytest", "-q",
                    "tests/test_bug_0078_show_fig.py"],
                   capture_output=True, text=True)
print(r.stdout.strip().split("\n")[-1] if r.stdout else r.stderr[-200:])
despues = set(glob.glob(patron))

nuevos = sorted(despues - antes)
print(f"\nficheros art_*.png nuevos en {TMP}: {len(nuevos)}")
blancos = [f for f in nuevos if os.path.getsize(f) < 2000]
for f in nuevos[:8]:
    print(f"  {os.path.getsize(f):6d} bytes  {os.path.basename(f)}")

print(f"\nde ellos, en blanco (<2 KB): {len(blancos)}")
print("Escritos en el temporal COMPARTIDO, no en un tmp_path de pytest.")
if nuevos:
    sys.exit(1)
