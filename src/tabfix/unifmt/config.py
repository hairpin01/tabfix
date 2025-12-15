import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class Formatter(Enum):
    BLACK = "black"
    AUTOPEP8 = "autopep8"
    ISORT = "isort"
    PRETTIER = "prettier"
    RUFF = "ruff"
    YAPF = "yapf"


@dataclass
class FileTypeConfig:
    extensions: list
    formatters: list
    line_length: Optional[int] = None
    indent_size: Optional[int] = None


@dataclass
class ProjectConfig:
    root_dir: Path
    file_types: Dict[str, FileTypeConfig] = field(default_factory=dict)
    exclude_patterns: list = field(default_factory=list)
    default_indent: int = 4
    default_line_length: int = 88
    respect_gitignore: bool = True
    auto_fix: bool = True
    check_only: bool = False


class ConfigLoader:
    @staticmethod
    def find_config_file(start_dir: Path) -> Optional[Path]:
        config_names = ["unifmt.toml", "pyproject.toml", ".unifmtrc"]

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
        if config_path.suffix == ".toml":
            try:
                import tomllib
                with open(config_path, "rb") as f:
                    data = tomllib.load(f)
                if config_path.name == "pyproject.toml":
                    return data.get("tool", {}).get("unifmt", {})
                return data
            except ImportError:
                print("Install tomllib for TOML support")
                return {}
        elif config_path.suffix == ".json":
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            content = config_path.read_text()
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {}


def create_default_config() -> Dict[str, Any]:
    return {
        "file_types": {
            "python": {
                "extensions": [".py"],
                "formatters": ["black", "isort"],
                "line_length": 88,
                "indent_size": 4,
            },
            "javascript": {
                "extensions": [".js", ".jsx", ".ts", ".tsx"],
                "formatters": ["prettier"],
                "line_length": 80,
                "indent_size": 2,
            },
        },
        "exclude_patterns": [
            "**/node_modules/**",
            "**/.git/**",
            "**/__pycache__/**",
        ],
        "default_indent": 4,
        "default_line_length": 88,
        "respect_gitignore": True,
        "auto_fix": True,
    }


def init_project(root_dir: Path) -> bool:
    config_path = root_dir / "unifmt.toml"

    if config_path.exists():
        print(f"Config already exists at {config_path}")
        return False

    try:
        import tomli_w
        config = create_default_config()
        with open(config_path, "wb") as f:
            tomli_w.dump(config, f)
        print(f"Created config at {config_path}")
        return True
    except ImportError:
        print("Install tomli-w to create TOML config")
        return False
