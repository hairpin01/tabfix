#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path
from typing import List, Optional

from .core import TabFix, Colors, print_color
from .config import TabFixConfig, ConfigLoader


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Advanced tab/space indentation fixer with extended features",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Configuration:
  tabfix will look for configuration files in the following order:
  1. .tabfixrc, .tabfixrc.json, .tabfixrc.toml, .tabfixrc.yaml
  2. pyproject.toml (in [tool.tabfix] section)
  3. tabfix.json

  Command line arguments override configuration file settings.

Examples:
  tabfix --init                    # Create .tabfixrc config file
  tabfix --pre-commit              # Generate pre-commit hook config
  tabfix --recursive --remove-bom  # Process recursively, remove BOM
  tabfix --git-staged --interactive # Interactive mode on staged files
""",
    )


    config_group = parser.add_argument_group("Configuration")
    config_group.add_argument(
        "--config",
        type=Path,
        help="Path to configuration file"
    )
    config_group.add_argument(
        "--no-config",
        action="store_true",
        help="Ignore configuration files"
    )
    config_group.add_argument(
        "--init",
        action="store_true",
        help="Initialize configuration file (.tabfixrc)"
    )
    config_group.add_argument(
        "--show-config",
        action="store_true",
        help="Show current configuration and exit"
    )


    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or directories to process"
    )

    formatting_group = parser.add_argument_group("Formatting options")
    formatting_group.add_argument(
        "-s", "--spaces",
        type=int,
        help="Number of spaces per tab (default: 4)"
    )
    formatting_group.add_argument(
        "-m", "--fix-mixed",
        action="store_true",
        help="Fix mixed tabs/spaces indentation"
    )
    formatting_group.add_argument(
        "-t", "--fix-trailing",
        action="store_true",
        help="Remove trailing whitespace"
    )
    formatting_group.add_argument(
        "-f", "--final-newline",
        action="store_true",
        help="Ensure file ends with newline"
    )
    formatting_group.add_argument(
        "--remove-bom",
        action="store_true",
        help="Remove UTF-8 BOM marker"
    )
    formatting_group.add_argument(
        "--keep-bom",
        action="store_true",
        help="Preserve existing BOM marker"
    )
    formatting_group.add_argument(
        "--format-json",
        action="store_true",
        help="Format JSON files with proper indentation"
    )


    git_group = parser.add_argument_group("Git integration")
    git_group.add_argument(
        "--git-staged",
        action="store_true",
        help="Process only staged files in git"
    )
    git_group.add_argument(
        "--git-unstaged",
        action="store_true",
        help="Process only unstaged files in git"
    )
    git_group.add_argument(
        "--git-all-changed",
        action="store_true",
        help="Process all changed files in git"
    )
    git_group.add_argument(
        "--no-gitignore",
        action="store_true",
        help="Do not use .gitignore patterns"
    )

    # Encoding and file handling
    encoding_group = parser.add_argument_group("Encoding and file handling")
    encoding_group.add_argument(
        "--skip-binary",
        action="store_true",
        help="Skip files that appear to be binary"
    )
    encoding_group.add_argument(
        "--no-skip-binary",
        action="store_false",
        dest="skip_binary",
        help="Process files even if they appear to be binary"
    )
    encoding_group.add_argument(
        "--force-encoding",
        help="Force specific encoding (skip auto-detection)"
    )
    encoding_group.add_argument(
        "--fallback-encoding",
        default="latin-1",
        help="Fallback encoding when detection fails (default: latin-1)"
    )
    encoding_group.add_argument(
        "--warn-encoding",
        action="store_true",
        help="Warn when encoding detection is uncertain"
    )
    encoding_group.add_argument(
        "--max-file-size",
        type=int,
        default=10 * 1024 * 1024,
        help="Maximum file size to process in bytes (default: 10MB)"
    )


    filetype_group = parser.add_argument_group("File type specific processing")
    filetype_group.add_argument(
        "--smart-processing",
        action="store_true",
        default=True,
        help="Enable smart processing for different file types (default: True)"
    )
    filetype_group.add_argument(
        "--no-smart-processing",
        action="store_false",
        dest="smart_processing",
        help="Disable smart processing for different file types"
    )
    filetype_group.add_argument(
        "--preserve-quotes",
        action="store_true",
        help="Preserve original string quotes in code files"
    )


    mode_group = parser.add_argument_group("Operation mode")
    mode_group.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Process directories recursively"
    )
    mode_group.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Interactive mode (confirm each change)"
    )
    mode_group.add_argument(
        "--progress",
        action="store_true",
        help="Show progress bar during processing"
    )
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without modifying files"
    )
    mode_group.add_argument(
        "--backup",
        action="store_true",
        help="Create backup files (.bak)"
    )
    mode_group.add_argument(
        "--pre-commit",
        action="store_true",
        help="Generate pre-commit hook configuration"
    )


    output_group = parser.add_argument_group("Output control")
    output_group.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    output_group.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Quiet mode (minimal output)"
    )
    output_group.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output"
    )

    parser.add_argument(
        "--diff",
        nargs=2,
        metavar=("FILE1", "FILE2"),
        help="Compare indentation between two files"
    )

    return parser


def init_config() -> bool:
    config = TabFixConfig()
    config_path = Path.cwd() / ".tabfixrc"

    if config_path.exists():
        print_color(f"Configuration file already exists at {config_path}", Colors.YELLOW)
        response = input("Overwrite? (y/n): ").lower().strip()
        if response != "y":
            return False

    if ConfigLoader.save_config(config, config_path):
        print_color(f"✓ Created configuration file: {config_path}", Colors.GREEN)
        return True
    else:
        print_color("✗ Failed to create configuration file", Colors.RED)
        return False


def generate_pre_commit_config() -> bool:
    try:
        from tabfix import __version__
    except ImportError:
        __version__ = "latest"

    config = f"""repos:
  - repo: https://github.com/hairpin01/tabfix
    rev: v{__version__}
    hooks:
      - id: tabfix
        name: tabfix
        entry: tabfix
        args: [--fix-mixed, --fix-trailing, --final-newline]
        language: python
        types: [python, javascript, json, yaml, markdown, html, css]
        stages: [commit]
