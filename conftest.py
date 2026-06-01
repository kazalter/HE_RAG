"""让测试无论用 `pytest` 还是 `python -m pytest` 都能 import 到 src 包。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
