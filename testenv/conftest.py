"""Source imports; unavailable native tests are deselected and reported NOT RUN."""
from pathlib import Path
import os
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "testenv"), str(ROOT)]


def pytest_collection_modifyitems(config, items):
    import tools_native_check as native
    reason = native.unavailable_reason(native.defaults())
    if not reason:
        return
    excluded = [item for item in items if "lobby" in item.fixturenames]
    items[:] = [item for item in items if item not in excluded]
    config.hook.pytest_deselected(items=excluded)
    config._native_not_run = (len(excluded), reason)


def pytest_report_collectionfinish(config, start_path, items):
    count, reason = getattr(config, "_native_not_run", (0, ""))
    if count:
        return f"NOT RUN {count} native tests: {reason}; build in the nix devShell"
