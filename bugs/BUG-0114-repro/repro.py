"""BUG-0114 — `version_instrumento` se colgaba para siempre bajo servidor MCP.

Portátil y determinista. El repro original era un volcado de pilas con tres
rutas absolutas de Windows escritas a mano: servía para LOCALIZAR el defecto —y
lo hizo, con `faulthandler` sobre el servidor colgado— pero no corre en ninguna
otra máquina. Éste prueba la propiedad que importa.

EL DEFECTO. `subprocess.run(..., timeout=3)` **no acota**. Es su comportamiento
documentado: al saltar el plazo mata al hijo y vuelve a llamar a `communicate()`
**sin plazo** para vaciar las tuberías. Si el hijo dejó un NIETO vivo con el
extremo de escritura abierto —un ayudante de credenciales, un paginador— esa
segunda espera no termina nunca.

Aquí se pone un `git` falso en el PATH que hace exactamente eso: escupe algo,
deja un nieto agarrado a la tubería y se va. Con el defecto, la llamada no
vuelve; con el arreglo, vuelve dentro del plazo.

    python bugs/BUG-0114-repro/repro.py
"""
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import time

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))

PLAZO = 3.0
MARGEN = 12.0          # generoso: lo que se mide es «vuelve» frente a «nunca»

if os.name == "nt":
    print("SALTADO: el `git` falso usa un guion de shell POSIX.")
    raise SystemExit(0)

d = tempfile.mkdtemp(prefix="bug0114-")
git = os.path.join(d, "git")
with open(git, "w", encoding="utf-8") as fh:
    fh.write(textwrap.dedent("""\
        #!/bin/sh
        # Un NIETO que se queda con el extremo de escritura de la tuberia.
        sleep 600 &
        echo deadbeef
        sleep 600
    """))
os.chmod(git, os.stat(git).st_mode | stat.S_IEXEC)

entorno = {**os.environ, "PATH": d + os.pathsep + os.environ.get("PATH", "")}
guion = textwrap.dedent(f"""
    import sys, time
    sys.path.insert(0, {os.path.join(RAIZ, 'src')!r})
    from art.guion import version_instrumento
    t0 = time.time()
    version_instrumento()
    print(f"VUELVE en {{time.time() - t0:.1f}}s")
""")

t0 = time.time()
try:
    pr = subprocess.run([sys.executable, "-c", guion], env=entorno,
                        capture_output=True, text=True, timeout=PLAZO + MARGEN)
    print(f"OK   version_instrumento vuelve en {time.time() - t0:.1f}s "
          f"(plazo {PLAZO:g}s)")
    print("     " + (pr.stdout.strip().splitlines() or [""])[-1])
    sys.exit(0)
except subprocess.TimeoutExpired:
    print(f"FALLO  no vuelve en {PLAZO + MARGEN:g}s: el plazo NO acota.")
    print("       Bajo servidor MCP esto cuelga la herramienta ENTERA después")
    print("       de haber escrito el .inp, el .out y el .pre.")
    sys.exit(1)
