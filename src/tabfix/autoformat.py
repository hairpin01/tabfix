import subprocess
import shutil
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Set
from enum import Enum
import json
import os


class Formatter(Enum):
    BLACK = "black"
    AUTOPEP8 = "autopep8"
    ISORT = "isort"
    PRETTIER = "prettier"
    RUFF = "ruff"
    YAPF = "yapf"
    CLANGFORMAT = "clang-format"
    GOFMT = "gofmt"
    RUSTFMT = "rustfmt"


class FormatterManager:
    def __init__(self, spaces_per_tab: int = 4):
        self.spaces_per_tab = spaces_per_tab
        self._available_formatters: Set[Formatter] = set()
        self._detect_formatters()

    def _detect_formatters(self):
        for formatter in Formatter:
            if shutil.which(formatter.value) is not None:
                self._available_formatters.add(formatter)

    def is_formatter_available(self, formatter: Formatter) -> bool:
        return formatter in self._available_formatters

    def get_available_formatters(self) -> List[str]:
        return [f.value for f in self._available_formatters]

    def format_file(self, filepath: Path, formatters: List[Formatter], check_only: bool = False) -> Tuple[bool, List[str]]:
        results = []
        for formatter in formatters:
            if self.is_formatter_available(formatter):
                if check_only:
                    result = self._check_formatting(filepath, formatter)
                else:
                    result = self._apply_formatter(filepath, formatter)
                results.append(result)
            else:
                results.append((False, f"Formatter {formatter.value} not available"))

        success = any(success for success, _ in results)
        messages = [msg for _, msg in results if msg]
        return success, messages

    def _apply_formatter(self, filepath: Path, formatter: Formatter) -> Tuple[bool, str]:
        cmd = self._build_formatter_command(filepath, formatter, fix=True)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return True, f"Formatted with {formatter.value}"
            else:
                error_msg = result.stderr[:200] if result.stderr else "Unknown error"
                return False, f"{formatter.value}: {error_msg}"
        except subprocess.TimeoutExpired:
            return False, f"{formatter.value}: Timeout"
        except Exception as e:
            return False, f"{formatter.value}: {str(e)}"

    def _check_formatting(self, filepath: Path, formatter: Formatter) -> Tuple[bool, str]:
        cmd = self._build_formatter_command(filepath, formatter, fix=False)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return True, f"OK ({formatter.value})"
            else:
                return False, f"Needs formatting ({formatter.value})"
        except subprocess.TimeoutExpired:
            return False, f"{formatter.value}: Timeout"
        except Exception as e:
            return False, f"{formatter.value}: {str(e)}"

    def _build_formatter_command(self, filepath: Path, formatter: Formatter, fix: bool) -> List[str]:
        base_cmd = [formatter.value]

        if formatter == Formatter.BLACK:
            if not fix:
                base_cmd.append("--check")
            base_cmd.append(str(filepath))

        elif formatter == Formatter.RUFF:
            if fix:
                base_cmd.extend(["format", str(filepath)])
            else:
                base_cmd.extend(["format", "--check", str(filepath)])

        elif formatter == Formatter.ISORT:
            if not fix:
                base_cmd.append("--check-only")
            base_cmd.append(str(filepath))

        elif formatter == Formatter.PRETTIER:
            if not fix:
                base_cmd.append("--check")
            base_cmd.append(str(filepath))

        elif formatter == Formatter.CLANGFORMAT:
            if not fix:
                base_cmd.extend(["--dry-run", "-Werror"])
            base_cmd.append(str(filepath))

        elif formatter == Formatter.GOFMT:
            if not fix:
                base_cmd.append("-d")
            base_cmd.append(str(filepath))

        else:
            base_cmd.append(str(filepath))

        return base_cmd


class FileProcessor:
    def __init__(self, spaces_per_tab: int = 4):
        self.spaces_per_tab = spaces_per_tab
        self.formatter_manager = FormatterManager(spaces_per_tab)
        self.default_formatters = {
            '.py': [Formatter.BLACK, Formatter.ISORT],
            '.js': [Formatter.PRETTIER],
            '.jsx': [Formatter.PRETTIER],
            '.ts': [Formatter.PRETTIER],
            '.tsx': [Formatter.PRETTIER],
            '.json': [Formatter.PRETTIER],
            '.md': [Formatter.PRETTIER],
            '.html': [Formatter.PRETTIER],
            '.css': [Formatter.PRETTIER],
            '.yaml': [Formatter.PRETTIER],
            '.yml': [Formatter.PRETTIER],
            '.go': [Formatter.GOFMT],
            '.rs': [Formatter.RUSTFMT],
            '.cpp': [Formatter.CLANGFORMAT],
            '.c': [Formatter.CLANGFORMAT],
            '.java': [Formatter.CLANGFORMAT],
        }

    def get_formatters_for_file(self, filepath: Path, user_formatters: Optional[List[Formatter]] = None) -> List[Formatter]:
        if user_formatters:
            return user_formatters

        suffix = filepath.suffix.lower()
        return self.default_formatters.get(suffix, [])

    def process_file(self, filepath: Path, formatters: Optional[List[Formatter]] = None, check_only: bool = False) -> Tuple[bool, List[str]]:
        formatters_to_use = self.get_formatters_for_file(filepath, formatters)
        if not formatters_to_use:
            return False, ["No formatters configured for this file type"]

        return self.formatter_manager.format_file(filepath, formatters_to_use, check_only)


def get_available_formatters() -> List[str]:
    manager = FormatterManager()
    return manager.get_available_formatters()


def create_autoformat_config(filepath: Path = Path(".tabfix-autoformat.json")):
    default_config = {
        "formatters": {
            "python": ["black", "isort"],
            "javascript": ["prettier"],
            "typescript": ["prettier"],
            "json": ["prettier"],
            "markdown": ["prettier"],
            "yaml": ["prettier"],
            "html": ["prettier"],
            "css": ["prettier"],
            "go": ["gofmt"],
            "rust": ["rustfmt"],
            "c_cpp": ["clang-format"],
        },
        "exclude_patterns": [
            "**/node_modules/**",
            "**/.git/**",
            "**/__pycache__/**",
            "**/*.pyc",
            "**/.venv/**",
            "**/venv/**",
        ]
    }

    with open(filepath, 'w') as f:
        json.dump(default_config, f, indent=2)
    return filepath
