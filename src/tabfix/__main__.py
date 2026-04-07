#!/usr/bin/env python3
"""
tabfix.__main__ — CLI entry point.

Fixes:
  [BUG-M1] --no-color: previously only shadowed Colors in this module's
            namespace.  Now calls core.disable_colors() so the flag
            actually works across all modules.
  [BUG-M2] --autoformat and --check-format conflict check was missing from
            the refactored flow (kept from original but verified it works).

New features:
  [NEW-M1] --normalize-endings  (CRLF → LF)
  [NEW-M2] --check-only         (CI mode: exit 1 if any file needs changes)
  [NEW-M3] --json-report PATH   (machine-readable stats)
"""

import sys
import os
import argparse
from pathlib import Path

from .core import TabFix, Colors, print_color, GitignoreMatcher, disable_colors
from .config import TabFixConfig, ConfigLoader, init_project
from .autoformat import get_available_formatters, create_autoformat_config, Formatter, FileProcessor


def create_pre_commit_hook(root: Path, spaces: int) -> bool:
    git_dir = root / ".git"
    hook_path = git_dir / "hooks" / "pre-commit"
    if not git_dir.exists():
        return False
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = f'tabfix --check-only --recursive --fix-mixed --fix-trailing --normalize-endings --format-json --spaces {spaces} .'
    script = f"#!/usr/bin/env bash\n{cmd}\nstatus=$?\nif [ $status -ne 0 ]; then\n  echo \"tabfix: fix issues before commit\" >&2\nfi\nexit $status\n"
    try:
        hook_path.write_text(script, encoding="utf-8")
        os.chmod(hook_path, 0o755)
        return True
    except OSError:
        return False

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Advanced tab/space indentation fixer with autoformatting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tabfix --init                          # Create .tabfixrc config file
  tabfix --init-autoformat               # Create autoformat config
  tabfix --autoformat                    # Autoformat with external tools
  tabfix --check-format                  # Check formatting (no changes)
  tabfix --list-formatters               # Show available formatters
  tabfix -r --fix-mixed --fix-trailing . # Fix indentation recursively
  tabfix --git-staged --interactive      # Interactive mode on staged files
  tabfix --diff file1.py file2.py        # Compare indentation
  tabfix --check-only -r src/            # CI: exit 1 if any file needs changes
  tabfix --normalize-endings -r .        # Convert CRLF to LF
  tabfix --json-report stats.json -r .   # Save stats to JSON
