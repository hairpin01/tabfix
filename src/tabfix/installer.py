#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
from pathlib import Path
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


def run_command(cmd: str, cwd: Optional[Path] = None) -> bool:
    try:
        print_color(f"Running: {cmd}", Colors.CYAN)
        result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
        
        if result.returncode != 0:
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
    cwd = Path.cwd()
    setup_py = cwd / "setup.py"
    pyproject = cwd / "pyproject.toml"
    
    if not setup_py.exists() and not pyproject.exists():
        print_color("No setup.py or pyproject.toml found in current directory", Colors.RED)
        return False
    
    return run_command(f"{sys.executable} -m pip install -e .")


def clone_and_install() -> bool:
    temp_dir = Path("/tmp") / "tabfix_install"
    
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    if not run_command("git clone https://github.com/hairpin01/tabfix.git", temp_dir):
        return False
    
    repo_dir = temp_dir / "tabfix"
    
    if not (repo_dir / "setup.py").exists() and not (repo_dir / "pyproject.toml").exists():
        print_color("Cloned repository doesn't contain setup files", Colors.RED)
        return False
    
    return run_command(f"{sys.executable} -m pip install -e .", repo_dir)


def check_installation() -> bool:
    try:
        subprocess.run([sys.executable, "-c", "import tabfix"], 
                      capture_output=True, check=True)
        print_color("✓ tabfix is installed and importable", Colors.GREEN)
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
    
    print_color("\nInstallation methods:", Colors.BOLD)
    print_color("1. Install from PyPI (pip install tabfix-tool)")
    print_color("2. Install from GitHub (pip install git+https://...)")
    print_color("3. Install editable from current directory")
    print_color("4. Clone from GitHub and install editable")
    print_color("5. Check current installation")
    
    try:
        choice = input("\nSelect method (1-5): ").strip()
    except (EOFError, KeyboardInterrupt):
        print_color("\nInstallation cancelled.", Colors.YELLOW)
        sys.exit(0)
    
    success = False
    
    if choice == "1":
        print_color("\nInstalling from PyPI...", Colors.BLUE)
        success = install_from_pypi()
    elif choice == "2":
        print_color("\nInstalling from GitHub...", Colors.BLUE)
        success = install_from_git()
    elif choice == "3":
        print_color("\nInstalling editable from current directory...", Colors.BLUE)
        success = install_editable()
    elif choice == "4":
        print_color("\nCloning and installing from GitHub...", Colors.BLUE)
        success = clone_and_install()
    elif choice == "5":
        print_color("\nChecking installation...", Colors.BLUE)
        success = check_installation()
    else:
        print_color("Invalid choice.", Colors.RED)
        sys.exit(1)
    
    if success:
        print_color("\n✓ Installation successful!", Colors.GREEN + Colors.BOLD)
        print_color("\nUsage:", Colors.CYAN)
        print_color("  tabfix [options] <file>")
        print_color("  tabfix --help")
    else:
        print_color("\n✗ Installation failed.", Colors.RED)
        sys.exit(1)


if __name__ == "__main__":
    main()