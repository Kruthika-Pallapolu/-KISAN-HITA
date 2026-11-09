"""Run the backend unittest suite against a disposable SQLite database."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    # Tests must not create fixture users or alter rate limits in the app DB.
    with tempfile.TemporaryDirectory(prefix="kisan-hita-backend-tests-") as test_dir:
        os.environ["DATABASE_PATH"] = str(Path(test_dir) / "test.sqlite3")
        # Never make paid providers or production credentials available to tests.
        os.environ["GNANI_LIVE_ENABLED"] = "false"
        os.environ["GEMINI_ENABLED"] = "false"
        os.environ["GEMINI_API_KEY"] = ""
        os.environ["GOOGLE_API_KEY"] = ""
        # Market-price tests exercise only the local deterministic
        # illustrative dataset.
        os.environ["DEMO_DATA_ENABLED"] = "false"
        os.chdir(PROJECT_ROOT)
        sys.path.insert(0, str(PROJECT_ROOT))
        suite = unittest.defaultTestLoader.discover(
            str(PROJECT_ROOT / "backend" / "tests"), pattern="test_*.py"
        )
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
