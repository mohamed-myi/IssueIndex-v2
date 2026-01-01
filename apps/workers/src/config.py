"""Worker configuration: imports and re-exports backend settings"""

import sys
from pathlib import Path

# Add backend src to path for imports
backend_src = Path(__file__).parent.parent.parent / "backend" / "src"
if str(backend_src) not in sys.path:
    sys.path.insert(0, str(backend_src))

# Add packages to path for database imports
packages_db = Path(__file__).parent.parent.parent.parent / "packages" / "database" / "src"
if str(packages_db) not in sys.path:
    sys.path.insert(0, str(packages_db))

packages_shared = Path(__file__).parent.parent.parent.parent / "packages" / "shared" / "src"
if str(packages_shared) not in sys.path:
    sys.path.insert(0, str(packages_shared))

from core.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]

