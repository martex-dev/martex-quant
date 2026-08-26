"""Autostart launcher for the dashboard (windowless, via pythonw).

Registered under HKCU\\...\\Run so the dashboard server starts at every
logon with no console window. Sets the working directory the server
expects, then serves forever.
"""

import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT)
sys.path.insert(0, str(PROJECT / "src"))

from martex_quant.dashboard.server import serve  # noqa: E402

try:
    serve(PROJECT)
except OSError:
    pass  # port already in use: another instance is running — fine, exit quietly
