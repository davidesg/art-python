"""BUG-0267: the form of an intervention has one source, the ladder. The
diagnosis gives the dates without a form, option A's call runs as written, and
a Call 3 outside the ladder says so before estimating."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_bug_0267_repro_passes():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "bugs", "BUG-0267-repro", "repro.py")],
                       capture_output=True, text=True, timeout=900,
                       env={**os.environ, "PYTHONPATH": os.path.join(ROOT, "src"),
                            "ART_NO_VIEWER": "1"})
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert "CERRADO" in r.stdout


def test_the_key_joins_the_inp_and_its_pre(tmp_path):
    import art.mcp_server as m
    a = m._clave_forma(str(tmp_path / "m01.inp"), " 1803 ")
    b = m._clave_forma(str(tmp_path / "m01.pre"), "1803")
    assert a == b
