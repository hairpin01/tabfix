#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path

from .core import TabFix, Colors, print_color, GitignoreMatcher
from .config import TabFixConfig, ConfigLoader, init_project


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Advanced tab/space indentation fixer with extended features",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tabfix --init                    # Create .tabfixrc config file
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
    
    parser.add_argument(
        "--diff",
        nargs=2,
        metavar=("FILE1", "FILE2"),
        help="Compare indentation between two files"
    )
    parser.add_argument(
        "--format-json",
        action="store_true",
        help="Format JSON files with proper indentation"
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Interactive mode (confirm each change)"
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show progress bar during processing"
    )
    parser.add_argument(
        "--remove-bom",
        action="store_true",
        help="Remove UTF-8 BOM marker"
    )
    parser.add_argument(
        "--keep-bom",
        action="store_true",
        help="Preserve existing BOM marker"
    )
    
    parser.add_argument(
        "-m", "--fix-mixed",
        action="store_true",
        help="Fix mixed tabs/spaces indentation"
    )
    parser.add_argument(
        "-t", "--fix-trailing",
        action="store_true",
        help="Remove trailing whitespace"
    )
    parser.add_argument(
        "-f", "--final-newline",
        action="store_true",
        help="Ensure file ends with newline"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without modifying files"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create backup files (.bak)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Quiet mode (minimal output)"
    )
    parser.add_argument(
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
    
    try:
        from tqdm import tqdm
        if args.progress and not args.interactive:
            iterator = tqdm(processed_files, desc="Processing", unit="file", disable=args.quiet)
        else:
            iterator = processed_files
    except ImportError:
        iterator = processed_files
    
    for filepath in iterator:
        fixer.process_file(filepath, args, gitignore_matcher)
    
    fixer.print_stats(args)


if __name__ == "__main__":
    main()
