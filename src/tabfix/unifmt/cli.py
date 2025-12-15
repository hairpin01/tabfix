#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path

from .config import ConfigLoader, create_default_config, init_project, ProjectConfig, FileTypeConfig
from .formatters import FormatterManager, Formatter
from .collector import FileCollector
from .report import ReportGenerator


class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    END = "\033[0m"
    BOLD = "\033[1m"


def print_color(text: str, color: str = Colors.END, end: str = "\n"):
    if sys.stdout.isatty():
        print(f"{color}{text}{Colors.END}", end=end)
    else:
        print(text, end=end)


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
  unifmt --list-formatters        # List available formatters
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

    formatter_manager = FormatterManager(project_config)

    if args.list_formatters:
        print_color("Available formatters:", Colors.BOLD)
        for formatter, installed, version in formatter_manager.check_formatter_dependencies():
            if installed:
                print_color(f"  ✓ {formatter} ({version})", Colors.GREEN)
            else:
                print_color(f"  ✗ {formatter}", Colors.DIM)
        return

    collector = FileCollector(project_config)
    reporter = ReportGenerator()

    files = collector.collect_files()

    if args.verbose:
        print_color(f"Found {len(files)} files to process", Colors.BLUE)
        print_color(f"Available formatters: {formatter_manager.get_available_formatters()}", Colors.DIM)

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
            reporter.add_result(skipped=True)
            continue

        if args.verbose:
            mode = "Checking" if project_config.check_only else "Formatting"
            print_color(f"{mode} {file_path}", Colors.CYAN)

        results = formatter_manager.format_file(file_path, file_type, project_config.check_only)

        any_failed = False
        any_success = False

        for result in results:
            if result.success:
                any_success = True
                if args.verbose:
                    print_color(f"  ✓ {result.formatter.value}", Colors.GREEN)
            else:
                any_failed = True
                if args.verbose:
                    status = "Needs formatting" if result.requires_formatting else "Failed"
                    print_color(f"  ✗ {result.formatter.value} ({status})", Colors.RED)
                    if result.message and args.verbose:
                        print_color(f"    {result.message}", Colors.DIM)

        if any_failed:
            reporter.add_result(failed=True)
        elif any_success and not project_config.check_only:
            reporter.add_result(formatted=True)
        elif any_success and project_config.check_only:
            # For check mode, success means no formatting needed
            reporter.add_result(unchanged=True)
        else:
            reporter.add_result(skipped=True)

    print_color("\n" + reporter.generate_report(verbose=args.verbose), Colors.BOLD)

    if reporter.has_failures():
        sys.exit(1)
    elif project_config.check_only and reporter.needs_formatting():
        print_color("\n✗ Some files need formatting", Colors.RED)
        sys.exit(1)
    elif project_config.check_only:
        print_color("\n✓ All files are properly formatted", Colors.GREEN)


if __name__ == "__main__":
    main()