"""

    config_path = Path.cwd() / ".pre-commit-config.yaml"

    if config_path.exists():
        print_color(f"pre-commit config already exists at {config_path}", Colors.YELLOW)
        response = input("Overwrite? (y/n): ").lower().strip()
        if response != "y":
            return False

    with open(config_path, "w") as f:
        f.write(config)

    print_color(f"✓ Created pre-commit config: {config_path}", Colors.GREEN)
    print_color("\nTo use this configuration:", Colors.CYAN)
    print_color("1. Install pre-commit: pip install pre-commit")
    print_color("2. Install the hook: pre-commit install")
    print_color("3. Run on all files: pre-commit run --all-files")

    return True


def show_config(config: TabFixConfig, config_path: Optional[Path] = None):
    print_color("Current Configuration:", Colors.BOLD + Colors.CYAN)
    if config_path:
        print_color(f"Loaded from: {config_path}", Colors.BLUE)

    config_dict = config.to_dict()
    for key, value in sorted(config_dict.items()):
        if value is not None:
            if isinstance(value, bool):
                value_str = "✓" if value else "✗"
                color = Colors.GREEN if value else Colors.RED
            else:
                value_str = str(value)
                color = Colors.BLUE

            key_str = key.replace("_", " ").title()
            print_color(f"  {key_str:20} : {color}{value_str}{Colors.END}")


def load_configuration(args) -> TabFixConfig:
    config = TabFixConfig()

    if not args.no_config:
        config_path = args.config
        if not config_path:
            config_path = ConfigLoader.find_config_file(Path.cwd())

        if config_path and config_path.exists():
            try:
                config_data = ConfigLoader.load_config(config_path)
                file_config = TabFixConfig.from_dict(config_data)


                config = file_config

                if args.verbose:
                    print_color(f"Loaded configuration from: {config_path}", Colors.CYAN)
            except Exception as e:
                if not args.quiet:
                    print_color(f"Error loading config {config_path}: {e}", Colors.YELLOW)


    config.update_from_args(args)

    return config


def main():
    parser = create_parser()
    args = parser.parse_args()

    if args.no_color:
        global Colors
        Colors = type("Colors", (), {k: "" for k in dir(Colors) if not k.startswith("_")})()


    if args.init:
        sys.exit(0 if init_config() else 1)

    if args.pre_commit:
        sys.exit(0 if generate_pre_commit_config() else 1)

    if args.show_config:
        config = load_configuration(args)
        show_config(config)
        sys.exit(0)


    config = load_configuration(args)


    for key, value in config.to_dict().items():
        if hasattr(args, key) and getattr(args, key) is None:
            setattr(args, key, value)


    if args.remove_bom and args.keep_bom:
        print_color("Cannot use both --remove-bom and --keep-bom", Colors.RED)
        sys.exit(1)


    fixer = TabFix(spaces_per_tab=args.spaces)


    if args.diff:
        file1 = Path(args.diff[0])
        file2 = Path(args.diff[1])
        fixer.compare_files(file1, file2, args)
        return


    files_to_process = []


    if args.git_staged or args.git_unstaged or args.git_all_changed:
        if args.git_staged:
            files = fixer.get_git_files("staged")
        elif args.git_unstaged:
            files = fixer.get_git_files("unstaged")
        else:
            files = fixer.get_git_files("all_changed")
        files_to_process.extend(files)
    else:

        for path_str in args.paths:
            path = Path(path_str)

            if not path.exists():
                if not args.quiet:
                    print_color(f"Warning: Path not found: {path}", Colors.YELLOW)
                continue

            if path.is_file():
                files_to_process.append(path)
            elif path.is_dir():
                if args.recursive:
                    pattern = "**/*"
                else:
                    pattern = "*"

                for filepath in path.glob(pattern):
                    if filepath.is_file():
                        files_to_process.append(filepath)

    if not files_to_process:
        if not args.quiet:
            print_color("No files to process", Colors.YELLOW)
        return


    gitignore_matcher = None
    if not args.no_gitignore and files_to_process:
        root_dir = Path.cwd()
        for filepath in files_to_process:
            if filepath.is_absolute():
                potential_root = filepath.parent
            else:
                potential_root = (Path.cwd() / filepath).parent

            gitignore_path = potential_root / ".gitignore"
            if gitignore_path.exists():
                root_dir = potential_root
                break

        gitignore_matcher = GitignoreMatcher(root_dir)
        if args.verbose:
            print_color(f"Using .gitignore from: {root_dir}", Colors.CYAN)


    processed_files = []
    for filepath in files_to_process:
        if gitignore_matcher and gitignore_matcher.should_ignore(filepath):
            continue
        processed_files.append(filepath)

    if args.verbose and gitignore_matcher:
        skipped = len(files_to_process) - len(processed_files)
        if skipped > 0:
            print_color(f"Skipping {skipped} files due to .gitignore", Colors.DIM)

    if not processed_files:
        if not args.quiet:
            print_color("No files to process after applying .gitignore", Colors.YELLOW)
        return


    from tqdm import tqdm

    if args.progress and not args.interactive:
        iterator = tqdm(processed_files, desc="Processing", unit="file", disable=args.quiet)
    else:
        iterator = processed_files

    for filepath in iterator:
        fixer.process_file(filepath, args, gitignore_matcher)

    fixer.print_stats(args)


if __name__ == "__main__":
    main()
