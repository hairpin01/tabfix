__version__ = "1.2.5"

# Re-export core functionality
from .core import TabFix, Colors, print_color, GitignoreMatcher
from .config import TabFixConfig, ConfigLoader

# API functions will be defined inline to avoid import issues
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass, asdict


# Define TabFixConfig inline to avoid circular imports
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
    backup: bool = False
    verbose: bool = False
    quiet: bool = True
    no_color: bool = True
    git_staged: bool = False
    git_unstaged: bool = False
    git_all_changed: bool = False
    no_gitignore: bool = False
    recursive: bool = False
    interactive: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

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


# API helper functions
def fix_string(content: str, spaces: int = 4, **kwargs) -> Tuple[str, List[str]]:
    """Fix indentation and formatting in a string."""
    config = TabFixConfig(spaces=spaces, **kwargs)
    tabfix = TabFix(spaces_per_tab=config.spaces)

    changes = []
    fixed_content = content

    if config.fix_mixed:
        fixed_content, indent_changes = tabfix.fix_mixed_indentation(fixed_content)
        changes.extend(indent_changes)

    if config.fix_trailing:
        fixed_content, trailing_changes = tabfix.fix_trailing_spaces(fixed_content)
        changes.extend(trailing_changes)

    if config.final_newline:
        fixed_content, newline_changes = tabfix.ensure_final_newline(fixed_content)
        changes.extend(newline_changes)

    return fixed_content, changes


def fix_file(filepath: Path, spaces: int = 4, **kwargs) -> Tuple[bool, List[str]]:
    """Fix a single file."""
    config = TabFixConfig(spaces=spaces, **kwargs)
    tabfix = TabFix(spaces_per_tab=config.spaces)

    class Args:
        def __init__(self, config):
            for key, value in config.to_dict().items():
                setattr(self, key, value)

    args = Args(config)
    return tabfix.process_file(filepath, args, None)


def check_file(filepath: Path, spaces: int = 4, **kwargs) -> Tuple[bool, List[str]]:
    """Check if a file needs fixing."""
    config = TabFixConfig(spaces=spaces, **kwargs)
    config.dry_run = True
    config.check_only = True
    tabfix = TabFix(spaces_per_tab=config.spaces)

    class Args:
        def __init__(self, config):
            for key, value in config.to_dict().items():
                setattr(self, key, value)

    args = Args(config)
    return tabfix.process_file(filepath, args, None)


def detect_indentation(content: str) -> Dict[str, Any]:
    """Detect indentation style in content."""
    tabfix = TabFix()
    return tabfix.detect_indentation(content)


def create_config_file(filepath: Path, config: Optional[TabFixConfig] = None):
    """Create a configuration file."""
    import json
    config = config or TabFixConfig()
    with open(filepath, 'w') as f:
        json.dump(config.to_dict(), f, indent=2)


# For backwards compatibility
class TabFixAPI:
    def __init__(self, config: Optional[TabFixConfig] = None):
        self.config = config or TabFixConfig()
        self.tabfix = TabFix(spaces_per_tab=self.config.spaces)

    def fix_string(self, content: str, filepath: Optional[Path] = None) -> Tuple[str, List[str]]:
        return fix_string(content, **self.config.to_dict())

    def fix_file(self, filepath: Path) -> Tuple[bool, List[str]]:
        return fix_file(filepath, **self.config.to_dict())

    def check_file(self, filepath: Path) -> Tuple[bool, List[str]]:
        return check_file(filepath, **self.config.to_dict())

    def detect_indentation(self, content: str) -> Dict[str, Any]:
        return detect_indentation(content)


__all__ = [
    "TabFix",
    "Colors",
    "print_color",
    "GitignoreMatcher",
    "TabFixConfig",
    "TabFixAPI",
    "fix_string",
    "fix_file",
    "check_file",
    "detect_indentation",
    "create_config_file",
]
