"""Entry point: python -m trading_bot.dashboard"""

from pathlib import Path

from trading_bot.dashboard.server import serve

if __name__ == "__main__":
    serve(Path.cwd())
