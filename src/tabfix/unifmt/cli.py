#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any
import subprocess
import shutil
from dataclasses import dataclass, field
from enum import Enum
import json
import os


class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    END = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"


def print_color(text: str, color: str = Colors.END, end: str = "\n"):
    if sys.stdout.isatty():
        print(f"{color}{text}{Colors.END}", end=end)
    else:
        print(text, end=end)


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
                print_color("TOML support requires tomllib (Python 3.11+) or tomli", Colors.RED)
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


class FormatterManager:
    def __init__(self, config: ProjectConfig):
        self.config = config
        self._available_formatters = set()
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

    def format_file(self, file_path: Path, file_config: FileTypeConfig) -> bool:
        if not self.config.auto_fix and self.config.check_only:
            return self._check_file(file_path, file_config)

        success = True
        for formatter in file_config.formatters:
            if formatter in self._available_formatters:
                if not self._apply_formatter(file_path, formatter, file_config):
                    success = False
                    print_color(f"  ✗ {formatter.value} failed", Colors.RED)
            else:
                print_color(f"  ⚠ {formatter.value} not available", Colors.YELLOW)

        return success

    def _check_file(self, file_path: Path, file_config: FileTypeConfig) -> bool:
        for formatter in file_config.formatters:
            if formatter in self._available_formatters:
                if not self._run_formatter_check(file_path, formatter, file_config):
                    return False
        return True

    def _apply_formatter(self, file_path: Path, formatter: Formatter,
                        file_config: FileTypeConfig) -> bool:
        cmd = self._build_formatter_command(file_path, formatter, file_config, fix=True)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                if result.stderr:
                    print_color(f"    {result.stderr[:200]}", Colors.RED)
                return False
            return True
        except Exception as e:
            print_color(f"    Failed: {e}", Colors.RED)
            return False

    def _run_formatter_check(self, file_path: Path, formatter: Formatter,
                           file_config: FileTypeConfig) -> bool:
        cmd = self._build_formatter_command(file_path, formatter, file_config, fix=False)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return False
            return True
        except Exception:
            return False

    def _build_formatter_command(self, file_path: Path, formatter: Formatter,
                               file_config: FileTypeConfig, fix: bool) -> List[str]:
        base_cmd = [formatter.value]

        if formatter == Formatter.BLACK:
            if not fix:
                base_cmd.append("--check")
            if file_config.line_length:
                base_cmd.extend(["--line-length", str(file_config.line_length)])
            base_cmd.append(str(file_path))

        elif formatter == Formatter.RUFF:
            base_cmd.append("format")
            if not fix:
                base_cmd.append("--check")
            if file_config.line_length:
                base_cmd.extend(["--line-length", str(file_config.line_length)])
            base_cmd.append(str(file_path))

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
                base_cmd.append("--dry-run")
                base_cmd.append("-Werror")
            base_cmd.append(str(file_path))

        elif formatter == Formatter.GOFMT:
            if not fix:
                base_cmd.append("-d")
            base_cmd.append(str(file_path))

        else:
            base_cmd.append(str(file_path))

        return base_cmd


class FileCollector:
    def __init__(self, config: ProjectConfig):
        self.config = config

    def collect_files(self) -> List[Path]:
        all_files = []

        for pattern in self.config.include_patterns or ["**/*"]:
            for file_path in self.config.root_dir.glob(pattern):
                if file_path.is_file() and self._should_include(file_path):
                    all_files.append(file_path)

        return sorted(set(all_files))

    def _should_include(self, file_path: Path) -> bool:
        try:
            rel_path = file_path.relative_to(self.config.root_dir)
        except ValueError:
            return False

        for pattern in self.config.exclude_patterns:
            if self._matches_pattern(rel_path, pattern):
                return False

        if self.config.respect_gitignore:
            if self._is_gitignored(file_path):
                return False

        for file_type in self.config.file_types.values():
            if any(str(rel_path).endswith(ext) for ext in file_type.extensions):
                return True

        return not self.config.file_types

    def _matches_pattern(self, path: Path, pattern: str) -> bool:
        try:
            import fnmatch
            return fnmatch.fnmatch(str(path), pattern)
        except:
            return False

    def _is_gitignored(self, file_path: Path) -> bool:
        git_dir = self._find_git_dir(file_path)
        if not git_dir:
            return False

        try:
            result = subprocess.run(
                ["git", "check-ignore", "-q", str(file_path)],
                cwd=git_dir,
                capture_output=True
            )
            return result.returncode == 0
        except:
            return False

    def _find_git_dir(self, file_path: Path) -> Optional[Path]:
        current = file_path.parent
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        return None


class ReportGenerator:
    def __init__(self):
        self.stats = {
            "total_files": 0,
            "formatted": 0,
            "failed": 0,
            "skipped": 0,
            "unchanged": 0,
        }

    def add_result(self, formatted: bool, failed: bool, skipped: bool):
        self.stats["total_files"] += 1
        if formatted:
            self.stats["formatted"] += 1
        elif failed:
            self.stats["failed"] += 1
        elif skipped:
            self.stats["skipped"] += 1
        else:
            self.stats["unchanged"] += 1

    def generate_report(self) -> str:
        lines = [
            "=" * 50,
            "UNIFMT REPORT",
            "=" * 50,
            f"Total files:     {self.stats['total_files']}",
            f"Formatted:       {self.stats['formatted']}",
            f"Failed:          {self.stats['failed']}",
            f"Skipped:         {self.stats['skipped']}",
            f"Unchanged:       {self.stats['unchanged']}",
        ]

        if self.stats["failed"] > 0:
            lines.append("\n✗ Some files failed to format")

        return "\n".join(lines)


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


