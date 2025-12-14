#!/usr/bin/env python3
import os
import sys
import subprocess
import hashlib
import tempfile
import difflib
import shutil
from pathlib import Path
from typing import Optional, Tuple, List
import urllib.request
import urllib.error

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    END = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

def print_color(text: str, color: str = Colors.END, end: str = '\n'):
    if sys.stdout.isatty():
        print(f"{color}{text}{Colors.END}", end=end)
    else:
        print(text, end=end)

def get_shell_config_file(shell: str) -> Optional[Path]:
    home = Path.home()
    
    shell_configs = {
        'zsh': home / '.zshrc',
        'bash': home / '.bashrc',
        'bash_profile': home / '.bash_profile',
        'bash_login': home / '.bash_login',
        'profile': home / '.profile',
        'sh': home / '.profile',
        'dash': home / '.profile',
        'ksh': home / '.kshrc',
        'tcsh': home / '.tcshrc',
        'csh': home / '.cshrc',
        'fish': home / '.config/fish/config.fish'
    }
    
    if shell == 'bash':
        for config in ['bashrc', 'bash_profile', 'bash_login', 'profile']:
            config_path = shell_configs[config]
            if config_path.exists():
                return config_path
    
    config_path = shell_configs.get(shell)
    if config_path and config_path.exists():
        return config_path
    
    return None

def detect_shell() -> str:
    shell_path = os.environ.get('SHELL', '')
    if not shell_path:
        return 'bash'
    
    shell_name = Path(shell_path).name.lower()
    
    known_shells = ['zsh', 'bash', 'sh', 'dash', 'ksh', 'tcsh', 'csh', 'fish']
    for known in known_shells:
        if known in shell_name:
            return known
    
    return 'bash'

def download_script(url: str) -> Optional[bytes]:
    try:
        headers = {'User-Agent': 'tabfix-installer/1.0'}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status == 200:
                return response.read()
            else:
                print_color(f"Failed to download script: HTTP {response.status}", Colors.RED)
                return None
    except urllib.error.URLError as e:
        print_color(f"Network error: {e}", Colors.RED)
        return None
    except Exception as e:
        print_color(f"Download error: {e}", Colors.RED)
        return None

def find_existing_installation() -> Tuple[Optional[Path], Optional[str]]:
    script_name = "tabfix"
    
    possible_locations = [
        Path('/usr/local/bin') / script_name,
        Path('/usr/bin') / script_name,
        Path.home() / '.local/bin' / script_name,
        Path.home() / 'bin' / script_name,
        Path.cwd() / script_name,
    ]
    
    for location in possible_locations:
        if location.exists() and location.is_file() and os.access(location, os.X_OK):
            return location, 'binary'
    
    home = Path.home()
    shell = detect_shell()
    config_file = get_shell_config_file(shell)
    
    if config_file and config_file.exists():
        try:
            content = config_file.read_text()
            alias_patterns = [
                f'alias {script_name}=',
                f'alias {script_name} =',
                f"alias {script_name}='",
                f'alias {script_name}="'
            ]
            
            for pattern in alias_patterns:
                if pattern in content:
                    return config_file, 'alias'
        except:
            pass
    
    return None, None

def get_file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

def compare_scripts(old_path: Path, new_content: bytes) -> List[str]:
    try:
        with open(old_path, 'rb') as f:
            old_content = f.read()
        
        if old_content == new_content:
            return []
        
        old_lines = old_content.decode('utf-8', errors='ignore').splitlines()
        new_lines = new_content.decode('utf-8', errors='ignore').splitlines()
        
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=str(old_path),
            tofile='new version',
            lineterm=''
        )
        
        return list(diff)
    except Exception as e:
        print_color(f"Error comparing scripts: {e}", Colors.YELLOW)
        return []

