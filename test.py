#!/usr/bin/env python
"""Runs pytest and associated test tooling"""
import os
from pathlib import Path
from subprocess import run

SRC_DIR = Path(__file__).resolve().parent.joinpath("pydration")
TESTS_DIR = Path(__file__).resolve().parent.joinpath("tests")

if not os.getenv("NO_RUFF"):
    ruff_cmd = ["poetry", "run", "ruff", "check", f"{SRC_DIR}"]
    run(ruff_cmd, check=True)
else:
    print("NO_RUFF set. Skipping...")

if not os.getenv("NO_BLACK"):
    black_cmd = ["poetry", "run", "black", f"{SRC_DIR}"]
    run(black_cmd, check=True)
else:
    print("NO_BLACK set. Skipping...")

if not os.getenv("NO_MYPY"):
    mypy_cmd = ["poetry", "run", "mypy", f"{SRC_DIR}"]
    run(mypy_cmd, check=True)
else:
    print("NO_MYPY set. Skipping...")

pytest_cmd = ["poetry", "run", "pytest", f"{TESTS_DIR}"]

run(pytest_cmd, check=True)
