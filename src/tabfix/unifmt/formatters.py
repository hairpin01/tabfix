import subprocess
import shutil
from pathlib import Path
from typing import List, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


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


@dataclass
class FormatResult:
    success: bool
    formatter: Formatter
    message: str = ""
    requires_formatting: bool = False


class FormatterManager:
    def __init__(self, config):
        self.config = config
        self._available_formatters: Set[Formatter] = set()
        self._detect_formatters()

    def _detect_formatters(self):
        formatter_commands = {
            Formatter.BLACK: ["black", "--version"],
            Formatter.AUTOPEP8: ["autopep8", "--version"],
            Formatter.ISORT: ["isort", "--version"],
            Formatter.PRETTIER: ["prettier", "--version"],
            Formatter.RUFF: ["ruff", "--version"],
            Formatter.YAPF: ["yapf", "--version"],
            Formatter.CLANGFORMAT: ["clang-format", "--version"],
            Formatter.GOFMT: ["gofmt", "-h"],
            Formatter.RUSTFMT: ["rustfmt", "--version"],
        }

        for formatter, cmd in formatter_commands.items():
            if shutil.which(cmd[0]) is not None:
                self._available_formatters.add(formatter)

    def get_available_formatters(self) -> List[str]:
        return [f.value for f in self._available_formatters]

    def is_formatter_available(self, formatter: Formatter) -> bool:
        return formatter in self._available_formatters

    def format_file(self, file_path: Path, file_config, check_only: bool = False) -> List[FormatResult]:
        results = []

        for formatter in file_config.formatters:
            if self.is_formatter_available(formatter):
                if check_only:
                    result = self._check_formatting(file_path, formatter, file_config)
                else:
                    result = self._apply_formatter(file_path, formatter, file_config)
                results.append(result)

        return results

    def _apply_formatter(self, file_path: Path, formatter: Formatter, file_config) -> FormatResult:
        cmd = self._build_formatter_command(file_path, formatter, file_config, fix=True)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return FormatResult(success=True, formatter=formatter)
            else:
                error_msg = result.stderr[:200] if result.stderr else "Unknown error"
                return FormatResult(success=False, formatter=formatter, message=error_msg)
        except subprocess.TimeoutExpired:
            return FormatResult(success=False, formatter=formatter, message="Timeout")
        except Exception as e:
            return FormatResult(success=False, formatter=formatter, message=str(e))

    def _check_formatting(self, file_path: Path, formatter: Formatter, file_config) -> FormatResult:
        cmd = self._build_formatter_command(file_path, formatter, file_config, fix=False)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return FormatResult(success=True, formatter=formatter)
            else:
                return FormatResult(
                    success=False,
                    formatter=formatter,
                    requires_formatting=True,
                    message="File needs formatting"
                )
        except subprocess.TimeoutExpired:
            return FormatResult(success=False, formatter=formatter, message="Timeout")
        except Exception as e:
            return FormatResult(success=False, formatter=formatter, message=str(e))

    def _build_formatter_command(self, file_path: Path, formatter: Formatter,
                                file_config, fix: bool) -> List[str]:
        base_cmd = [formatter.value]

        if formatter == Formatter.BLACK:
            if not fix:
                base_cmd.append("--check")
            if file_config.line_length:
                base_cmd.extend(["--line-length", str(file_config.line_length)])
            base_cmd.append(str(file_path))

        elif formatter == Formatter.RUFF:
            if fix:
                base_cmd.extend(["format", str(file_path)])
            else:
                base_cmd.extend(["format", "--check", str(file_path)])
            if file_config.line_length:
                base_cmd.extend(["--line-length", str(file_config.line_length)])

        elif formatter == Formatter.ISORT:
            if not fix:
                base_cmd.append("--check-only")
            if file_config.line_length:
                base_cmd.extend(["--line-length", str(file_config.line_length)])
            base_cmd.append(str(file_path))

        elif formatter == Formatter.PRETTIER:
            if not fix:
                base_cmd.append("--check")
            if file_config.indent_size:
                base_cmd.extend(["--tab-width", str(file_config.indent_size)])
            base_cmd.append(str(file_path))

        elif formatter == Formatter.CLANGFORMAT:
            if not fix:
                base_cmd.extend(["--dry-run", "-Werror"])
            base_cmd.append(str(file_path))

        elif formatter == Formatter.GOFMT:
            if not fix:
                base_cmd.append("-d")
            base_cmd.append(str(file_path))

        else:
            base_cmd.append(str(file_path))

        return base_cmd

    def check_formatter_dependencies(self) -> List[Tuple[str, bool, str]]:
        """Check all formatters and return their status."""
        results = []

        for formatter in Formatter:
            is_available = self.is_formatter_available(formatter)
            if is_available:
                try:
                    result = subprocess.run([formatter.value, "--version"],
                                          capture_output=True, text=True)
                    version = result.stdout.strip() if result.stdout else "Unknown"
                    results.append((formatter.value, True, version))
                except:
                    results.append((formatter.value, True, "Installed"))
            else:
                results.append((formatter.value, False, "Not installed"))

        return results
