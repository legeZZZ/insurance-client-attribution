"""Run the existing regression suite with the user-deferred console test excluded."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    tests = []
    excluded = []
    for test in flatten(suite):
        if ".test_console_" in test.id():
            excluded.append(test.id())
        else:
            tests.append(test)
    print("Deferred by user:", ", ".join(excluded), flush=True)
    result = unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(tests))
    sys.exit(not result.wasSuccessful())