def init_project(root_dir: Path):
    config_path = root_dir / "unifmt.toml"

    if config_path.exists():
        print_color(f"Config file already exists at {config_path}", Colors.YELLOW)
        return False

    default_config = create_default_config()

    try:
        import tomli_w
        with open(config_path, "wb") as f:
            tomli_w.dump(default_config, f)
        print_color(f"✓ Created config file at {config_path}", Colors.GREEN)
        print_color("\nYou can now run: unifmt .", Colors.CYAN)
        return True
    except ImportError:
        print_color("Please install tomli-w to create TOML config:", Colors.RED)
        print_color("  pip install tomli-w", Colors.BOLD)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Universal code formatter with multi-tool support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  unifmt .                         # Format all files in current directory
  unifmt --check src/             # Check formatting without changes
  unifmt --init                   # Create config file
  unifmt --verbose *.py           # Verbose output for Python files
""",
    )

    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or directories to format"
    )

    parser.add_argument(
        "--config",
        type=Path,
        help="Path to config file"
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Check formatting without making changes"
    )

    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize project with default config"
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )

    parser.add_argument(
        "--list-formatters",
        action="store_true",
        help="List available formatters"
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output"
    )

    args = parser.parse_args()

    if args.no_color:
        global Colors
        Colors = type("Colors", (), {k: "" for k in dir(Colors) if not k.startswith("_")})()

    if args.init:
        success = init_project(Path.cwd())
        sys.exit(0 if success else 1)

    if args.list_formatters:
        print_color("Available formatters:", Colors.BOLD)
        formatter_manager = FormatterManager(ProjectConfig(root_dir=Path.cwd()))
        for formatter in Formatter:
            if formatter in formatter_manager._available_formatters:
                print_color(f"  ✓ {formatter.value}", Colors.GREEN)
            else:
                print_color(f"  ✗ {formatter.value} (not installed)", Colors.DIM)
        return

    config_loader = ConfigLoader()

    config_path = args.config
    if not config_path:
        config_path = config_loader.find_config_file(Path.cwd())

    config_data = {}
    if config_path:
        if args.verbose:
            print_color(f"Using config: {config_path}", Colors.CYAN)
        config_data = config_loader.load_config(config_path)
    else:
        if args.verbose:
            print_color("No config file found, using defaults", Colors.YELLOW)
        config_data = create_default_config()

    project_config = ProjectConfig(
        root_dir=Path.cwd(),
        file_types={},
        check_only=args.check,
        auto_fix=not args.check,
    )

    for file_type_name, ft_config in config_data.get("file_types", {}).items():
        try:
            formatters = [Formatter(f) for f in ft_config.get("formatters", [])]
            project_config.file_types[file_type_name] = FileTypeConfig(
                extensions=ft_config.get("extensions", []),
                formatters=formatters,
                disabled_rules=ft_config.get("disabled_rules", []),
                line_length=ft_config.get("line_length"),
                indent_size=ft_config.get("indent_size"),
                use_tabs=ft_config.get("use_tabs"),
            )
        except ValueError as e:
            print_color(f"Error in config for {file_type_name}: {e}", Colors.RED)

    project_config.exclude_patterns = config_data.get("exclude_patterns", [])
    project_config.include_patterns = config_data.get("include_patterns", [])
    project_config.default_indent = config_data.get("default_indent", 4)
    project_config.default_line_length = config_data.get("default_line_length", 88)
    project_config.respect_gitignore = config_data.get("respect_gitignore", True)

    collector = FileCollector(project_config)
    formatter = FormatterManager(project_config)
    reporter = ReportGenerator()

    files = collector.collect_files()

    if args.verbose:
        print_color(f"Found {len(files)} files to process", Colors.BLUE)
        print_color(f"Available formatters: {[f.value for f in formatter._available_formatters]}", Colors.DIM)

    if not files:
        print_color("No files to process", Colors.YELLOW)
        return

    for file_path in files:
        file_type = None
        for ft_name, ft_config in project_config.file_types.items():
            if any(file_path.suffix == ext for ext in ft_config.extensions):
                file_type = ft_config
                break

        if not file_type:
            if args.verbose:
                print_color(f"Skipping {file_path}: no matching file type", Colors.DIM)
            reporter.add_result(False, False, True)
            continue

        if args.verbose:
            mode = "Checking" if project_config.check_only else "Formatting"
            print_color(f"{mode} {file_path}", Colors.CYAN)

        try:
            success = formatter.format_file(file_path, file_type)
            if success:
                if project_config.check_only:
                    if args.verbose:
                        print_color(f"  ✓ OK", Colors.GREEN)
                    reporter.add_result(False, False, False)
                else:
                    reporter.add_result(True, False, False)
            else:
                reporter.add_result(False, True, False)
        except Exception as e:
            print_color(f"Error processing {file_path}: {e}", Colors.RED)
            reporter.add_result(False, True, False)

    print_color("\n" + reporter.generate_report(), Colors.BOLD)

    if reporter.stats["failed"] > 0:
        sys.exit(1)
    elif project_config.check_only and reporter.stats["formatted"] > 0:
        print_color("\n✗ Some files need formatting", Colors.RED)
        sys.exit(1)
    elif project_config.check_only:
        print_color("\n✓ All files are properly formatted", Colors.GREEN)


if __name__ == "__main__":
    main()
