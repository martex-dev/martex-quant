"""Locating the shipped research corpus (docs + config).

The dashboard's Lab view, the hypothesis ledger, and the universe config are
read from paths relative to the *working directory* — `docs/research/ledger/
trials.toml`, `config/universe.json`. That works in a git checkout, where the
repo root is the working directory, but a `pip install trading-bot` gets only
the Python package: no docs, no config, so `tradingbot init` would have
nothing to copy into a new workspace.

So the wheel carries them. `setup.py` copies `docs/` and `config/` into
`trading_bot/_bundle/` at build time (secrets excluded), and this module
resolves whichever copy exists:

1. `trading_bot/_bundle/` — present in a built wheel or sdist install.
2. the repo root above `src/trading_bot/` — present in an editable/dev
   install, where the build-time copy never ran.

Returning None is a normal outcome, not an error: a user who installed the
wheel and deleted the bundle still gets a working backtester, just without
the pre-registered hypothesis corpus.
"""

from __future__ import annotations

from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent

#: Directories copied into a fresh workspace by `tradingbot init`.
BUNDLED_TREES = ("docs", "config")


def bundle_root() -> Path | None:
    """Directory holding the shipped `docs/` and `config/` trees, or None.

    The live checkout wins when there is one. An editable install still runs
    the build-time copy, so `_bundle/` exists in a dev tree but goes stale the
    moment a hypothesis doc is edited — serving that copy would show a
    developer yesterday's ledger. In a wheel there is no checkout and the
    packaged copy is the only answer.
    """
    # src/trading_bot/bundle.py -> src/trading_bot -> src -> repo root
    checkout = _PACKAGE_ROOT.parent.parent
    if is_editable_checkout() and _looks_like_bundle(checkout):
        return checkout

    packaged = _PACKAGE_ROOT / "_bundle"
    if _looks_like_bundle(packaged):
        return packaged

    return checkout if _looks_like_bundle(checkout) else None


def _looks_like_bundle(candidate: Path) -> bool:
    """A bundle is only useful if the ledger is in it — the rest follows."""
    return (candidate / "docs" / "research" / "ledger" / "trials.toml").is_file()


def is_editable_checkout() -> bool:
    """True when running from a git checkout rather than an installed wheel.

    Used only to word CLI messages accurately; nothing branches on it.
    """
    return (_PACKAGE_ROOT.parent.parent / "pyproject.toml").is_file()
