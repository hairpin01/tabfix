import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from .formatters import Formatter


@dataclass
class FileTypeConfig:
    extensions: List[str]
    formatters: List[Formatter]
    disabled_rules: List[str] = field(default_factory=list)
    line_length: Optional[int] = None
    indent_size: Optional[int] = None
    use_tabs: Optional[bool] = None


@dataclass
class ProjectConfig:
    root_dir: Path
    file_types: Dict[str, FileTypeConfig] = field(default_factory=dict)
    exclude_patterns: List[str] = field(default_factory=list)
    include_patterns: List[str] = field(default_factory=list)
    default_indent: int = 4
    default_line_length: int = 88
    respect_gitignore: bool = True
    auto_fix: bool = True
    check_only: bool = False


class ConfigLoader:
    @staticmethod
    def find_config_file(start_dir: Path) -> Optional[Path]:
        config_names = [
            "unifmt.toml",
            "pyproject.toml",
            ".unifmtrc",
            ".unifmtrc.json",
            ".unifmtrc.toml",
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
            try:
                import tomllib
                with open(config_path, "rb") as f:
                    data = tomllib.load(f)

                if config_path.name == "pyproject.toml":
                    return data.get("tool", {}).get("unifmt", {})
                return data
            except ImportError:
                try:
                    import tomli
                    with open(config_path, "rb") as f:
                        data = tomli.load(f)

                    if config_path.name == "pyproject.toml":
                        return data.get("tool", {}).get("unifmt", {})
                    return data
                except ImportError:
                    print("TOML support requires tomllib (Python 3.11+) or tomli")
                    return {}
        elif suffix == ".json":
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            content = config_path.read_text(encoding="utf-8")
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
            "markdown": {
                "extensions": [".md", ".markdown"],
                "formatters": ["prettier"],
            },
            "json": {
                "extensions": [".json"],
                "formatters": ["prettier"],
            },
            "yaml": {
                "extensions": [".yaml", ".yml"],
                "formatters": ["prettier"],
            },
            "html": {
                "extensions": [".html", ".htm"],
                "formatters": ["prettier"],
            },
            "css": {
                "extensions": [".css", ".scss", ".sass"],
                "formatters": ["prettier"],
            },
        },
        "exclude_patterns": [
            "**/node_modules/**",
            "**/.git/**",
            "**/__pycache__/**",
            "**/*.pyc",
            "**/.venv/**",
            "**/venv/**",
            "**/dist/**",
            "**/build/**",
        ],
        "default_indent": 4,
        "default_line_length": 88,
        "respect_gitignore": True,
        "auto_fix": True,
    }


def init_project(root_dir: Path) -> bool:
    config_path = root_dir / "unifmt.toml"

    if config_path.exists():
        print(f"Config file already exists at {config_path}")
        return False

    default_config = create_default_config()

    try:
        import tomli_w
        with open(config_path, "wb") as f:
            tomli_w.dump(default_config, f)
        print(f"Created config file at {config_path}")
        return True
    except ImportError:
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2)
            print(f"Created JSON config file at {config_path}")
            return True
        except Exception as e:
            print(f"Failed to create config: {e}")
            return False
