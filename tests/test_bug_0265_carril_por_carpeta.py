"""BUG-0265: the autonomous lane holds for the whole series folder (no images,
no windows), and the guided lane still shows its figures."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_bug_0265_repro_passes():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "bugs", "BUG-0265-repro", "repro.py")],
                       capture_output=True, text=True, timeout=600,
                       env={**os.environ, "PYTHONPATH": os.path.join(ROOT, "src")})
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert "FIXED" in r.stdout


def test_every_tool_is_wrapped():
    import art.mcp_server as m
    ts = m.mcp._tool_manager.list_tools()
    assert ts and all(getattr(t.fn, "_carril_por_carpeta", False) for t in ts)


def test_a_folder_without_lane_is_guided(tmp_path):
    import art.mcp_server as m
    assert m._carpetas({"inp_path": str(tmp_path / "X.inp")}) == [str(tmp_path)]
    assert m._CARRIL_CARPETA.get(str(tmp_path)) is None
