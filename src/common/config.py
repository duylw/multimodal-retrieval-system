"""
Configuration loader and manager for the retrieval system.
Loads YAML settings and provides central access to pipeline parameters.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import yaml


class ConfigManager:
    """Manages system configuration loaded from a YAML file."""

    _instance: Optional["ConfigManager"] = None
    _config: Dict[str, Any] = {}

    def __init__(self, config_path: str = "configs/default_config.yaml"):
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found at: {config_path}")
        
        with open(path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

    @classmethod
    def get_instance(cls, config_path: str = "configs/default_config.yaml") -> "ConfigManager":
        """Singleton accessor for global configuration."""
        if cls._instance is None:
            cls._instance = ConfigManager(config_path)
        return cls._instance

    @property
    def config(self) -> Dict[str, Any]:
        """Returns the raw dictionary of configuration parameters."""
        return self._config

    def get(self, section: str, key: str = None, default: Any = None) -> Any:
        """
        Safely retrieves a configuration value.

        Args:
            section: Top-level section name in the YAML file.
            key: Optional sub-key within the section.
            default: Fallback value if section or key is not found.
        """
        sec_val = self._config.get(section, {})
        if key is None:
            return sec_val if sec_val is not None else default
        if isinstance(sec_val, dict):
            return sec_val.get(key, default)
        return default
