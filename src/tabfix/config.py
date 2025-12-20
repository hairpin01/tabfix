#!/usr/bin/env python3
import json
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field, asdict
import os

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
    check_only: bool = False
    backup: bool = False
    verbose: bool = False
    quiet: bool = False
    no_color: bool = False

    git_staged: bool = False
    git_unstaged: bool = False
    git_all_changed: bool = False
    no_gitignore: bool = False

    include_patterns: list = field(default_factory=list)
    exclude_patterns: list = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def update_from_dict(self, data: Dict[str, Any]):
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def update_from_args(self, args):
        for key, value in vars(args).items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)


class ConfigLoader:
    @staticmethod
    def find_config_file(start_dir: Path) -> Optional[Path]:
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


def init_project(root_dir: Path) -> bool:
    config_path = root_dir / ".tabfixrc"
    
    if config_path.exists():
        print(f"Configuration file already exists at {config_path}")
        return False
    
    config = TabFixConfig()
    if ConfigLoader.save_config(config, config_path):
        print(f"Created configuration file at {config_path}")
        return True
    else:
        print("Failed to create configuration file")
        return False
