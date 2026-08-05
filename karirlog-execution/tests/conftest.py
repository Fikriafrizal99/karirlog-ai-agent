from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT.parent / "karirlog-contracts" / "src"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(CONTRACTS))
