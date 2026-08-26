"""Continuously capture the Solana new-pool stream into the launch registry.

Run this and leave it running. Every sweep walks the ten pages of
GeckoTerminal's new-pool feed — about a five-minute window of launches — and
records any pool it has not seen before, exactly as the API described it at
first sighting. Nothing is ever revised afterwards.

The default 90-second cadence gives roughly three-fold overlap against the
sliding window, so a burst of launches has to be extraordinary before anything
slips through, while costing under seven requests per minute against a
30-per-minute budget.

    python scripts/meme_record.py --hours 12
    python scripts/meme_record.py --forever --interval 90

Stop with Ctrl-C; the registry is append-only, so an interrupted run loses at
most the sweep in flight.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from martex_quant.meme.http import RateLimitedJsonClient  # noqa: E402
from martex_quant.meme.registry import LaunchRegistry  # noqa: E402
from martex_quant.meme.sources.geckoterminal import (  # noqa: E402
    MAX_NEW_POOL_PAGES,
    GeckoTerminalClient,
)

logger = logging.getLogger("meme_record")

_GECKO_ACCEPT = "application/json;version=20230302"


def acquire_lock(path: Path) -> bool:
    """Claim exclusive recorder rights, or report that someone else holds them.

    Two recorders are worse than none: they double the request rate into a
    30/minute budget (so both get throttled into backoff) and they interleave
    appends into one JSONL. A stale lock from a killed process is reclaimed by
    checking whether the recorded PID is still alive.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            # O_EXCL makes creation atomic, so two recorders starting in the same
            # instant cannot both conclude the lock was free. A check-then-write
            # would let both through, which is exactly the failure this guards.
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                holder = int(path.read_text(encoding="utf-8").strip())
            except (ValueError, OSError):
                holder = -1
            if holder > 0 and _pid_alive(holder):
                logger.error("recorder already running as PID %d (lock %s)", holder, path)
                return False
            logger.warning("reclaiming stale lock from PID %s", holder)
            path.unlink(missing_ok=True)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
        return True
    logger.error("could not acquire lock %s", path)
    return False


def _pid_alive(pid: int) -> bool:
    """Windows-safe liveness check without adding psutil."""
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


def sweep(client: GeckoTerminalClient, registry: LaunchRegistry, pages: int) -> tuple[int, int]:
    """One pass over the new-pool feed. Returns (seen, newly registered).

    A page that errors is logged and skipped rather than aborting the sweep:
    losing one page of one sweep costs a little coverage, losing the whole
    recorder costs the dataset.
    """
    seen = 0
    fresh = 0
    for page in range(1, pages + 1):
        try:
            snapshots = client.new_pools(page)
        except Exception as exc:  # noqa: BLE001 - one bad page must not kill the run
            logger.warning("page %d failed: %s", page, exc)
            continue
        seen += len(snapshots)
        fresh += len(registry.register(snapshots))
    return seen, fresh


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=float, default=1.0, help="how long to run")
    parser.add_argument(
        "--forever", action="store_true", help="ignore --hours and run until killed"
    )
    parser.add_argument("--interval", type=float, default=90.0, help="seconds between sweeps")
    parser.add_argument(
        "--pages", type=int, default=MAX_NEW_POOL_PAGES, help="new_pools pages/sweep"
    )
    parser.add_argument("--root", type=Path, default=Path("data/meme/launches"))
    parser.add_argument("--min-interval", type=float, default=3.0, help="seconds between requests")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
        force=True,
    )

    lock_path = args.root.parent / "recorder.lock"
    if not acquire_lock(lock_path):
        return 1

    # 3s spacing keeps the in-sweep burst at 20 requests/minute. The published
    # free-tier ceiling is 30/min, but it is enforced on a sliding window, so a
    # 10-page sweep at 2.2s spacing sits close enough to trip it intermittently.
    client = GeckoTerminalClient(
        network="solana",
        client=RateLimitedJsonClient(min_interval_s=args.min_interval, accept=_GECKO_ACCEPT),
    )
    registry = LaunchRegistry(args.root)
    started = time.monotonic()
    deadline = float("inf") if args.forever else started + args.hours * 3600.0

    logger.info(
        "recording solana launches -> %s (interval %.0fs, %d pages, known=%d)",
        registry.root,
        args.interval,
        args.pages,
        len(registry),
    )

    sweeps = 0
    total_new = 0
    try:
        while time.monotonic() < deadline:
            cycle_started = time.monotonic()
            seen, fresh = sweep(client, registry, args.pages)
            sweeps += 1
            total_new += fresh
            elapsed_h = (time.monotonic() - started) / 3600.0
            rate = total_new / elapsed_h if elapsed_h > 0 else 0.0
            logger.info(
                "sweep %d @ %s: %d listed, %d new (total %d, ~%.0f/hour)",
                sweeps,
                datetime.now(UTC).strftime("%H:%M:%S"),
                seen,
                fresh,
                total_new,
                rate,
            )
            sys.stdout.flush()  # log is redirected to a file; block buffering hides progress
            # Sweeps take ~22s of throttled request time; sleep only the remainder
            # so cadence stays honest rather than drifting to interval + work.
            remaining = args.interval - (time.monotonic() - cycle_started)
            if remaining > 0 and time.monotonic() + remaining < deadline:
                time.sleep(remaining)
    except KeyboardInterrupt:
        logger.info("interrupted")
    finally:
        # Only the holder clears it; a loser of the race must not free the winner.
        try:
            if lock_path.read_text(encoding="utf-8").strip() == str(os.getpid()):
                lock_path.unlink(missing_ok=True)
        except OSError:
            pass

    logger.info("done: %d sweeps, %d launches registered", sweeps, total_new)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
