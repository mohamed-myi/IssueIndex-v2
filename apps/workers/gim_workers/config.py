"""Worker configuration: imports and re-exports backend settings"""

from gim_backend.core.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
