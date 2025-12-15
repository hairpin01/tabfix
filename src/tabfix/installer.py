#!/usr/bin/env python3
import sys
import subprocess
import os
from typing import Optional


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


def is_interactive() -> bool:
    return sys.stdin.isatty()


def check_tabfix_installed() -> bool:
    try:
        subprocess.run([sys.executable, "-c", "import tabfix"], 
                      capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def run_command(cmd: str) -> bool:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            if result.stderr:
                print_color(f"Error: {result.stderr}", Colors.RED)
            return False
        
        if result.stdout:
            print_color(result.stdout, Colors.BLUE)
        
        return True
    except Exception as e:
        print_color(f"Failed to run command: {e}", Colors.RED)
        return False


def install_or_update() -> bool:
    if check_tabfix_installed():
        print_color("Updating tabfix from PyPI...", Colors.BLUE)
        return run_command(f"{sys.executable} -m pip install --upgrade tabfix-tool")
    else:
        print_color("Installing tabfix from PyPI...", Colors.BLUE)
        return run_command(f"{sys.executable} -m pip install tabfix-tool")


def main():
    print_color("tabfix package installer", Colors.BOLD + Colors.CYAN)
    print_color("=" * 40, Colors.CYAN)
    
    if not is_interactive():
        print_color("Non-interactive mode detected", Colors.BLUE)
        success = install_or_update()
    else:
        print_color("\nInstallation methods:", Colors.BOLD)
        print_color("1. Install/update from PyPI (recommended)")
        print_color("2. Install from GitHub")
        print_color("3. Install editable from current directory")
        print_color("4. Clone from GitHub and install")
        print_color("5. Check current installation")
        
        try:
            choice = input("\nSelect method (1-5): ").strip()
        except (EOFError, KeyboardInterrupt):
            print_color("\nInstallation cancelled.", Colors.YELLOW)
            sys.exit(0)
        
        if choice == "1":
            success = install_or_update()
        elif choice == "2":
            print_color("Installing from GitHub...", Colors.BLUE)
            success = run_command(f"{sys.executable} -m pip install git+https://github.com/hairpin01/tabfix.git")
        elif choice == "3":
            print_color("Installing editable from current directory...", Colors.BLUE)
            success = run_command(f"{sys.executable} -m pip install -e .")
        elif choice == "4":
            print_color("Cloning and installing from GitHub...", Colors.BLUE)
            success = run_command("git clone https://github.com/hairpin01/tabfix.git && cd tabfix && pip install -e .")
        elif choice == "5":
            print_color("Checking installation...", Colors.BLUE)
            success = check_tabfix_installed()
            if success:
                print_color("✓ tabfix is installed", Colors.GREEN)
            else:
                print_color("✗ tabfix is not installed", Colors.RED)
            return success
        else:
            print_color("Invalid choice.", Colors.RED)
            sys.exit(1)
    
    if success:
        print_color("\n✓ Success!", Colors.GREEN + Colors.BOLD)
        print_color("\nUsage:", Colors.CYAN)
        print_color("  tabfix [options] <file>")
        print_color("  tabfix --help")
        return True
    else:
        print_color("\n✗ Failed.", Colors.RED)
        sys.exit(1)


if __name__ == "__main__":
    main()