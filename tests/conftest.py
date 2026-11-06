"""
tests/conftest.py
Ensures project root (onecontext) is on sys.path for pytest.
"""

import sys
from pathlib import Path

# Add onecontext directory to sys.path
root_dir = Path(__file__).parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
