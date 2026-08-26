"""Entry point: python -m martex_quant.dashboard"""

from pathlib import Path

from martex_quant.dashboard.server import serve

if __name__ == "__main__":
    serve(Path.cwd())
