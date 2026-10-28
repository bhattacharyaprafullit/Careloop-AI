"""CareLoop AI ML package."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "apps" / "api")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
