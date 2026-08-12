"""Run pytest with a unique repository-owned temporary directory on Windows."""

from pathlib import Path
import subprocess
import sys
import uuid


BASE_DIR = Path(__file__).resolve().parent


def main() -> int:
    temp_dir = BASE_DIR / ".test-tmp" / uuid.uuid4().hex
    temp_dir.mkdir(parents=True, exist_ok=False)
    command = [
        sys.executable,
        "-m",
        "pytest",
        f"--basetemp={temp_dir}",
        *sys.argv[1:],
    ]
    return subprocess.call(command, cwd=BASE_DIR)


if __name__ == "__main__":
    raise SystemExit(main())
