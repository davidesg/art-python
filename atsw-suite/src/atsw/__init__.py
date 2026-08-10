"""ATSW — A Time Series Workshop.

An umbrella distribution: `pip install atsw` pulls the whole Box-Jenkins-
Treadway suite and its three MCP assistants. It carries no analysis code of its
own, on purpose (see `atsw-mcp --help`).
"""

__version__ = "1.2.3"


def example_path(name: str = "") -> str:
    """Where the example data lives after `pip install atsw`.

    The worked examples in the documentation run on two public series that ship
    inside the package, so they can be reproduced without hunting for data:

        >>> import atsw
        >>> atsw.example_path("IPC_ES.csv")      # Spanish CPI, 2002-2019
        >>> atsw.example_path("WTI.csv")         # oil, same window
        >>> atsw.example_path()                  # the directory

    Sources and why the window stops in 2019 are in `PROVENANCE.md`, next to the
    data. Both series are public statistics and are shipped only so the examples
    can be run; they are not part of the software.
    """
    import os
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples")
    return os.path.join(here, name) if name else here
