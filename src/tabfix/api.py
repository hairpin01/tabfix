from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass, asdict
import json

from .core import TabFix, GitignoreMatcher


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


class TabFixAPI:
    def __init__(self, config: Optional[TabFixConfig] = None):
        self.config = config or TabFixConfig()
        self.tabfix = TabFix(spaces_per_tab=self.config.spaces)

    def fix_string(self, content: str, filepath: Optional[Path] = None) -> Tuple[str, List[str]]:
        changes = []
        fixed_content = content

        if self.config.format_json and filepath and filepath.suffix.lower() == ".json":
            formatted, changed = self.tabfix.format_json(fixed_content)
            if changed:
                fixed_content = formatted
                changes.append("Formatted JSON")

        if self.config.fix_mixed:
            fixed_content, indent_changes = self.tabfix.fix_mixed_indentation(fixed_content)
            changes.extend(indent_changes)

        if self.config.fix_trailing:
            fixed_content, trailing_changes = self.tabfix.fix_trailing_spaces(fixed_content)
            changes.extend(trailing_changes)

        if self.config.final_newline:
            fixed_content, newline_changes = self.tabfix.ensure_final_newline(fixed_content)
            changes.extend(newline_changes)

        return fixed_content, changes

    def fix_file(self, filepath: Path) -> Tuple[bool, List[str]]:
        class Args:
            def __init__(self, config):
                for key, value in config.to_dict().items():
                    setattr(self, key, value)

        args = Args(self.config)
        
        if hasattr(self.tabfix, 'process_file_with_changes'):
            return self.tabfix.process_file_with_changes(filepath, args)
        else:
            changed = self.tabfix.process_file(filepath, args)
            return changed, []

    def check_file(self, filepath: Path) -> Tuple[bool, List[str]]:
        temp_config = TabFixConfig(**self.config.to_dict())
        temp_config.dry_run = True
        temp_config.check_only = True
        
        class Args:
            def __init__(self, config):
                for key, value in config.to_dict().items():
                    setattr(self, key, value)
        
        args = Args(temp_config)
        
        if hasattr(self.tabfix, 'process_file_with_changes'):
            changed, changes = self.tabfix.process_file_with_changes(filepath, args)
            return changed, changes
        else:
            changed = self.tabfix.process_file(filepath, args)
            return changed, []

    def detect_indentation(self, content: str) -> Dict[str, Any]:
        return self.tabfix.detect_indentation(content)

    def compare_files(self, file1: Path, file2: Path) -> Dict[str, Any]:
        class Args:
            quiet = True
            no_color = True
        
        args = Args()
        return self.tabfix.compare_files_indentation(file1, file2)

    def get_available_formatters(self) -> List[str]:
        try:
            from .unifmt.formatters import Formatter, FormatterManager
            config = type('Config', (), {})()
            manager = FormatterManager(config)
            return [f.value for f in manager._available_formatters]
        except ImportError:
            return []


def fix_string(content: str, spaces: int = 4, **kwargs) -> Tuple[str, List[str]]:
    config = TabFixConfig(spaces=spaces, **kwargs)
    api = TabFixAPI(config)
    return api.fix_string(content)


def fix_file(filepath: Path, spaces: int = 4, **kwargs) -> Tuple[bool, List[str]]:
    config = TabFixConfig(spaces=spaces, **kwargs)
    api = TabFixAPI(config)
    return api.fix_file(filepath)


def check_file(filepath: Path, spaces: int = 4, **kwargs) -> Tuple[bool, List[str]]:
    config = TabFixConfig(spaces=spaces, **kwargs)
    config.dry_run = True
    config.check_only = True
    api = TabFixAPI(config)
    return api.check_file(filepath)


def detect_indentation(content: str) -> Dict[str, Any]:
    api = TabFixAPI()
    return api.detect_indentation(content)


def create_config_file(filepath: Path, config: Optional[TabFixConfig] = None):
    config = config or TabFixConfig()
    with open(filepath, 'w') as f:
        json.dump(config.to_dict(), f, indent=2)