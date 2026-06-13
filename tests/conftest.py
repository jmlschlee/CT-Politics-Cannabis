"""Make the project importable as `src.*` and force every test run to be offline
(fixtures/cache only — zero live requests)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
