"""Freeze (or verify) the research baseline: golden stdout + fingerprints.

    .venv/Scripts/python scripts/freeze_research_baseline.py            # verify
    .venv/Scripts/python scripts/freeze_research_baseline.py --write    # freeze

MI Lab Layer 1, Step 0. Writing goldens is DELIBERATE: without --write this
tool only reports differences and exits nonzero if any exist. There is no
"update on failure" path anywhere in the test suite, because a golden that
changes is a change to research history, not a stale fixture.

If a golden legitimately must change (a corrected estimator, a refreshed
lake), that is its own pre-registered decision with its own commit — never
a side effect of a refactor.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from trading_bot.research.baseline import (
    FINGERPRINT_FILE,
    FROZEN_CATEGORIES,
    GOLDEN_DIR,
    SPECS,
    ScriptSpec,
    compare_fingerprints,
    fingerprint,
    inputs_present,
    read_golden,
    run_script,
    spec_by_name,
)

ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python scripts/freeze_research_baseline.py",
        description="Freeze or verify the frozen research baseline.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="write goldens and fingerprints (deliberate research-history change)",
    )
    parser.add_argument("--only", action="append", default=None, help="script name (repeatable)")
    return parser.parse_args(argv)


def selected(names: list[str] | None) -> tuple[ScriptSpec, ...]:
    if not names:
        return SPECS
    return tuple(spec_by_name(name) for name in names)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    specs = selected(args.only)
    golden_dir = ROOT / GOLDEN_DIR
    golden_dir.mkdir(parents=True, exist_ok=True)
    fingerprint_path = golden_dir / FINGERPRINT_FILE

    stored: dict[str, object] = {}
    if fingerprint_path.exists():
        stored = json.loads(fingerprint_path.read_text(encoding="utf-8"))

    fingerprints: dict[str, object] = dict(stored)
    failures: list[str] = []

    for spec in specs:
        if not inputs_present(spec, ROOT):
            print(f"{spec.name:<24} SKIP — declared inputs missing locally")
            failures.append(f"{spec.name}: inputs missing")
            continue

        output = run_script(spec, ROOT)
        current = fingerprint(spec, ROOT)
        golden_path = ROOT / spec.golden_path

        if not spec.requires_exact_stdout:
            # Audited, not stdout-gated: the script ran and exited 0, and its
            # inputs are fingerprinted, but its output is a function of the
            # calendar so no byte-exact fixture can be permanent.
            fingerprints[spec.name] = current
            deps = "; ".join(spec.external_dependencies)
            print(f"{spec.name:<24} AUDITED (time-dependent: {deps})")
            continue

        if args.write:
            # Bytes, not write_text: text mode would translate LF to CRLF on
            # Windows and the fixture would stop matching subprocess output.
            golden_path.write_bytes(output.encode("utf-8"))
            fingerprints[spec.name] = current
            print(f"{spec.name:<24} WROTE {len(output.splitlines())} lines")
            continue

        if not golden_path.exists():
            print(f"{spec.name:<24} MISSING golden (run with --write to create)")
            failures.append(f"{spec.name}: no golden")
            continue

        expected_output = read_golden(spec, ROOT)
        previous = stored.get(spec.name)
        status = "OK"
        if output != expected_output:
            status = "STDOUT DIFFERS"
            failures.append(f"{spec.name}: stdout differs")
        if isinstance(previous, dict):
            report = compare_fingerprints(previous, current)
            frozen_hits = [c for c in FROZEN_CATEGORIES if c in report]
            if frozen_hits:
                status += f"  [{', '.join(frozen_hits)} CHANGED]"
                failures.append(f"{spec.name}: {frozen_hits} changed")
            elif "code" in report:
                status += "  [code changed — expected during Layer 1]"
        print(f"{spec.name:<24} {status}")

    if args.write:
        fingerprint_path.write_bytes(
            (json.dumps(fingerprints, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
        print(f"\nfingerprints written to {fingerprint_path.relative_to(ROOT).as_posix()}")
        return 0

    if failures:
        print("\nFAILURES:")
        for line in failures:
            print(f"  {line}")
        return 1
    print("\nbaseline verified: all goldens reproduce, no frozen category changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
