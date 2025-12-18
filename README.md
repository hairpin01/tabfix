[![PyPI version](https://img.shields.io/pypi/v/tabfix-tool.svg)](https://pypi.org/project/tabfix-tool/)
[![PyPI downloads](https://img.shields.io/pypi/dm/tabfix-tool.svg)](https://pypi.org/project/tabfix-tool/)
[![Python versions](https://img.shields.io/pypi/pyversions/tabfix-tool.svg)](https://pypi.org/project/tabfix-tool/)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/7fceb52b899d44b3bb151b568dc99d38)](https://app.codacy.com/gh/hairpin01/tabfix/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
[![GitHub repo size](https://img.shields.io/github/repo-size/hairpin01/tabfix)](https://github.com/hairpin01/tabfix)
[![GitHub last commit](https://img.shields.io/github/last-commit/hairpin01/tabfix)](https://github.com/hairpin01/tabfix/commits/main)
[![GitHub issues](https://img.shields.io/github/issues-raw/hairpin01/tabfix)](https://github.com/hairpin01/tabfix/issues)
[![GitHub forks](https://img.shields.io/github/forks/hairpin01/tabfix?style=flat)](https://github.com/hairpin01/tabfix/network/members)
[![GitHub stars](https://img.shields.io/github/stars/hairpin01/tabfix)](https://github.com/hairpin01/tabfix/stargazers)
[![GitHub license](https://img.shields.io/github/license/hairpin01/tabfix)](https://github.com/hairpin01/tabfix/blob/main/LICENSE)

# TabFix Tool
Advanced tool for fixing `tab/space` indentation issues in `code` files.

## Features
> - Fix mixed tabs and spaces indentation
> - Remove trailing whitespace
> - Normalize line endings
> - Handle `UTF-8` BOM markers
> - Format `JSON` files
> - `Git` integration
> - Progress bars with tqdm
> - Colorful output

## Installation
```bash
# Install from PyPI
pip install tabfix-tool
```
```bash
# Or directly from GitHub
pip install git+https://github.com/hairpin01/tabfix.git
```
or via installer
```bash
curl https://raw.githubusercontent.com/hairpin01/tabfix/refs/heads/main/src/tabfix/installer.py | python3
```
> [!TIP]
> to install the unifmt package, see [optional](https://github.com/hairpin01/tabfix#install-optional-unifmt-or-devencodingfull)


## From source
```bash
git clone https://github.com/hairpin01/tabfix.git && cd tabfix && pip install -e .
```
## Usage
```bash
# Basic usage
tabfix file.py
```
```bash
# Recursive processing
tabfix --recursive src/
```
```bash
# Fix multiple issues
tabfix --all --progress .
```
```bash
# Check without modifying
tabfix --check-mixed --recursive .
```
## Complete Help Reference

<details>
<summary><b>Show full command reference (tabfix -h)</b></summary>

```bash
$ tabfix -h
usage: tabfix [-h] [--config CONFIG] [--no-config] [--init] [--show-config] [-s SPACES] [-m] [-t] [-f] [--remove-bom] [--keep-bom] [--format-json] [--git-staged]
              [--git-unstaged] [--git-all-changed] [--no-gitignore] [--skip-binary] [--no-skip-binary] [--force-encoding FORCE_ENCODING]
              [--fallback-encoding FALLBACK_ENCODING] [--warn-encoding] [--max-file-size MAX_FILE_SIZE] [--smart-processing] [--no-smart-processing]
              [--preserve-quotes] [-r] [-i] [--progress] [--dry-run] [--backup] [--pre-commit] [-v] [-q] [--no-color] [--diff FILE1 FILE2]
              [paths ...]

Advanced tab/space indentation fixer with extended features

positional arguments:
  paths                 Files or directories to process

options:
  -h, --help            show this help message and exit
  --diff FILE1 FILE2    Compare indentation between two files

Configuration:
  --config CONFIG       Path to configuration file
  --no-config           Ignore configuration files
  --init                Initialize configuration file (.tabfixrc)
  --show-config         Show current configuration and exit

Formatting options:
  -s, --spaces SPACES   Number of spaces per tab (default: 4)
  -m, --fix-mixed       Fix mixed tabs/spaces indentation
  -t, --fix-trailing    Remove trailing whitespace
  -f, --final-newline   Ensure file ends with newline
  --remove-bom          Remove UTF-8 BOM marker
  --keep-bom            Preserve existing BOM marker
  --format-json         Format JSON files with proper indentation

Git integration:
  --git-staged          Process only staged files in git
  --git-unstaged        Process only unstaged files in git
  --git-all-changed     Process all changed files in git
  --no-gitignore        Do not use .gitignore patterns

Encoding and file handling:
  --skip-binary         Skip files that appear to be binary
  --no-skip-binary      Process files even if they appear to be binary
  --force-encoding FORCE_ENCODING
                        Force specific encoding (skip auto-detection)
  --fallback-encoding FALLBACK_ENCODING
                        Fallback encoding when detection fails (default: latin-1)
  --warn-encoding       Warn when encoding detection is uncertain
  --max-file-size MAX_FILE_SIZE
                        Maximum file size to process in bytes (default: 10MB)

File type specific processing:
  --smart-processing    Enable smart processing for different file types (default: True)
  --no-smart-processing
                        Disable smart processing for different file types
  --preserve-quotes     Preserve original string quotes in code files

Operation mode:
  -r, --recursive       Process directories recursively
  -i, --interactive     Interactive mode (confirm each change)
  --progress            Show progress bar during processing
  --dry-run             Show changes without modifying files
  --backup              Create backup files (.bak)
  --pre-commit          Generate pre-commit hook configuration

Output control:
  -v, --verbose         Verbose output
  -q, --quiet           Quiet mode (minimal output)
  --no-color            Disable colored output

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
```
</details>


## install optional unifmt or dev/encoding/full 
```
pip install tabfix-tool[all] # or {optional}
```

## API Documentation
<details>
<summary><b> Python API examples</b></summary>
  
```python
# developer_script.py
from tabfix import TabFixAPI, TabFixConfig, fix_string, fix_file

# Method 1: Using API class
config = TabFixConfig(spaces=2, fix_mixed=True, fix_trailing=True)
api = TabFixAPI(config)

# Fix a string
fixed_content, changes = api.fix_string("def foo():\n\tprint('hello')", Path("test.py"))
print(f"Fixed content: {fixed_content}")
print(f"Changes: {changes}")

# Fix a file
changed, file_changes = api.fix_file(Path("my_script.py"))
print(f"File changed: {changed}")
print(f"File changes: {file_changes}")

# Method 2: Using convenience functions
# Fix string directly
content = "if True:\n\tprint('tab')"
fixed, changes = fix_string(content, spaces=4)
print(f"Fixed: {fixed}")

# Check if file needs fixing
needs_fix, issues = check_file(Path("config.json"))
print(f"Needs fix: {needs_fix}, Issues: {issues}")

# Detect indentation style
result = detect_indentation(content)
print(f"Indentation: {result}")

# Create config file
create_config_file(Path(".tabfixrc.json"))
```
More:
```python
# developer_script.py
from tabfix import TabFixAPI, TabFixConfig, fix_string, fix_file

# Method 1: Using API class
config = TabFixConfig(spaces=2, fix_mixed=True, fix_trailing=True)
api = TabFixAPI(config)

# Fix a string
fixed_content, changes = api.fix_string("def foo():\n\tprint('hello')", Path("test.py"))
print(f"Fixed content: {fixed_content}")
print(f"Changes: {changes}")

# Fix a file
changed, file_changes = api.fix_file(Path("my_script.py"))
print(f"File changed: {changed}")
print(f"File changes: {file_changes}")

# Method 2: Using convenience functions
# Fix string directly
content = "if True:\n\tprint('tab')"
fixed, changes = fix_string(content, spaces=4)
print(f"Fixed: {fixed}")

# Check if file needs fixing
needs_fix, issues = check_file(Path("config.json"))
print(f"Needs fix: {needs_fix}, Issues: {issues}")

# Detect indentation style
result = detect_indentation(content)
print(f"Indentation: {result}")

# Create config file
create_config_file(Path(".tabfixrc.json"))
```
</details>
