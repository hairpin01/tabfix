#!/usr/bin/env python3
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field, asdict


try:
    import tomllib
    TOML_AVAILABLE = True
except ImportError:
    try:
        import tomli as tomllib
        TOML_AVAILABLE = True
    except ImportError:
        TOML_AVAILABLE = False


@dataclass
class TabFixConfig:
    """Configuration for tabfix tool."""
    spaces: int = 4
    fix_mixed: bool = True
    fix_trailing: bool = True
    final_newline: bool = True
    remove_bom: bool = False
    keep_bom: bool = False
    format_json: bool = True
    max_file_size: int = 10 * 1024 * 1024
    skip_binary: bool = True
    fallback_encoding: str = "latin-1"
    warn_encoding: bool = False
    force_encoding: Optional[str] = None
    smart_processing: bool = True
    preserve_quotes: bool = False
    progress: bool = False
    dry_run: bool = False
    backup: bool = False
    verbose: bool = False
    quiet: bool = False
    no_color: bool = False

    # Git options
    git_staged: bool = False
    git_unstaged: bool = False
    git_all_changed: bool = False
    no_gitignore: bool = False

    # Path patterns
    include_patterns: list = field(default_factory=list)
    exclude_patterns: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TabFixConfig":
        """Create config from dictionary."""
        valid_fields = {f.name for f in field(cls)}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)

    def update_from_args(self, args):
        """Update config from argparse namespace."""
        for key, value in vars(args).items():
            if hasattr(self, key) and value is not None:
                # Only update if value is not default (for booleans, check if explicitly set)
                if isinstance(value, bool) and value == False and key not in vars(args):
                    # Skip False booleans that might be defaults
                    continue
                setattr(self, key, value)


class ConfigLoader:
    """Load configuration from various file formats."""

    @staticmethod
    def find_config_file(start_dir: Path) -> Optional[Path]:
        """Find configuration file in directory hierarchy."""
        config_names = [
            ".tabfixrc",
            ".tabfixrc.json",
            ".tabfixrc.toml",
            ".tabfixrc.yaml",
            ".tabfixrc.yml",
            "pyproject.toml",
            "tabfix.json",
        ]

        current = start_dir
        while current != current.parent:
            for name in config_names:
                config_path = current / name
                if config_path.exists():
                    return config_path
            current = current.parent
        return None

    @staticmethod
    def load_config(config_path: Path) -> Dict[str, Any]:
        """Load configuration from file."""
        suffix = config_path.suffix.lower()

        if suffix == ".toml":
            if not TOML_AVAILABLE:
                raise ImportError("TOML support requires tomllib (Python 3.11+) or tomli")

            with open(config_path, "rb") as f:
                data = tomllib.load(f)

            if config_path.name == "pyproject.toml":
                return data.get("tool", {}).get("tabfix", {})
            return data

        elif suffix in [".yaml", ".yml"]:
            try:
                import yaml
                with open(config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
            except ImportError:
                raise ImportError("YAML support requires PyYAML")

        elif suffix == ".json" or config_path.name == ".tabfixrc":
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)

        else:
            return {}

    @staticmethod
    def save_config(config: TabFixConfig, config_path: Path) -> bool:
        """Save configuration to file."""
        suffix = config_path.suffix.lower()

        try:
            if suffix == ".json" or config_path.name == ".tabfixrc":
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(config.to_dict(), f, indent=2)

            elif suffix == ".toml":
                if not TOML_AVAILABLE:
                    raise ImportError("TOML support requires tomllib or tomli")

                import tomli_w
                with open(config_path, "wb") as f:
                    tomli_w.dump(config.to_dict(), f)

            elif suffix in [".yaml", ".yml"]:
                import yaml
                with open(config_path, "w", encoding="utf-8") as f:
                    yaml.dump(config.to_dict(), f, default_flow_style=False)

            else:
                return False

            return True

        except Exception as e:
            print(f"Error saving config: {e}")
            return False


class TabFixConfig:
    def update_from_dict(self, data: dict):
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def update_from_args(self, args):
        for key in vars(args):
            if hasattr(self, key):
                value = getattr(args, key)
                if value is not None:
                    setattr(self, key, value)