def install_as_alias(script_path: Path, shell: str, config_file: Optional[Path] = None) -> bool:
    if not config_file:
        config_file = get_shell_config_file(shell)
        if not config_file:
            print_color(f"Could not find config file for {shell}", Colors.RED)
            print_color("Please specify config file path:", Colors.CYAN)
            custom_path = input("> ").strip()
            if not custom_path:
                return False
            config_file = Path(custom_path).expanduser()
    
    alias_line = f"\nalias tabfix='{script_path.absolute()}'\n"
    
    try:
        content = config_file.read_text()
        
        if 'alias tabfix=' in content:
            print_color(f"Alias already exists in {config_file}", Colors.YELLOW)
            
            lines = content.splitlines()
            new_lines = []
            for line in lines:
                if line.strip().startswith('alias tabfix='):
                    continue
                new_lines.append(line)
            
            new_content = '\n'.join(new_lines) + alias_line
            backup_path = config_file.with_suffix(config_file.suffix + '.backup')
            shutil.copy2(config_file, backup_path)
            print_color(f"Backup created at {backup_path}", Colors.BLUE)
        else:
            new_content = content.rstrip() + alias_line
        
        config_file.write_text(new_content)
        print_color(f"Alias added to {config_file}", Colors.GREEN)
        
        print_color("\nYou need to reload your shell config:", Colors.CYAN)
        print_color(f"  source {config_file}", Colors.BOLD)
        return True
        
    except Exception as e:
        print_color(f"Error adding alias: {e}", Colors.RED)
        return False

def install_as_binary(script_path: Path, install_path: Path) -> bool:
    try:
        if install_path.exists():
            backup_path = install_path.with_suffix(install_path.suffix + '.backup')
            shutil.copy2(install_path, backup_path)
            print_color(f"Backup created at {backup_path}", Colors.BLUE)
        
        shutil.copy2(script_path, install_path)
        install_path.chmod(0o755)
        print_color(f"Installed to {install_path}", Colors.GREEN)
        return True
    except PermissionError:
        print_color(f"Permission denied. Try with sudo?", Colors.RED)
        return False
    except Exception as e:
        print_color(f"Error installing binary: {e}", Colors.RED)
        return False

def choose_installation_method() -> str:
    print_color("\nChoose installation method:", Colors.CYAN)
    print_color("1. Alias (adds to shell config)", Colors.BOLD)
    print_color("2. System-wide (/usr/local/bin)", Colors.BOLD)
    print_color("3. User local (~/.local/bin)", Colors.BOLD)
    print_color("4. Current directory", Colors.BOLD)
    print_color("5. Custom location", Colors.BOLD)
    
    while True:
        choice = input("\nEnter choice (1-5): ").strip()
        if choice in ['1', '2', '3', '4', '5']:
            return choice
        print_color("Invalid choice. Enter 1-5.", Colors.RED)

def get_install_location(method: str) -> Optional[Path]:
    if method == '2':
        return Path('/usr/local/bin/tabfix')
    elif method == '3':
        local_bin = Path.home() / '.local' / 'bin'
        local_bin.mkdir(parents=True, exist_ok=True)
        return local_bin / 'tabfix'
    elif method == '4':
        return Path.cwd() / 'tabfix'
    elif method == '5':
        print_color("Enter full path for installation:", Colors.CYAN)
        custom_path = input("> ").strip()
        if custom_path:
            return Path(custom_path).expanduser()
        return None
    return None

def check_path_in_path(install_path: Path) -> bool:
    path_dirs = os.environ.get('PATH', '').split(':')
    return str(install_path.parent) in path_dirs

