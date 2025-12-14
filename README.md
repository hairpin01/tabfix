
# TabFix Tool
Advanced tool for fixing `tab/space` indentation issues in `code` files.

## Features
- Fix mixed tabs and spaces indentation
- Remove trailing whitespace
- Normalize line endings
- Handle `UTF-8` BOM markers
- Format `JSON` files
- Git integration
- Progress bars with tqdm
- Colorful output

## Installation
```shell
# Install from PyPI
pip install tabfix-tool 
```
```shell
# Or directly from GitHub
pip install git+https://github.com/hairpin01/tabfix.git
```
## From source
`git clone https://github.com/alina/tabfix.git
cd tabfix
pip install -e .
`
## Usage
```
# Basic usage
tabfix file.py
```
```
# Recursive processing
tabfix --recursive src/
```
```
# Fix multiple issues
tabfix --all --progress .
```
```
# Check without modifying
tabfix --check-mixed --recursive .
```
