"""BUG-0253: tests/test_guion_instrumento.py::
test_avisa_si_el_arbol_tiene_cambios_sin_commitear runs `git status` on the
directory three levels above art/__init__.py, taking for granted that art is a
checkout and that git is installed. In an installed art (a wheel) that
directory is the venv's lib/, and on a machine without git the test does not
skip: it dies with FileNotFoundError: 'git'. The clean-install test of atsw
2.1.0 (2026-10-30, ten distributions in podman, art 0.2.3 from PyPI, no git in
the images) failed it in all ten.

The repro runs that test with a PATH that has python but no git. Expected: it
skips (or passes), it does not fail.

    python3 bugs/BUG-0253-repro/repro.py   # exits 1 while open
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
bin_ = tempfile.mkdtemp()
os.symlink(sys.executable, os.path.join(bin_, "python3"))
env = dict(os.environ, PATH=bin_)
p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                    "tests/test_guion_instrumento.py::test_avisa_si_el_arbol_tiene_cambios_sin_commitear"],
                   cwd=ROOT, env=env, capture_output=True, text=True)
print("\n".join(l for l in p.stdout.splitlines() if l.startswith(("E ", "FAILED", "1 ")))[:800])
sys.exit(1 if p.returncode == 1 else 0)