def main():
    print_color("tabfix installer", Colors.BOLD + Colors.CYAN)
    
    SCRIPT_URL = "https://raw.githubusercontent.com/hairpin01/tabfix/refs/heads/main/src/tabfix/tabfix" 
    
    existing_path, install_type = find_existing_installation()
    
    if existing_path:
        print_color(f"Found existing installation:", Colors.GREEN)
        print_color(f"  Location: {existing_path}", Colors.BLUE)
        print_color(f"  Type: {install_type}", Colors.BLUE)
        
        response = input("\nUpdate existing installation? (y/n): ").lower().strip()
        if response not in ['y', 'yes']:
            print_color("Installation cancelled.", Colors.YELLOW)
            return
    else:
        print_color("No existing installation found.", Colors.BLUE)
    
    print_color("\nDownloading tabfix script...", Colors.CYAN)
    script_content = download_script(SCRIPT_URL)
    
    if not script_content:
        print_color("Failed to download script. Using local version if available.", Colors.YELLOW)
        
        local_script = Path(__file__).parent / 'tabfix'
        if local_script.exists():
            script_content = local_script.read_bytes()
            print_color(f"Using local script: {local_script}", Colors.GREEN)
        else:
            print_color("No script available for installation.", Colors.RED)
            return
    
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.py') as tmp:
        tmp.write(script_content)
        temp_path = Path(tmp.name)
    
    temp_path.chmod(0o755)
    
    if existing_path and install_type == 'binary':
        diffs = compare_scripts(existing_path, script_content)
        if diffs:
            print_color("\nChanges in new version:", Colors.CYAN)
            for line in diffs[:20]:
                if line.startswith('+'):
                    print_color(line, Colors.GREEN)
                elif line.startswith('-'):
                    print_color(line, Colors.RED)
                else:
                    print_color(line, Colors.DIM)
            
            if len(diffs) > 20:
                print_color(f"... and {len(diffs) - 20} more lines", Colors.DIM)
            
            response = input("\nApply these changes? (y/n): ").lower().strip()
            if response not in ['y', 'yes']:
                temp_path.unlink()
                print_color("Update cancelled.", Colors.YELLOW)
                return
            
            install_method = '2'
            install_location = existing_path
        else:
            print_color("No changes detected. Already up to date.", Colors.GREEN)
            temp_path.unlink()
            return
    else:
        install_choice = choose_installation_method()
        
        if install_choice == '1':
            shell = detect_shell()
            print_color(f"\nDetected shell: {shell}", Colors.BLUE)
            
            config_file = get_shell_config_file(shell)
            if config_file:
                print_color(f"Config file: {config_file}", Colors.BLUE)
            else:
                print_color(f"No config file found for {shell}", Colors.YELLOW)
            
            response = input(f"Install as alias in {config_file}? (y/n): ").lower().strip()
            if response not in ['y', 'yes']:
                print_color("Installation cancelled.", Colors.YELLOW)
                temp_path.unlink()
                return
            
            if install_as_alias(temp_path, shell, config_file):
                temp_path.unlink()
                return
            else:
                print_color("Falling back to other installation methods...", Colors.YELLOW)
                install_choice = choose_installation_method()
        
        if install_choice in ['2', '3', '4', '5']:
            install_location = get_install_location(install_choice)
            if not install_location:
                print_color("Invalid installation location.", Colors.RED)
                temp_path.unlink()
                return
            
            if install_location.exists():
                response = input(f"Overwrite {install_location}? (y/n): ").lower().strip()
                if response not in ['y', 'yes']:
                    print_color("Installation cancelled.", Colors.YELLOW)
                    temp_path.unlink()
                    return
            
            if install_as_binary(temp_path, install_location):
                if install_choice in ['2', '3']:
                    if not check_path_in_path(install_location):
                        print_color("\nWarning: Installation directory not in PATH", Colors.YELLOW)
                        print_color(f"Add {install_location.parent} to your PATH", Colors.CYAN)
                
                print_color("\nInstallation successful!", Colors.GREEN + Colors.BOLD)
                print_color(f"\nUsage: tabfix [options] <file>", Colors.BLUE)
                print_color("Try: tabfix --help", Colors.BLUE)
            else:
                print_color("Installation failed.", Colors.RED)
    
    try:
        temp_path.unlink()
    except:
        pass

if __name__ == '__main__':
    main()