""",
    )

    parser.add_argument(
        "paths", nargs="*", default=["."],
        help="Files or directories to process",
    )
    parser.add_argument("-s", "--spaces",    type=int, default=4,
                        help="Spaces per tab (default: 4)")
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="Process directories recursively")

    git = parser.add_argument_group("Git integration")
    git.add_argument("--git-staged",      action="store_true", help="Process staged files only")
    git.add_argument("--git-unstaged",    action="store_true", help="Process unstaged files only")
    git.add_argument("--git-all-changed", action="store_true", help="Process all changed files")
    git.add_argument("--no-gitignore",    action="store_true", help="Ignore .gitignore patterns")
    git.add_argument("--install-pre-commit", action="store_true",
                     help="Install a Git pre-commit hook that runs tabfix in check-only mode")

    af = parser.add_argument_group("Autoformatting")
    af.add_argument("--autoformat",      "-a", action="store_true",
                    help="Autoformat files using external formatters")
    af.add_argument("--check-format",          action="store_true",
                    help="Check formatting without making changes")
    af.add_argument("--list-formatters",       action="store_true",
                    help="List available formatters and exit")
    af.add_argument("--formatters",
                    help="Comma-separated list of formatters to use (e.g. black,isort)")
    af.add_argument("--init-autoformat",       action="store_true",
                    help="Create autoformat config file")

    enc = parser.add_argument_group("Encoding and binary file handling")
    enc.add_argument("--skip-binary",      action="store_true", default=True,
                     help="Skip binary files (default: True)")
    enc.add_argument("--no-skip-binary",   action="store_false", dest="skip_binary",
                     help="Process even binary-looking files")
    enc.add_argument("--force-encoding",   help="Force a specific encoding")
    enc.add_argument("--fallback-encoding", default="latin-1",
                     help="Fallback encoding (default: latin-1)")
    enc.add_argument("--warn-encoding",    action="store_true",
                     help="Warn when encoding detection is uncertain")
    enc.add_argument("--max-file-size",    type=int, default=10 * 1024 * 1024,
                     help="Maximum file size to process in bytes (default: 10 MB)")

    ft = parser.add_argument_group("File type specific processing")
    ft.add_argument("--smart-processing",    action="store_true", default=True,
                    help="Smart per-extension processing (default: True)")
    ft.add_argument("--no-smart-processing", action="store_false", dest="smart_processing",
                    help="Disable smart per-extension processing")
    ft.add_argument("--preserve-quotes",     action="store_true",
                    help="Preserve original string quotes in code files")
    ft.add_argument("--respect-strings",     action="store_true",
                    help="Skip indentation fixes inside Python triple-quoted strings/docstrings")
    ft.add_argument("--detect-spaces",       action="store_true",
                    help="Auto-detect dominant indent width from project files before running")

    fmt = parser.add_argument_group("Formatting options")
    fmt.add_argument("-m", "--fix-mixed",         action="store_true",
                     help="Fix mixed tabs/spaces indentation")
    fmt.add_argument("-t", "--fix-trailing",       action="store_true",
                     help="Remove trailing whitespace")
    fmt.add_argument("-f", "--final-newline",      action="store_true",
                     help="Ensure file ends with a newline")
    fmt.add_argument("--remove-bom",               action="store_true",
                     help="Remove UTF-8 BOM marker")
    fmt.add_argument("--keep-bom",                 action="store_true",
                     help="Preserve existing BOM marker")
    fmt.add_argument("--format-json",              action="store_true",
                     help="Format JSON files with proper indentation")
    fmt.add_argument("--normalize-endings",        action="store_true",   # [NEW-M1]
                     help="Convert CRLF (\\r\\n) and stray CR (\\r) to LF (\\n)")

    mode = parser.add_argument_group("Operation mode")
    mode.add_argument("-i", "--interactive", action="store_true",
                      help="Interactive mode (confirm each change)")
    mode.add_argument("--progress",          action="store_true",
                      help="Show progress bar during processing")
    mode.add_argument("--dry-run",           action="store_true",
                      help="Show changes without modifying files")
    mode.add_argument("--check-only",        action="store_true",  # [NEW-M2]
                      help="Like --dry-run but exits with code 1 if any file needs changes (CI)")
    mode.add_argument("--backup",            action="store_true",
                      help="Create .bak backup before modifying")
    mode.add_argument("--diff", nargs=2, metavar=("FILE1", "FILE2"),
                      help="Compare indentation between two files")

    out = parser.add_argument_group("Output control")
    out.add_argument("-v", "--verbose",    action="store_true", help="Verbose output")
    out.add_argument("-q", "--quiet",      action="store_true", help="Minimal output")
    out.add_argument("--no-color",         action="store_true", help="Disable colored output")
    out.add_argument("--json-report",      metavar="PATH",      # [NEW-M3]
                     help="Write machine-readable stats to a JSON file")

    parser.add_argument("--init",      action="store_true",
                        help="Create .tabfixrc config file in current directory")
    parser.add_argument("--config",    type=Path,
                        help="Path to configuration file")
    parser.add_argument("--no-config", action="store_true",
                        help="Ignore all configuration files")

    return parser

def main() -> None:
    parser = create_parser()
    args   = parser.parse_args()

    # [BUG-M1] Use the module-level disable_colors() so it applies everywhere
    if args.no_color:
        disable_colors()

    if args.init:
        sys.exit(0 if init_project(Path.cwd()) else 1)

    if args.init_autoformat:
        path = create_autoformat_config()
        print_color(f"Created autoformat config: {path}", Colors.GREEN)
        sys.exit(0)

    if args.list_formatters:
        fmts = get_available_formatters()
        print_color("Available formatters:", Colors.BOLD)
        for f in fmts:
            print_color(f"  ✓ {f}", Colors.GREEN)
        if not fmts:
            print_color("  None found. Install black, prettier, gofmt, etc.", Colors.YELLOW)
        sys.exit(0)

    if args.remove_bom and args.keep_bom:
        print_color("Cannot use both --remove-bom and --keep-bom", Colors.RED)
        sys.exit(1)

    if args.autoformat and args.check_format:
        print_color("Cannot use both --autoformat and --check-format", Colors.RED)
        sys.exit(1)

    if args.dry_run and args.check_only:
        print_color("--dry-run and --check-only are redundant; using --check-only", Colors.YELLOW)
        args.dry_run = False

    if args.install_pre_commit:
        ok = create_pre_commit_hook(Path.cwd(), args.spaces)
        if ok:
            print_color("Installed .git/hooks/pre-commit for tabfix", Colors.GREEN)
            sys.exit(0)
        else:
            print_color("Failed to install pre-commit hook (is this a git repo?)", Colors.RED)
            sys.exit(1)

    files_to_process = []
    finder = TabFix(spaces_per_tab=args.spaces)

    if args.git_staged or args.git_unstaged or args.git_all_changed:
        mode = ("staged"      if args.git_staged
                else "unstaged" if args.git_unstaged
                else "all_changed")
        files_to_process = finder.get_git_files(mode)
    else:
        for path_str in args.paths:
            path = Path(path_str)
            if not path.exists():
                if not args.quiet:
                    print_color(f"Warning: path not found: {path}", Colors.YELLOW)
                continue
            if path.is_file():
                files_to_process.append(path)
            elif path.is_dir():
                pattern = "**/*" if args.recursive else "*"
                files_to_process.extend(p for p in path.glob(pattern) if p.is_file())

    if not files_to_process:
        if not args.quiet:
            print_color("No files to process", Colors.YELLOW)
        return

    gitignore_matcher = None
    if not args.no_gitignore:
        root = Path.cwd()
        for fp in files_to_process:
            cand = (fp if fp.is_absolute() else Path.cwd() / fp).parent
            if (cand / ".gitignore").exists():
                root = cand
                break
        gitignore_matcher = GitignoreMatcher(root)
        if args.verbose:
            print_color(f"Using .gitignore from: {root}", Colors.CYAN)

    processed = [
        fp for fp in files_to_process
        if not gitignore_matcher or not gitignore_matcher.should_ignore(fp)
    ]

    if args.verbose and gitignore_matcher:
        skipped = len(files_to_process) - len(processed)
        if skipped:
            print_color(f"Skipping {skipped} file(s) due to .gitignore", Colors.DIM)

    if not processed:
        if not args.quiet:
            print_color("No files to process after .gitignore filter", Colors.YELLOW)
        return

    # Auto-detect indent width if requested
    if args.detect_spaces:
        detector = TabFix(spaces_per_tab=args.spaces)
        detected = detector.detect_spaces_from_files(processed)
        if detected:
            args.spaces = detected
            if not args.quiet:
                print_color(f"Auto-detected indent: {detected} spaces", Colors.CYAN)

    fixer          = TabFix(spaces_per_tab=args.spaces)
    file_processor = None

    if args.autoformat or args.check_format:
        file_processor = FileProcessor(spaces_per_tab=args.spaces)
        if args.formatters:
            try:
                args.formatter_list = [Formatter(f.strip()) for f in args.formatters.split(",")]
            except ValueError as e:
                print_color(f"Invalid formatter: {e}", Colors.RED)
                sys.exit(1)
        else:
            args.formatter_list = None

    if args.diff:
        fixer.compare_files(Path(args.diff[0]), Path(args.diff[1]), args)
        return

    try:
        from tqdm import tqdm as _tqdm
        iterator = (
            _tqdm(processed, desc="Processing", unit="file", disable=args.quiet)
            if args.progress and not args.interactive
            else processed
        )
    except ImportError:
        iterator = processed

    af_stats = {"formatted": 0, "failed": 0, "checked": 0}

    for filepath in iterator:
        fixer.process_file(filepath, args, gitignore_matcher)

        if file_processor and (args.autoformat or args.check_format):
            if args.verbose:
                verb = "Checking" if args.check_format else "Formatting"
                print_color(f"  {verb}: {filepath}", Colors.CYAN)

            ok, msgs = file_processor.process_file(
                filepath,
                formatters=args.formatter_list,
                check_only=args.check_format,
            )

            if args.check_format:
                af_stats["checked"] += 1
                if not ok and args.verbose:
                    for m in msgs:
                        print_color(f"    ✗ {m}", Colors.RED)
            else:
                if ok:
                    af_stats["formatted"] += 1
                    if args.verbose:
                        for m in msgs:
                            print_color(f"    ✓ {m}", Colors.GREEN)
                else:
                    af_stats["failed"] += 1
                    if args.verbose:
                        for m in msgs:
                            print_color(f"    ✗ {m}", Colors.RED)

    fixer.print_stats(args)

    if args.autoformat or args.check_format:
        print_color(f"\n{'='*60}", Colors.CYAN)
        print_color("AUTOFORMAT STATISTICS", Colors.BOLD + Colors.CYAN)
        print_color(f"{'='*60}", Colors.CYAN)
        if args.check_format:
            print_color(f"Files checked:    {af_stats['checked']}", Colors.BLUE)
        else:
            print_color(f"Files formatted:  {af_stats['formatted']}", Colors.GREEN)
            if af_stats["failed"]:
                print_color(f"Files failed:     {af_stats['failed']}", Colors.RED)

    # [NEW-M2] Exit 1 in check-only mode when any file would change
    if args.check_only and fixer.stats["files_would_change"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
