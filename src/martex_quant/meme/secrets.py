"""Credential loading for the meme layer.

Keys live in ``config/secrets/*.json``, which is gitignored as a tree. They are
never read from the repo, never logged, and never printed - the only thing that
should ever surface in output is whether a key was found, not what it is.

Environment variables win over files so that a scheduled task or CI run can
supply a key without one existing on disk.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_SECRETS_DIR = Path("config/secrets")


class MissingCredential(RuntimeError):
    """Raised when a required key is absent, with instructions rather than a stack trace."""


def load_secret(
    name: str,
    field: str = "access_token",
    *,
    env_var: str | None = None,
    secrets_dir: Path | str = DEFAULT_SECRETS_DIR,
) -> str:
    """Return one credential, from the environment or ``<secrets_dir>/<name>.json``.

    Args:
        name: Basename of the JSON file, e.g. ``"bitquery"``.
        field: Key within that JSON object.
        env_var: Environment variable checked first. Defaults to
            ``<NAME>_<FIELD>`` upper-cased, e.g. ``BITQUERY_ACCESS_TOKEN``.
        secrets_dir: Directory holding the JSON files.

    Raises:
        MissingCredential: If neither source supplies a non-empty value. The
            message says how to fix it and never echoes any partial value.
    """
    env_name = env_var or f"{name}_{field}".upper()
    from_env = os.environ.get(env_name, "").strip()
    if from_env:
        return from_env

    path = Path(secrets_dir) / f"{name}.json"
    if not path.exists():
        raise MissingCredential(
            f"no credential for {name!r}: set ${env_name} or create {path} "
            f'containing {{"{field}": "..."}}'
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MissingCredential(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise MissingCredential(f"{path} must contain a JSON object")

    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise MissingCredential(f"{path} has no non-empty {field!r} field")
    return value.strip()


def has_secret(name: str, field: str = "access_token", **kwargs: object) -> bool:
    """Whether a credential is available, without revealing or returning it."""
    try:
        load_secret(name, field, **kwargs)  # type: ignore[arg-type]
    except MissingCredential:
        return False
    return True
