"""Build-time hook: vendor the research corpus into the package.

Project metadata lives in `pyproject.toml`; this file exists only to copy
`docs/` and `config/` into `src/trading_bot/_bundle/` before the wheel is
built, so that `pip install martex-quant` ships the pre-registered hypotheses,
the trial ledger, and the universe config — not just the code. See
`trading_bot/bundle.py` for the runtime half.

`config/secrets/` is excluded explicitly. It is gitignored, but a developer
building a wheel on a machine where it exists must not publish it.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

_ROOT = Path(__file__).resolve().parent
_BUNDLE = _ROOT / "src" / "trading_bot" / "_bundle"
_TREES = ("docs", "config")

# Never vendor these, whatever the working tree happens to contain.
_EXCLUDE = shutil.ignore_patterns("secrets", "*.key", "*.pem", ".env", "__pycache__")


def _vendor_corpus() -> None:
    """Refresh `_bundle` from the repository's docs/ and config/ trees.

    Two build contexts reach this, and only one has those trees:

    - a source checkout, where they exist and `_bundle` must be rebuilt;
    - a wheel built *from an sdist*, where the sdist already carries a
      vendored `_bundle` but the top-level trees may not have survived the
      packaging step.

    So the vendored copy is only ever removed once there is something to
    replace it with. Deleting first and discovering the sources are absent
    would leave the wheel with no corpus at all — and, because package-data
    globs a directory that then does not exist, no wheel.
    """
    sources = [tree for tree in _TREES if (_ROOT / tree).is_dir()]
    if not sources:
        if _is_populated(_BUNDLE):
            return  # building from an sdist; the vendored copy is authoritative
        raise SystemExit(
            "setup.py: no docs/ or config/ to vendor and no existing "
            f"{_BUNDLE.name}/ — the built distribution would ship without the "
            "research corpus. Build from a full checkout or sdist."
        )

    if _BUNDLE.exists():
        shutil.rmtree(_BUNDLE)
    for tree in sources:
        shutil.copytree(_ROOT / tree, _BUNDLE / tree, ignore=_EXCLUDE)

    # Marks the directory as generated, for anyone who finds it in a working
    # tree and wonders why it is not in git.
    (_BUNDLE / "README.md").write_text(
        "Generated at build time by setup.py from the repository's docs/ "
        "and config/ trees. Do not edit; do not commit.\n",
        encoding="utf-8",
    )


def _is_populated(directory: Path) -> bool:
    return directory.is_dir() and any(directory.rglob("*.md"))


class build_py(_build_py):  # noqa: N801 - setuptools requires this command name
    def run(self) -> Any:
        _vendor_corpus()
        return super().run()


setup(cmdclass={"build_py": build_py})
