"""Poll every registered launch and append its state to the forward panel.

Run alongside ``meme_record.py``. The recorder decides *who is in the cohort*
(at birth, irrevocably); this decides *what happened to them* (by observation,
repeatedly). Keeping the two jobs separate is what makes the dataset defensible:
no outcome can ever influence membership.

Each pass fetches the whole tracked cohort in batches of 30 and appends one row
per pool per pass. Pools the API has stopped returning are written with
``alive=false`` rather than skipped — a token going dark is the modal outcome
in this market and has to stay in the denominator.

    python scripts/meme_panel.py --hours 14 --interval 300

Cohort size grows by roughly 2,000/hour, so a pass costs about
``tracked / 30`` requests: ~70 at hour one, ~900 by hour twelve. At 100
requests/minute that is well inside the endpoint's budget, but the pass
duration grows, so --interval should stay comfortably above it.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trading_bot.meme.registry import LaunchRegistry  # noqa: E402
from trading_bot.meme.sources.dexscreener import DexScreenerClient  # noqa: E402

logger = logging.getLogger("meme_panel")


def acquire_lock(path: Path) -> bool:
    """Atomically claim the poller role; see meme_record.acquire_lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                holder = int(path.read_text(encoding="utf-8").strip())
            except (ValueError, OSError):
                holder = -1
            if holder > 0 and _pid_alive(holder):
                logger.error("panel poller already running as PID %d", holder)
                return False
            path.unlink(missing_ok=True)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
        return True
    return False


def _pid_alive(pid: int) -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return str(pid) in result.stdout


def tracked_pools(registry: LaunchRegistry, max_age_h: float) -> list[str]:
    """Pools young enough to still be worth polling.

    Tracking is dropped past ``max_age_h`` so the pass cost stops growing
    without bound. This is a resource decision, not a filter on outcomes: by
    then every horizon we measure has already been observed, and dropping a
    pool from *future* polling cannot change what its panel already records.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=max_age_h)
    out: list[str] = []
    for row in registry.iter_rows():
        stamp = row.get("observed_at")
        address = row.get("pool_address")
        if not isinstance(stamp, str) or not isinstance(address, str):
            continue
        if datetime.fromisoformat(stamp) >= cutoff:
            out.append(address)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=float, default=14.0)
    parser.add_argument("--interval", type=float, default=300.0, help="seconds between passes")
    parser.add_argument("--max-age-h", type=float, default=30.0, help="stop polling past this age")
    parser.add_argument("--root", type=Path, default=Path("data/meme/launches"))
    parser.add_argument("--out", type=Path, default=Path("data/meme/panel"))
    parser.add_argument("--min-interval", type=float, default=0.6)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(message)s", stream=sys.stdout, force=True
    )

    lock_path = args.out.parent / "panel.lock"
    if not acquire_lock(lock_path):
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    registry = LaunchRegistry(args.root)
    client = DexScreenerClient(chain="solana")
    started = time.monotonic()
    deadline = started + args.hours * 3600.0
    passes = 0

    try:
        while time.monotonic() < deadline:
            pass_started = time.monotonic()
            # Re-read each pass: the recorder is appending new launches
            # continuously and they should enter the panel as soon as they exist.
            registry = LaunchRegistry(args.root)
            pools = tracked_pools(registry, args.max_age_h)
            if not pools:
                logger.info("no pools tracked yet; waiting")
                time.sleep(args.interval)
                continue

            states = client.fetch(pools)
            path = args.out / f"{datetime.now(UTC):%Y-%m-%d}.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                for state in states:
                    handle.write(json.dumps(state.to_row(), separators=(",", ":")) + "\n")

            alive = sum(1 for state in states if state.alive)
            passes += 1
            logger.info(
                "pass %d: %d tracked, %d alive (%.0f%%), %.0fs",
                passes,
                len(states),
                alive,
                100.0 * alive / len(states) if states else 0.0,
                time.monotonic() - pass_started,
            )
            sys.stdout.flush()

            remaining = args.interval - (time.monotonic() - pass_started)
            if remaining > 0 and time.monotonic() + remaining < deadline:
                time.sleep(remaining)
    except KeyboardInterrupt:
        logger.info("interrupted")
    finally:
        try:
            if lock_path.read_text(encoding="utf-8").strip() == str(os.getpid()):
                lock_path.unlink(missing_ok=True)
        except OSError:
            pass

    logger.info("done: %d passes", passes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
