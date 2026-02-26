"""
tabfix.autoformat — external formatter integration.

Fixes:
  [BUG-F1] rustfmt: added --check flag for check-only mode.
  [BUG-F2] yapf:    --diff for check mode, -i for fix mode (was missing both).
  [BUG-F3] gofmt:   -w flag for write mode (was writing to stdout only),
                    -l flag for check mode (list files that need changes).
  [BUG-F4] autopep8: added --diff flag for check mode.
"""

import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
import json
import os


class Formatter(Enum):
    BLACK       = "black"
    AUTOPEP8    = "autopep8"
    ISORT       = "isort"
    PRETTIER    = "prettier"
    RUFF        = "ruff"
    YAPF        = "yapf"
    CLANGFORMAT = "clang-format"
    GOFMT       = "gofmt"
    RUSTFMT     = "rustfmt"


class FormatterManager:
    def __init__(self, spaces_per_tab: int = 4) -> None:
        self.spaces_per_tab = spaces_per_tab
        self._available: Set[Formatter] = set()
        self._detect()

    def _detect(self) -> None:
        for fmt in Formatter:
            if shutil.which(fmt.value) is not None:
                self._available.add(fmt)

    def is_available(self, fmt: Formatter) -> bool:
        return fmt in self._available

    def get_available_formatters(self) -> List[str]:
        return sorted(f.value for f in self._available)

    def format_file(
        self,
        filepath:   Path,
        formatters: List[Formatter],
        check_only: bool = False,
    ) -> Tuple[bool, List[str]]:
        results: List[Tuple[bool, str]] = []
        for fmt in formatters:
            if self.is_available(fmt):
                fn = self._check if check_only else self._apply
                results.append(fn(filepath, fmt))
            else:
                results.append((False, f"{fmt.value}: not installed"))

        success  = any(ok for ok, _ in results)
        messages = [msg for _, msg in results if msg]
        return success, messages

    def _apply(self, filepath: Path, fmt: Formatter) -> Tuple[bool, str]:
        cmd = self._build_cmd(filepath, fmt, fix=True)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                return True, f"Formatted with {fmt.value}"
            err = (r.stderr or r.stdout or "unknown error")[:200]
            return False, f"{fmt.value}: {err}"
        except subprocess.TimeoutExpired:
            return False, f"{fmt.value}: timeout"
        except Exception as e:
            return False, f"{fmt.value}: {e}"

    def _check(self, filepath: Path, fmt: Formatter) -> Tuple[bool, str]:
        cmd = self._build_cmd(filepath, fmt, fix=False)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            # gofmt -l: outputs filename if reformatting is needed; exit code is always 0
            if fmt == Formatter.GOFMT:
                needs_fmt = bool(r.stdout.strip())
                return not needs_fmt, ("Needs formatting (gofmt)" if needs_fmt else "OK (gofmt)")
            # Most other formatters exit 0 = clean, non-0 = needs formatting
            if r.returncode == 0:
                return True, f"OK ({fmt.value})"
            return False, f"Needs formatting ({fmt.value})"
        except subprocess.TimeoutExpired:
            return False, f"{fmt.value}: timeout"
        except Exception as e:
            return False, f"{fmt.value}: {e}"

    def _build_cmd(self, filepath: Path, fmt: Formatter, fix: bool) -> List[str]:
        fp = str(filepath)

        if fmt == Formatter.BLACK:
            cmd = ["black"]
            if not fix:
                cmd.append("--check")
            cmd.append(fp)

        elif fmt == Formatter.RUFF:
            if fix:
                cmd = ["ruff", "format", fp]
            else:
                cmd = ["ruff", "format", "--check", fp]

        elif fmt == Formatter.ISORT:
            cmd = ["isort"]
            if not fix:
                cmd.append("--check-only")
            cmd.append(fp)

        elif fmt == Formatter.PRETTIER:
            cmd = ["prettier"]
            if not fix:
                cmd.append("--check")
            cmd.append(fp)

        elif fmt == Formatter.CLANGFORMAT:
            if fix:
                cmd = ["clang-format", "-i", fp]
            else:
                cmd = ["clang-format", "--dry-run", "-Werror", fp]

        elif fmt == Formatter.GOFMT:
            # [BUG-F3] -w writes in-place; -l lists files needing changes
            if fix:
                cmd = ["gofmt", "-w", fp]
            else:
                cmd = ["gofmt", "-l", fp]

        elif fmt == Formatter.RUSTFMT:
            # [BUG-F1] --check prevents in-place modification
            if fix:
                cmd = ["rustfmt", fp]
            else:
                cmd = ["rustfmt", "--check", fp]

        elif fmt == Formatter.YAPF:
            # [BUG-F2] -i for in-place; --diff for check (exits 1 if different)
            if fix:
                cmd = ["yapf", "-i", fp]
            else:
                cmd = ["yapf", "--diff", fp]

        elif fmt == Formatter.AUTOPEP8:
            # [BUG-F4] --diff for check mode; -i for fix mode
            if fix:
                cmd = ["autopep8", "-i", fp]
            else:
                cmd = ["autopep8", "--diff", fp]

        else:
            cmd = [fmt.value, fp]

        return cmd


