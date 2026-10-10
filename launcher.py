"""Stable stdio launcher; installs live alongside this file in private tools directory."""
import os
import sys
from pathlib import Path


def launch():
    root = Path(__file__).resolve().parent
    os.environ["AGENT_REACH_PLUS_HOME"] = str(root)
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["HOME"] = str(Path.home())
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    from agent_reach_plus.server import main
    main()

if __name__ == "__main__":
    launch()
