# Installing

Requires **Python 3.12 or newer** and an internet connection (market data is
downloaded from Binance on demand — nothing large ships with the package).

Check what you have:

```bash
python --version
```

If that prints 3.11 or lower, or "command not found", install Python from
[python.org/downloads](https://www.python.org/downloads/) first. On Windows,
tick **"Add python.exe to PATH"** in the installer.

---

## Option 1 — install the released version (recommended)

```bash
pip install trading-bot
```

That gives you the `tradingbot` command. Verify it:

```bash
tradingbot doctor
```

### If `pip` or `tradingbot` is "not found"

Use the module form, which always works:

```bash
python -m pip install trading-bot
python -m trading_bot.cli doctor
```

On macOS and Linux you may need `python3` instead of `python`.

---

## Option 2 — install a downloaded release file

Every release attaches a `.whl` (wheel) and a `.tar.gz` (source archive) to
its [GitHub Releases page](https://github.com/MartexHACK/trading-bot/releases).
Download the `.whl` and install it directly — useful for an offline machine
or when you want to pin an exact build:

```bash
pip install ./trading_bot-1.0.0-py3-none-any.whl
```

---

## Option 3 — install from source (for development)

Do this if you want to change the code, add a strategy, or run the test
suite.

```bash
git clone https://github.com/MartexHACK/trading-bot.git
cd trading-bot

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -e .
pip install -r requirements-dev.txt
```

Confirm the checks pass before you change anything. Run them one per line:
Windows PowerShell has no `&&` operator, and chaining them there is a parser
error that silently runs nothing.

```bash
pytest
ruff check .
mypy
```

---

## Use a virtual environment

Whichever option you pick, installing into a virtual environment rather than
your system Python keeps this project's dependencies from colliding with
anything else:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install trading-bot
```

You must activate that environment (`source .venv/bin/activate`) in each new
terminal before `tradingbot` is on your PATH.

---

## Optional extras

The core install deliberately stays small. Two extras exist:

```bash
pip install "trading-bot[research]"   # TensorFlow — only for the TSLA CNN study
pip install "trading-bot[mt5]"        # MetaTrader 5 broker adapter (Windows only)
```

You do **not** need either to run the data pipeline, backtester, Monte Carlo,
paper trading, or dashboard.

---

## First run

```bash
tradingbot init my-lab
cd my-lab
tradingbot quickstart
```

`init` creates the workspace — where your data lake, paper-trading records,
and a copy of the research corpus live. `quickstart` downloads real market
data, backtests it honestly, and explains the result.

Full command reference: [USAGE.md](USAGE.md).

---

## Troubleshooting

**`tradingbot: command not found` after installing.**
Your virtual environment is not activated, or pip installed to a directory
that is not on your PATH. `python -m trading_bot.cli` always works as a
substitute.

**Data pull fails with a connection or 451 error.**
Binance restricts access from some regions and blocks some cloud IP ranges.
The data pipeline needs it; everything downstream needs data. A VPN or a
different machine is the usual fix.

**`tradingbot doctor` says the research corpus is missing.**
You are running from a source tree that was never installed. Run
`pip install -e .` from the repository root.

**Windows shows garbled characters in output.**
Set `PYTHONIOENCODING=utf-8` in your environment. Windows Terminal handles
this better than the legacy console.

**A command fails and you cannot tell why.**
Run `tradingbot doctor` first — it checks the install, the dependencies, the
corpus, and the workspace, and tells you the next command to run.