class FileProcessor:
    """Maps file extensions to the appropriate external formatters."""

    def __init__(self, spaces_per_tab: int = 4) -> None:
        self.spaces_per_tab   = spaces_per_tab
        self.formatter_manager = FormatterManager(spaces_per_tab)
        self.default_formatters: Dict[str, List[Formatter]] = {
            ".py":    [Formatter.BLACK, Formatter.ISORT],
            ".js":    [Formatter.PRETTIER],
            ".jsx":   [Formatter.PRETTIER],
            ".ts":    [Formatter.PRETTIER],
            ".tsx":   [Formatter.PRETTIER],
            ".json":  [Formatter.PRETTIER],
            ".md":    [Formatter.PRETTIER],
            ".html":  [Formatter.PRETTIER],
            ".css":   [Formatter.PRETTIER],
            ".yaml":  [Formatter.PRETTIER],
            ".yml":   [Formatter.PRETTIER],
            ".go":    [Formatter.GOFMT],
            ".rs":    [Formatter.RUSTFMT],
            ".cpp":   [Formatter.CLANGFORMAT],
            ".c":     [Formatter.CLANGFORMAT],
            ".java":  [Formatter.CLANGFORMAT],
        }

    def get_formatters_for_file(
        self,
        filepath:        Path,
        user_formatters: Optional[List[Formatter]] = None,
    ) -> List[Formatter]:
        if user_formatters:
            return user_formatters
        return self.default_formatters.get(filepath.suffix.lower(), [])

    def process_file(
        self,
        filepath:        Path,
        formatters:      Optional[List[Formatter]] = None,
        check_only:      bool                      = False,
    ) -> Tuple[bool, List[str]]:
        fmts = self.get_formatters_for_file(filepath, formatters)
        if not fmts:
            return False, ["No formatters configured for this file type"]
        return self.formatter_manager.format_file(filepath, fmts, check_only)

def get_available_formatters() -> List[str]:
    """Return names of all currently installed formatters."""
    return FormatterManager().get_available_formatters()


def create_autoformat_config(filepath: Path = Path(".tabfix-autoformat.json")) -> Path:
    """Write a default autoformat configuration file and return its path."""
    config = {
        "formatters": {
            "python":     ["black", "isort"],
            "javascript": ["prettier"],
            "typescript": ["prettier"],
            "json":       ["prettier"],
            "markdown":   ["prettier"],
            "yaml":       ["prettier"],
            "html":       ["prettier"],
            "css":        ["prettier"],
            "go":         ["gofmt"],
            "rust":       ["rustfmt"],
            "c_cpp":      ["clang-format"],
        },
        "exclude_patterns": [
            "**/node_modules/**",
            "**/.git/**",
            "**/__pycache__/**",
            "**/*.pyc",
            "**/.venv/**",
            "**/venv/**",
        ],
    }
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)
    return filepath
