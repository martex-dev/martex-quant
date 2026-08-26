"""CLI and workspace tests: the surfaces a downloaded copy exposes.

These guard the distribution contract rather than any research result — that
`tradingbot` parses, that a fresh workspace comes out complete, that secrets
never travel into one, and that commands fail with an explanation instead of
a traceback when the lake is empty.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trading_bot import workspace as ws
from trading_bot.bundle import bundle_root
from trading_bot.cli import build_parser, main

REPO_ROOT = Path(__file__).resolve().parent.parent


# -- parser ----------------------------------------------------------------


def test_every_subcommand_has_a_handler() -> None:
    """A subcommand without a handler would crash on dispatch."""
    parser = build_parser()
    subparsers = [
        action
        for action in parser._subparsers._group_actions  # type: ignore[union-attr]
        if hasattr(action, "choices")
    ][0]
    for name, sub in subparsers.choices.items():
        defaults = sub._defaults
        assert "handler" in defaults, f"{name} has no handler"


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    assert "quickstart" in capsys.readouterr().out


def test_bare_invocation_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "tradingbot" in capsys.readouterr().out


def test_disclaimer_is_in_the_help_text() -> None:
    """Anyone typing `tradingbot --help` must see this is not advice."""
    assert "not financial advice" in build_parser().description.lower()  # type: ignore[union-attr]


# -- workspace -------------------------------------------------------------


def test_init_creates_data_dirs_and_corpus(tmp_path: Path) -> None:
    target = tmp_path / "lab"
    ws.initialise(target)

    for relative in ws.DATA_DIRS:
        assert (target / relative).is_dir()
    assert (target / "docs" / "research" / "ledger" / "trials.toml").is_file()
    assert (target / "config" / "universe.json").is_file()


def test_init_is_idempotent_and_never_clobbers(tmp_path: Path) -> None:
    """Re-running init on a live workspace must not destroy local edits."""
    target = tmp_path / "lab"
    ws.initialise(target)

    ledger = target / "docs" / "research" / "ledger" / "trials.toml"
    ledger.write_text("locally edited", encoding="utf-8")
    journal = target / "data" / "paper" / "journal.jsonl"
    journal.write_text('{"kept": true}\n', encoding="utf-8")

    ws.initialise(target)

    assert ledger.read_text(encoding="utf-8") == "locally edited"
    assert journal.read_text(encoding="utf-8") == '{"kept": true}\n'


def test_init_overwrite_restores_corpus(tmp_path: Path) -> None:
    target = tmp_path / "lab"
    ws.initialise(target)
    ledger = target / "docs" / "research" / "ledger" / "trials.toml"
    ledger.write_text("clobbered", encoding="utf-8")

    ws.initialise(target, overwrite=True)

    assert ledger.read_text(encoding="utf-8") != "clobbered"


def test_init_never_copies_credentials(tmp_path: Path) -> None:
    """A workspace copied from a live checkout must not carry API keys."""
    source = tmp_path / "source"
    (source / "config" / "secrets").mkdir(parents=True)
    (source / "config" / "secrets" / "bitquery.json").write_text('{"key": "SECRET"}')
    (source / "config").joinpath("universe.json").write_text("[]")
    (source / "config").joinpath("broker.pem").write_text("PRIVATE")

    destination = tmp_path / "lab" / "config"
    copied, _ = ws._copy_tree(source / "config", destination, overwrite=False)

    assert copied == 1
    assert (destination / "universe.json").is_file()
    assert not (destination / "secrets").exists()
    assert not (destination / "broker.pem").exists()


def test_resolve_prefers_explicit_over_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ws.HOME_ENV, str(tmp_path / "from-env"))
    assert ws.resolve(tmp_path / "explicit") == (tmp_path / "explicit").resolve()
    assert ws.resolve(None) == (tmp_path / "from-env").resolve()


def test_resolve_falls_back_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ws.HOME_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    assert ws.resolve(None) == tmp_path.resolve()


def test_looks_like_workspace(tmp_path: Path) -> None:
    assert not ws.looks_like_workspace(tmp_path)
    (tmp_path / "data").mkdir()
    assert ws.looks_like_workspace(tmp_path)


# -- bundle ----------------------------------------------------------------


def test_bundle_resolves_in_this_checkout() -> None:
    source = bundle_root()
    assert source is not None
    assert (source / "docs" / "research" / "ledger" / "trials.toml").is_file()


# -- dispatch --------------------------------------------------------------


def test_missing_workspace_is_reported_not_raised(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["-w", str(tmp_path / "nope"), "data", "status"]) == 1
    assert "no such workspace" in capsys.readouterr().err


def test_data_status_on_empty_lake_explains_itself(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ws.initialise(tmp_path)
    assert main(["-w", str(tmp_path), "data", "status"]) == 1
    assert "tradingbot data pull" in capsys.readouterr().out


def test_backtest_without_data_explains_itself(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ws.initialise(tmp_path)
    assert main(["-w", str(tmp_path), "backtest", "--symbol", "BTCUSDT"]) == 1
    assert "pull it first" in capsys.readouterr().err


def test_backtest_rejects_unknown_interval(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ws.initialise(tmp_path)
    assert main(["-w", str(tmp_path), "backtest", "--interval", "3s"]) == 2
    assert "unknown interval" in capsys.readouterr().err


def test_ledger_reads_a_copied_workspace(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The corpus must be usable from a workspace, not only the checkout."""
    ws.initialise(tmp_path)
    assert main(["-w", str(tmp_path), "ledger", "--limit", "5"]) == 0
    out = capsys.readouterr().out
    assert "trials registered" in out
    assert "kill rate" in out


def test_ledger_unknown_verdict_lists_the_real_ones(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ws.initialise(tmp_path)
    assert main(["-w", str(tmp_path), "ledger", "--verdict", "spectacular"]) == 0
    assert "Known verdicts" in capsys.readouterr().out


def test_ledger_without_corpus_points_at_init(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "data").mkdir()
    assert main(["-w", str(tmp_path), "ledger"]) == 1
    assert "tradingbot init" in capsys.readouterr().err


def test_doctor_reports_an_uninitialised_workspace(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["-w", str(tmp_path), "doctor"]) == 1
    assert "not initialised" in capsys.readouterr().out


def test_doctor_passes_on_a_real_workspace(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ws.initialise(tmp_path)
    assert main(["-w", str(tmp_path), "doctor"]) == 0
    assert "problems found" not in capsys.readouterr().out


# -- packaging contract ----------------------------------------------------


def test_universe_config_is_valid_json_in_a_fresh_workspace(tmp_path: Path) -> None:
    """The rotation universe is read from config/; a broken copy is silent."""
    ws.initialise(tmp_path)
    payload = json.loads((tmp_path / "config" / "universe.json").read_text(encoding="utf-8"))
    assert payload


def test_release_documents_exist() -> None:
    for name in ("LICENSE", "DISCLAIMER.md", "CHANGELOG.md", "README.md"):
        assert (REPO_ROOT / name).is_file(), f"{name} is required for a public release"


def test_entry_point_is_declared() -> None:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'tradingbot = "trading_bot.cli:main"' in text
