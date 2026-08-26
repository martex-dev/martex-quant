"""Trading Bot: a quantitative trading research platform.

Data pipeline, event-driven backtesting, statistical validation, Monte Carlo
simulation against prop-firm rule sets, paper trading, and an operations
dashboard. Research software — see DISCLAIMER.md before connecting it to
anything that holds money.

The `martex-quant` command (trading_bot.cli) is the front door for an installed
copy; every subsystem also remains importable and runnable on its own.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

try:
    __version__ = _version("martex-quant")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
