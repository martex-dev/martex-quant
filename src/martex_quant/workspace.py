"""Workspaces: where an installed copy keeps its data and research corpus.

Almost every path in this project is resolved relative to the working
directory — `data/lake`, `data/paper/<strategy>`, `docs/research/ledger/
trials.toml`, `config/universe.json`. In a git checkout that is simply the
repo root, which is why it was never a problem.

An installed `martex-quant` has no repo root. Rather than thread an explicit
root through every module (a large, risky change to code the ledger already
depends on), the CLI resolves a *workspace* directory and chdirs into it
before dispatching. One decision, one place, and every existing relative
path keeps meaning what it always meant.

Resolution order:

1. `--workspace/-w` on the command line,
2. `$MARTEX_QUANT_HOME`,
3. the current directory, if it already looks like a workspace or a checkout,
4. the current directory regardless — with `init` telling the user what to do.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from martex_quant.bundle import BUNDLED_TREES, bundle_root

HOME_ENV = "MARTEX_QUANT_HOME"

#: Created by `init`; the lake and paper-trading state live here.
DATA_DIRS = (
    Path("data") / "lake",
    Path("data") / "paper",
    Path("data") / "series",
)

_MARKER = "data"

#: Never copied into a workspace. `setup.py` already keeps these out of the
#: wheel, but `init` can also run against a live checkout, where they exist.
_NEVER_COPY = ("secrets", "__pycache__", ".env")
_NEVER_COPY_SUFFIXES = (".key", ".pem")


def looks_like_workspace(path: Path) -> bool:
    """True if `path` has been initialised (or is a repo checkout)."""
    return (path / _MARKER).is_dir() or (path / "pyproject.toml").is_file()


def resolve(explicit: Path | None = None) -> Path:
    """Pick the workspace directory. Does not create or validate it."""
    if explicit is not None:
        return explicit.expanduser().resolve()

    from_env = os.environ.get(HOME_ENV)
    if from_env:
        return Path(from_env).expanduser().resolve()

    return Path.cwd().resolve()


def initialise(target: Path, *, overwrite: bool = False) -> list[str]:
    """Create a workspace at `target`, copying in the shipped corpus.

    Returns human-readable lines describing what happened, so the CLI can
    print a report without this module knowing about output formatting.

    Existing files are never overwritten unless `overwrite` is set: re-running
    `init` on a live workspace must not destroy a trade journal or a locally
    edited hypothesis doc.
    """
    report: list[str] = []
    target.mkdir(parents=True, exist_ok=True)

    for relative in DATA_DIRS:
        directory = target / relative
        existed = directory.is_dir()
        directory.mkdir(parents=True, exist_ok=True)
        report.append(f"{'exists' if existed else 'created'}  {relative.as_posix()}/")

    source = bundle_root()
    if source is None:
        report.append(
            "missing  research corpus not found in this install — docs/ and config/ were not copied"
        )
        return report

    if source.resolve() == target.resolve():
        report.append("skipped  docs/ and config/ (workspace is the source checkout)")
        return report

    for tree in BUNDLED_TREES:
        origin = source / tree
        if not origin.is_dir():
            continue
        copied, skipped = _copy_tree(origin, target / tree, overwrite=overwrite)
        report.append(f"copied   {tree}/ ({copied} files, {skipped} left alone)")

    return report


def _copy_tree(origin: Path, destination: Path, *, overwrite: bool) -> tuple[int, int]:
    copied = skipped = 0
    for path in sorted(origin.rglob("*")):
        if path.is_dir() or _is_secret(path):
            continue
        relative = path.relative_to(origin)
        out = destination / relative
        if out.exists() and not overwrite:
            skipped += 1
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)
        copied += 1
    return copied, skipped


def _is_secret(path: Path) -> bool:
    """Credentials and caches, which must never reach a copied workspace."""
    if any(part in _NEVER_COPY for part in path.parts):
        return True
    return path.suffix in _NEVER_COPY_SUFFIXES
