"""Entry point for the verified aggregate analysis and Streamlit dashboard."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BUILD_SCRIPT = ROOT / "scripts" / "build_aggregate_report.py"
APP_SCRIPT = ROOT / "app.py"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the evidence-based annual analysis or launch its dashboard."
    )
    parser.add_argument(
        "--stage",
        choices=["report", "all", "app"],
        default="report",
        help="'report' (or 'all') rebuilds the verified aggregate pipeline; 'app' launches Streamlit.",
    )
    args = parser.parse_args()

    if args.stage == "app":
        logger.info("Launching the Chennai road-safety research dashboard")
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(APP_SCRIPT)], cwd=ROOT, check=True)
        return

    logger.info("Running the validated annual aggregate analysis")
    logger.info("This workflow does not use generated event-level crash records.")
    subprocess.run([sys.executable, str(BUILD_SCRIPT)], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
