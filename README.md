
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/b4wOszL76ZhJ36AozTO7/)](https://www.codacy.com/gh/hairpin01/tabfix/dashboard?utm_source=github.com&utm_medium=referral&utm_content=hairpin01/tabfix&utm_campaign=Badge_Grade)

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
```shell
# Install from PyPI
pip install tabfix-tool
```
```shell
# Or directly from GitHub
pip install git+https://github.com/hairpin01/tabfix.git
```
or via installer
```shell
curl https://raw.githubusercontent.com/hairpin01/tabfix/refs/heads/main/src/tabfix/installer.py | python3
```
> [!TIP]
> to install the unifmt package, see [optional](https://github.com/hairpin01/tabfix#install-optional-unifmt-or-devencodingfull)


## From source
`git clone https://github.com/hairpin01/tabfix.git
&& cd tabfix
&& pip install -e .
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

## install optional unifmt or dev/encoding/full
```
pip install tabfix-tool[unifmt] # or {optional}
```
