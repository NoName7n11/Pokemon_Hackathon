from __future__ import annotations

import sys
from pathlib import Path


PLAN_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PLAN_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
