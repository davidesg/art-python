"""
Regression test for BUG-0003 — clean estimation tools did not persist .pre/.out.

estimate_and_diagnose used to only render to screen, so a model estimated through
the clean path was left without the `.pre`/`.out` artefacts the workflow needs
(only confirm_and_estimate wrote them, and it carried the μ-collapse BUG-0001).
The fix adds an opt-in `output_path` that writes the `.pre`+`.out` trio.

See bugs/BUG-0003-display-tools-no-persist.md.
"""

import os

import pytest

_RIPC1 = os.path.expanduser(
    "~/Dropbox/SRC/atws/fue/fue/tests/real_cases/PRICES"
    "/IPC/Mensual/sample_1.2002_12.2007/RIPC.1.pre"
)


def _skip_if_missing(path):
    if not os.path.exists(path):
        pytest.skip(f"test data not found: {path}")


def _text(result):
    return next(it.text for it in result if getattr(it, "type", "") == "text")


def test_estimate_and_diagnose_persists_pre_out(tmp_path):
    _skip_if_missing(_RIPC1)
    from art.mcp_server import estimate_and_diagnose
    out = str(tmp_path / "clean.inp")
    result = estimate_and_diagnose(_RIPC1, output_path=out)
    base = os.path.splitext(out)[0]
    assert os.path.exists(base + ".pre")
    assert os.path.exists(base + ".out")
    assert "Guardado" in _text(result)


def test_estimate_and_diagnose_no_persist_by_default():
    _skip_if_missing(_RIPC1)
    from art.mcp_server import estimate_and_diagnose
    result = estimate_and_diagnose(_RIPC1)          # no output_path → screen only
    assert result and result[0].type == "text"
    assert "Guardado" not in _text(result)
