"""Smoke test: the package imports and CI has something to run.

Replaced by real tests as each component lands (validator, store, collector).
"""

import trading_bot


def test_package_imports() -> None:
    assert trading_bot.__version__
