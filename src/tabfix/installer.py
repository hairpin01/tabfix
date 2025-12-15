#!/usr/bin/env python3
import sys
import subprocess
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


def run_command(cmd: str) -> bool:
    try:
        print_color(f"Running: {cmd}", Colors.CYAN)
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


def check_pip_installed() -> bool:
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], 
                      capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_from_pypi() -> bool:
    return run_command(f"{sys.executable} -m pip install tabfix-tool")


def install_from_git() -> bool:
    return run_command(f"{sys.executable} -m pip install git+https://github.com/hairpin01/tabfix.git")


def install_editable() -> bool:
    return run_command(f"{sys.executable} -m pip install -e .")


def clone_and_install() -> bool:
    return run_command("git clone https://github.com/hairpin01/tabfix.git && cd tabfix && pip install -e .")


def check_installation() -> bool:
    try:
        subprocess.run([sys.executable, "-c", "import tabfix"], 
                      capture_output=True, check=True)
        print_color("✓ tabfix is installed and importable", Colors.GREEN)
        
        subprocess.run(["tabfix", "--version"], capture_output=True, check=True)
        print_color("✓ tabfix CLI is available", Colors.GREEN)
        return True
    except subprocess.CalledProcessError:
        print_color("✗ tabfix is not installed or not importable", Colors.RED)
        return False


def main():
    print_color("tabfix package installer", Colors.BOLD + Colors.CYAN)
    print_color("=" * 40, Colors.CYAN)
    
    if not check_pip_installed():
        print_color("pip is not installed. Please install pip first.", Colors.RED)
        sys.exit(1)
    
    methods = {
        "1": ("Install from PyPI", install_from_pypi),
        "2": ("Install from GitHub", install_from_git),
        "3": ("Install editable from current directory", install_editable),
        "4": ("Clone from GitHub and install", clone_and_install),
        "5": ("Check current installation", check_installation),
    }
    
    print_color("\nInstallation methods:", Colors.BOLD)
    for key, (description, _) in methods.items():
        print_color(f"{key}. {description}")
    
    if len(sys.argv) > 1:
        choice = sys.argv[1]
        print_color(f"\nUsing command line argument: {choice}", Colors.BLUE)
    else:
        try:
            choice = input("\nSelect method (1-5): ").strip()
        except (EOFError, KeyboardInterrupt):
            print_color("\nInstallation cancelled.", Colors.YELLOW)
            sys.exit(0)
    
    if choice not in methods:
        print_color("Invalid choice.", Colors.RED)
        sys.exit(1)
    
    description, installer_func = methods[choice]
    print_color(f"\n{description}...", Colors.BLUE)
    
    success = installer_func()
    
    if success:
        print_color("\n✓ Success!", Colors.GREEN + Colors.BOLD)
        if choice != "5":
            print_color("\nUsage:", Colors.CYAN)
            print_color("  tabfix [options] <file>")
            print_color("  tabfix --help")
    else:
        print_color("\n✗ Failed.", Colors.RED)
        sys.exit(1)


if __name__ == "__main__":
    main()