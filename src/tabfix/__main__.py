#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path

from .core import TabFix, Colors, print_color, GitignoreMatcher
from .config import TabFixConfig, ConfigLoader, init_project
from .autoformat import get_available_formatters, create_autoformat_config, Formatter, FileProcessor


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Advanced tab/space indentation fixer with autoformatting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tabfix --init                    # Create .tabfixrc config file
  tabfix --init-autoformat         # Create autoformat config
  tabfix --autoformat              # Autoformat files using external tools
  tabfix --check-format            # Check formatting without changes
  tabfix --list-formatters         # List available formatters
  tabfix --recursive --remove-bom  # Process recursively, remove BOM
  tabfix --git-staged --interactive # Interactive mode on staged files
  tabfix --diff file1.py file2.py  # Compare indentation
""",
    )

    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or directories to process"
    )

    parser.add_argument(
        "-s", "--spaces",
        type=int,
        default=4,
        help="Number of spaces per tab (default: 4)"
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Process directories recursively"
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

    autoformat_group = parser.add_argument_group("Autoformatting")
    autoformat_group.add_argument(
        "--autoformat",
        "-a",
        action="store_true",
        help="Autoformat files using external formatters"
    )
    autoformat_group.add_argument(
        "--check-format",
        action="store_true",
        help="Check formatting without making changes"
    )
    autoformat_group.add_argument(
        "--list-formatters",
        action="store_true",
        help="List available formatters and exit"
    )
    autoformat_group.add_argument(
        "--formatters",
        help="Comma-separated list of formatters to use (e.g. black,isort)"
    )
    autoformat_group.add_argument(
        "--init-autoformat",
        action="store_true",
        help="Initialize autoformat configuration file"
    )

    encoding_group = parser.add_argument_group("Encoding and binary file handling")
    encoding_group.add_argument(
        "--skip-binary",
        action="store_true",
        default=True,
        help="Skip files that appear to be binary (default: True)"
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

    formatting_group = parser.add_argument_group("Formatting options")
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

    mode_group = parser.add_argument_group("Operation mode")
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
        "--diff",
        nargs=2,
        metavar=("FILE1", "FILE2"),
        help="Compare indentation between two files"
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
        "--init",
        action="store_true",
        help="Initialize configuration file (.tabfixrc)"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to configuration file"
    )
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="Ignore configuration files"
    )

    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    if args.no_color:
        global Colors
        Colors = type("Colors", (), {k: "" for k in dir(Colors) if not k.startswith("_")})()

    if args.init:
        success = init_project(Path.cwd())
        sys.exit(0 if success else 1)

    if args.init_autoformat:
        config_path = create_autoformat_config()
        print_color(f"Created autoformat config: {config_path}", Colors.GREEN)
        sys.exit(0)

    if args.list_formatters:
        formatters = get_available_formatters()
        print_color("Available formatters:", Colors.BOLD)
        for formatter in formatters:
            print_color(f"  ✓ {formatter}", Colors.GREEN)
        if not formatters:
            print_color("  No formatters found. Install tools like black, prettier, etc.", Colors.YELLOW)
        sys.exit(0)

    if args.remove_bom and args.keep_bom:
        print_color("Cannot use both --remove-bom and --keep-bom", Colors.RED)
        sys.exit(1)

    if args.autoformat and args.check_format:
        print_color("Cannot use both --autoformat and --check-format", Colors.RED)
        sys.exit(1)

    fixer = TabFix(spaces_per_tab=args.spaces)
    file_processor = None

    if args.autoformat or args.check_format:
        file_processor = FileProcessor(spaces_per_tab=args.spaces)
        if args.formatters:
            try:
                formatter_list = [Formatter(f.strip()) for f in args.formatters.split(',')]
                args.formatter_list = formatter_list
            except ValueError as e:
                print_color(f"Invalid formatter: {e}", Colors.RED)
                sys.exit(1)
        else:
            args.formatter_list = None

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

    try:
        from tqdm import tqdm
        if args.progress and not args.interactive:
            iterator = tqdm(processed_files, desc="Processing", unit="file", disable=args.quiet)
        else:
            iterator = processed_files
    except ImportError:
        iterator = processed_files

    autoformat_stats = {"formatted": 0, "failed": 0, "checked": 0}

    for filepath in iterator:
        file_changed = fixer.process_file(filepath, args, gitignore_matcher)

        if file_processor and (args.autoformat or args.check_format):
            if args.verbose:
                mode = "Checking" if args.check_format else "Formatting"
                print_color(f"{mode} {filepath}", Colors.CYAN)

            success, messages = file_processor.process_file(
                filepath,
                formatters=args.formatter_list,
                check_only=args.check_format
            )

            if args.check_format:
                autoformat_stats["checked"] += 1
                if not success and args.verbose:
                    for msg in messages:
                        print_color(f"  ✗ {msg}", Colors.RED)
            elif args.autoformat:
                if success:
                    autoformat_stats["formatted"] += 1
                    if args.verbose:
                        for msg in messages:
                            print_color(f"  ✓ {msg}", Colors.GREEN)
                else:
                    autoformat_stats["failed"] += 1
                    if args.verbose:
                        for msg in messages:
                            print_color(f"  ✗ {msg}", Colors.RED)

    fixer.print_stats(args)

    if args.autoformat or args.check_format:
        print_color(f"\n{'='*60}", Colors.CYAN)
        print_color("AUTOFORMAT STATISTICS", Colors.BOLD + Colors.CYAN)
        print_color(f"{'='*60}", Colors.CYAN)

        if args.check_format:
            print_color(f"Files checked: {autoformat_stats['checked']}", Colors.BLUE)
        else:
            print_color(f"Files formatted: {autoformat_stats['formatted']}", Colors.GREEN)
            if autoformat_stats['failed'] > 0:
                print_color(f"Files failed: {autoformat_stats['failed']}", Colors.RED)


if __name__ == "__main__":
    main()
