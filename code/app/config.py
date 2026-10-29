"""Paths and settings, all read from the environment (code/.env is loaded by __main__)."""
import os
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = CODE_DIR.parent


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR") or REPO_DIR)


def mock_system_dir() -> Path:
    return Path(os.environ.get("MOCK_SYSTEM_DIR") or REPO_DIR / "mock_system")


RUNS_DIR = CODE_DIR / "runs"
TRACES_DIR = CODE_DIR / "traces"

# Rupee threshold used by R-01 and R-11 ("more than ₹1 crore").
ONE_CRORE = 1_00_00_000.0

MAX_REVIEW_ROUNDS = 2
