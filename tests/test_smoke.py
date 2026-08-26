"""Smoke test: the package imports and CI has something to run.

Replaced by real tests as each component lands (validator, store, collector).
"""

import martex_quant


def test_package_imports() -> None:
    assert martex_quant.__version__
