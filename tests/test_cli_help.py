"""`art-mcp --help` and `--version` answer and exit instead of starting the
stdio server (drvarma BUG-0014, which covers the three servers)."""
import sys

import pytest

mcp_server = pytest.importorskip("art.mcp_server")


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_answers_and_exits(flag, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["art-mcp", flag])
    with pytest.raises(SystemExit) as e:
        mcp_server._cli_flags()
    assert e.value.code == 0
    assert capsys.readouterr().out.startswith("usage: art-mcp")


def test_version_answers_and_exits(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["art-mcp", "--version"])
    with pytest.raises(SystemExit) as e:
        mcp_server._cli_flags()
    assert e.value.code == 0
    assert capsys.readouterr().out.startswith("art-mcp (art-tseries) ")


def test_without_flags_it_returns(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["art-mcp"])
    assert mcp_server._cli_flags() is None
