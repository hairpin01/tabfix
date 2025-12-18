#!/usr/bin/env python3
import sys
import os
import argparse
import re
import json
import subprocess
import shutil
import fnmatch
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Set, Any
from datetime import datetime
from collections import Counter

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False

try:
    from charset_normalizer import detect as charset_detect
    HAS_CHARSET_NORMALIZER = True
except ImportError:
    HAS_CHARSET_NORMALIZER = False


class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    END = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"


def print_color(text: str, color: str = Colors.END, end: str = "\n"):
    if sys.stdout.isatty():
        print(f"{color}{text}{Colors.END}", end=end)
    else:
        print(text, end=end)


class GitignoreMatcher:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir.resolve()
        self.patterns = []
        self.load_gitignore()

    def load_gitignore(self):
        gitignore_paths = [
            self.root_dir / ".gitignore",
            self.root_dir / ".git" / "info" / "exclude",
        ]

        for gitignore_path in gitignore_paths:
            if gitignore_path.exists():
                with open(gitignore_path, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if line.startswith("!"):
                            continue
                        if "/" in line:
                            self.patterns.append(line)
                        else:
                            self.patterns.append(f"**/{line}")

        default_patterns = [
            ".git/",
            ".svn/",
            ".hg/",
            ".bzr/",
            ".idea/",
            ".vscode/",
            "__pycache__/",
            "*.pyc",
            "*.pyo",
            "*.pyd",
            ".Python",
            "*.so",
            "*.dylib",
            "*.egg-info/",
            "*.egg",
            "dist/",
            "build/",
            "*.log",
            "*.sqlite3",
            "*.db",
            "*.env",
            "*.venv",
            "venv/",
            "node_modules/",
            "bower_components/",
            ".cache/",
            "coverage/",
            ".tox/",
            ".nox/",
            ".pytest_cache/",
            ".mypy_cache/",
            ".hypothesis/",
        ]
        self.patterns.extend(default_patterns)

    def should_ignore(self, path: Path) -> bool:
        try:
            rel_path = path.resolve().relative_to(self.root_dir)
            rel_str = str(rel_path).replace("\\", "/")
            if rel_str == ".":
                return False

            for pattern in self.patterns:
                if pattern.endswith("/"):
                    if rel_str.startswith(pattern[:-1]) or fnmatch.fnmatch(rel_str, pattern[:-1]):
                        return True
                else:
                    if fnmatch.fnmatch(rel_str, pattern) or fnmatch.fnmatch(path.name, pattern):
                        return True

            return False
        except ValueError:
            return False


class EncodingDetector:
    def __init__(self, confidence_threshold: float = 0.8):
        self.confidence_threshold = confidence_threshold

    def detect_with_chardet(self, content: bytes) -> Optional[Tuple[str, float]]:
        if HAS_CHARDET:
            try:
                result = chardet.detect(content)
                if result['encoding'] and result['confidence'] > self.confidence_threshold:
                    return result['encoding'], result['confidence']
            except Exception:
                pass

        if HAS_CHARSET_NORMALIZER:
            try:
                result = charset_detect(content)
                if result and result['encoding']:
                    return result['encoding'], result['confidence']
            except Exception:
                pass

        return None

    def analyze_byte_patterns(self, content: bytes) -> str:
        if len(content) < 4:
            return 'utf-8'

        if content.startswith(b'\xff\xfe'):
            return 'utf-16-le'
        elif content.startswith(b'\xfe\xff'):
            return 'utf-16-be'
        elif content.startswith(b'\xff\xfe\x00\x00'):
            return 'utf-32-le'
        elif content.startswith(b'\x00\x00\xfe\xff'):
            return 'utf-32-be'

        utf8_valid = 0
        latin1_valid = 0
        content_length = len(content)

        i = 0
        while i < min(content_length, 1000):
            byte = content[i]

            if byte < 128:
                utf8_valid += 1
            elif 194 <= byte <= 223 and i + 1 < content_length:
                next_byte = content[i + 1]
                if 128 <= next_byte <= 191:
                    utf8_valid += 2
                    i += 1
            elif 224 <= byte <= 239 and i + 2 < content_length:
                if (128 <= content[i + 1] <= 191 and 
                    128 <= content[i + 2] <= 191):
                    utf8_valid += 3
                    i += 2
            elif 240 <= byte <= 244 and i + 3 < content_length:
                if (128 <= content[i + 1] <= 191 and 
                    128 <= content[i + 2] <= 191 and
                    128 <= content[i + 3] <= 191):
                    utf8_valid += 4
                    i += 3

            latin1_valid += 1
            i += 1

        if utf8_valid > latin1_valid * 1.1:
            return 'utf-8'
        else:
            return 'latin-1'

    def get_encoding_for_region(self, filename: str) -> Optional[str]:
        filename_lower = filename.lower()

        if any(x in filename_lower for x in ['.ru.', '.rus.', 'russian']):
            return 'cp1251'
        elif any(x in filename_lower for x in ['.jp.', '.jpn.', 'japanese']):
            return 'shift_jis'
        elif any(x in filename_lower for x in ['.cn.', '.chs.', 'chinese']):
            return 'gbk'
        elif any(x in filename_lower for x in ['.tw.', '.cht.', 'traditional']):
            return 'big5'

        return None


class FileProcessor:
    def __init__(self, spaces_per_tab: int = 4):
        self.spaces_per_tab = spaces_per_tab
        self.processors = {
            '.py': self.process_python,
            '.js': self.process_javascript,
            '.jsx': self.process_javascript,
            '.ts': self.process_typescript,
            '.tsx': self.process_typescript,
            '.json': self.process_json,
            '.yaml': self.process_yaml,
            '.yml': self.process_yaml,
            '.md': self.process_markdown,
            '.markdown': self.process_markdown,
            '.html': self.process_html,
            '.htm': self.process_html,
            '.css': self.process_css,
            '.scss': self.process_scss,
            '.sass': self.process_sass,
            '.xml': self.process_xml,
            '.svg': self.process_xml,
            '.txt': self.process_text,
            '.csv': self.process_csv,
            '.ini': self.process_ini,
            '.cfg': self.process_ini,
            '.toml': self.process_toml,
            '.sh': self.process_shell,
            '.bash': self.process_shell,
            '.zsh': self.process_shell,
            '.dockerfile': self.process_docker,
            'dockerfile': self.process_docker,
            '.gitignore': self.process_gitignore,
            '.editorconfig': self.process_editorconfig,
        }

    def process_by_extension(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        suffix = filepath.suffix.lower()
        if filepath.name.lower() == 'dockerfile':
            suffix = 'dockerfile'

        processor = self.processors.get(suffix, self.process_generic)
        return processor(content, filepath)

    def process_python(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes = []
        lines = content.split('\n')

        if lines and lines[0].startswith('#!'):
            if 'python' in lines[0] and 'python3' not in lines[0]:
                lines[0] = '#!/usr/bin/env python3'
                changes.append("Fixed shebang to python3")

        for i, line in enumerate(lines):
            stripped = line.rstrip()
            if line != stripped:
                if line.strip().startswith('#') or not line.strip():
                    lines[i] = stripped
                    changes.append(f"Line {i+1}: Removed trailing spaces in comment")

        return '\n'.join(lines), changes

    def process_javascript(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes = []
        lines = content.split('\n')
        in_import_block = False
        import_lines = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(('import ', 'export ', 'from ')):
                in_import_block = True
                import_lines.append((i, line))
            elif stripped and not stripped.startswith(('//', '/*', '*', '`')):
                in_import_block = False

        if import_lines and len(import_lines) > 1:
            max_length = max(len(line) for _, line in import_lines)
            for idx, (line_num, line) in enumerate(import_lines):
                if len(line) < max_length:
                    lines[line_num] = line + ' ' * (max_length - len(line))
                    changes.append(f"Line {line_num+1}: Aligned import")

        return '\n'.join(lines), changes

    def process_typescript(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        return self.process_javascript(content, filepath)

    def process_json(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes = []
        try:
            parsed = json.loads(content)
            formatted = json.dumps(
                parsed, 
                indent=self.spaces_per_tab, 
                ensure_ascii=False,
                sort_keys=False
            )
            if formatted != content:
                changes.append("Formatted JSON")
                return formatted, changes
        except json.JSONDecodeError as e:
            fixed = self.fix_json_issues(content)
            if fixed != content:
                changes.append(f"Fixed JSON syntax: {str(e)[:50]}")
                return fixed, changes

        return content, changes

    def fix_json_issues(self, content: str) -> str:
        fixed = content
        lines = fixed.split('\n')
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.endswith(',') and not stripped.endswith('",'):
                if i + 1 < len(lines):
                    next_stripped = lines[i + 1].strip()
                    if next_stripped in ('}', ']'):
                        lines[i] = line.rstrip(',')
        fixed = '\n'.join(lines)

        in_string = False
        escape_next = False
        result = []
        for char in fixed:
            if escape_next:
                result.append(char)
                escape_next = False
            elif char == '\\':
                result.append(char)
                escape_next = True
            elif char == '"':
                result.append(char)
                in_string = not in_string
            elif char == "'" and not in_string:
                result.append('"')
            else:
                result.append(char)

        return ''.join(result)

    def process_yaml(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes = []
        try:
            import yaml
            yaml.safe_load(content)
            lines = content.split('\n')
            for i, line in enumerate(lines):
                stripped = line.rstrip()
                if line != stripped:
                    lines[i] = stripped
                    changes.append(f"Line {i+1}: Removed trailing spaces")
            return '\n'.join(lines), changes
        except ImportError:
            pass
        return content, changes

    def process_markdown(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes = []
        lines = content.split('\n')
        in_code_block = False

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('```') or stripped.startswith('~~~'):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            if stripped.startswith('#'):
                hash_count = 0
                while hash_count < len(stripped) and stripped[hash_count] == '#':
                    hash_count += 1
                if hash_count < len(stripped) and stripped[hash_count] != ' ':
                    lines[i] = line.replace('#' * hash_count, '#' * hash_count + ' ', 1)
                    changes.append(f"Line {i+1}: Fixed heading formatting")

            if stripped.startswith(('- ', '* ', '+ ')) and len(stripped) > 2:
                if stripped[2] == ' ':
                    lines[i] = line.replace(stripped[:3], stripped[:2], 1)
                    changes.append(f"Line {i+1}: Fixed list formatting")

        return '\n'.join(lines), changes

    def process_html(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes = []
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if '<br>' in line or '<hr>' in line:
                lines[i] = line.replace('<br>', '<br/>').replace('<hr>', '<hr/>')
                changes.append(f"Line {i+1}: Fixed self-closing tags")
        return '\n'.join(lines), changes

    def process_css(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        return self.process_generic(content, filepath)

    def process_scss(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        return self.process_generic(content, filepath)

    def process_sass(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        return self.process_generic(content, filepath)

    def process_xml(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes = []
        lines = content.split('\n')
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            if line != stripped:
                lines[i] = stripped
                changes.append(f"Line {i+1}: Removed trailing spaces")
        return '\n'.join(lines), changes

    def process_text(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        return self.process_generic(content, filepath)

    def process_csv(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        return self.process_generic(content, filepath)

    def process_ini(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes = []
        lines = content.split('\n')
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            if line != stripped:
                lines[i] = stripped
                changes.append(f"Line {i+1}: Removed trailing spaces")
        return '\n'.join(lines), changes

    def process_toml(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        return self.process_generic(content, filepath)

    def process_shell(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes = []
        lines = content.split('\n')
        if lines and lines[0].startswith('#!'):
            if 'bash' in lines[0] and '-e' not in lines[0]:
                lines[0] = '#!/usr/bin/env bash'
                changes.append("Standardized bash shebang")
        return '\n'.join(lines), changes

    def process_docker(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        return self.process_generic(content, filepath)

    def process_gitignore(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        return self.process_generic(content, filepath)

    def process_editorconfig(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        return self.process_generic(content, filepath)

    def process_generic(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes = []
        lines = content.split('\n')
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            if line != stripped:
                lines[i] = stripped
                changes.append(f"Line {i+1}: Removed trailing spaces")
        return '\n'.join(lines), changes


class TabFix:
    def __init__(self, spaces_per_tab: int = 4):
        self.spaces_per_tab = spaces_per_tab
        self.stats = {
            "files_processed": 0,
            "files_changed": 0,
            "tabs_replaced": 0,
            "lines_fixed": 0,
            "bom_removed": 0,
            "json_formatted": 0,
            "mixed_indent_files": 0,
            "files_skipped": 0,
            "binary_files_skipped": 0,
        }
        self.encoding_detector = EncodingDetector()
        self.file_processor = FileProcessor(spaces_per_tab)

    def remove_bom(self, content: bytes) -> Tuple[bytes, bool]:
        if content.startswith(b"\xef\xbb\xbf"):
            return content[3:], True
        return content, False

    def add_bom(self, content: bytes) -> bytes:
        return b"\xef\xbb\xbf" + content

    def format_json(self, content: str) -> Tuple[str, bool]:
        try:
            parsed = json.loads(content)
            formatted = json.dumps(parsed, indent=self.spaces_per_tab, ensure_ascii=False)
            if formatted != content:
                return formatted, True
        except (json.JSONDecodeError, TypeError):
            pass
        return content, False

    def compare_files_indentation(self, file1: Path, file2: Path) -> Dict:
        try:
            with open(file1, "r", encoding="utf-8-sig") as f:
                content1 = f.read()
            with open(file2, "r", encoding="utf-8-sig") as f:
                content2 = f.read()
        except Exception as e:
            return {"error": str(e)}

        lines1 = content1.split("\n")
        lines2 = content2.split("\n")

        differences = []
        max_lines = max(len(lines1), len(lines2))

        for i in range(max_lines):
            line1 = lines1[i] if i < len(lines1) else ""
            line2 = lines2[i] if i < len(lines2) else ""

            indent1 = len(line1) - len(line1.lstrip())
            indent2 = len(line2) - len(line2.lstrip())

            uses_tabs1 = "\t" in line1[:indent1]
            uses_tabs2 = "\t" in line2[:indent2]

            if indent1 != indent2 or uses_tabs1 != uses_tabs2:
                differences.append(
                    {
                        "line": i + 1,
                        "file1": {
                            "indent": indent1,
                            "uses_tabs": uses_tabs1,
                            "preview": line1[:50] + "..." if len(line1) > 50 else line1,
                        },
                        "file2": {
                            "indent": indent2,
                            "uses_tabs": uses_tabs2,
                            "preview": line2[:50] + "..." if len(line2) > 50 else line2,
                        },
                    }
                )

        return {
            "differences": differences,
            "total_lines_file1": len(lines1),
            "total_lines_file2": len(lines2),
            "indent_matches": len(differences) == 0,
        }
        
        
    def process_file_with_changes(self, filepath: Path, args, 
                                gitignore_matcher: Optional[GitignoreMatcher] = None) -> Tuple[bool, List[str]]:
        if gitignore_matcher and gitignore_matcher.should_ignore(filepath):
            self.stats["files_skipped"] += 1
            return False, []
    
        try:
            if not filepath.is_file():
                return False, []
    
            file_size = filepath.stat().st_size
            if file_size > args.max_file_size:
                return False, []
    
            with open(filepath, "rb") as f:
                raw_content = f.read()
        except Exception:
            return False, []
    
        original_raw = raw_content
        changes = []
        content = raw_content.decode("utf-8-sig")
        had_bom = raw_content.startswith(b"\xef\xbb\xbf")
    
        if args.remove_bom and had_bom:
            changes.append("Removed BOM")
    
        if args.format_json and filepath.suffix.lower() == ".json":
            formatted, changed = self.format_json(content)
            if changed:
                content = formatted
                changes.append("Formatted JSON")
                self.stats["json_formatted"] += 1
    
        if args.fix_mixed:
            content, indent_changes = self.fix_mixed_indentation(content)
            changes.extend(indent_changes)
            if indent_changes:
                self.stats["tabs_replaced"] += len(indent_changes)
                self.stats["lines_fixed"] += len(indent_changes)
    
        if args.fix_trailing:
            content, trailing_changes = self.fix_trailing_spaces(content)
            changes.extend(trailing_changes)
            if trailing_changes:
                self.stats["lines_fixed"] += len(trailing_changes)
    
        if args.final_newline:
            content, newline_changes = self.ensure_final_newline(content)
            changes.extend(newline_changes)
    
        if not changes:
            return False, []
    
        if args.interactive and not self.interactive_confirm(filepath, changes):
            return False, []
    
        new_raw = content.encode("utf-8")
        if args.keep_bom and had_bom:
            new_raw = self.add_bom(new_raw)
    
        if new_raw == original_raw:
            return False, []
    
        if args.backup and not args.dry_run:
            backup_path = filepath.with_suffix(filepath.suffix + ".bak")
            with open(backup_path, "wb") as f:
                f.write(original_raw)
    
        if not args.dry_run:
            with open(filepath, "wb") as f:
                f.write(new_raw)
    
            if had_bom and args.remove_bom:
                self.stats["bom_removed"] += 1
    
        self.stats["files_changed"] += 1
        return True, changes
            
    def interactive_confirm(self, filepath: Path, changes: List[str]) -> bool:
        if not changes:
            return True

        print_color(f"\n{Colors.CYAN}File:{Colors.END} {filepath}")
        print_color(f"{Colors.YELLOW}Changes to be made:{Colors.END}")
        for i, change in enumerate(changes[:5], 1):
            print_color(f"  {i}. {change}")
        if len(changes) > 5:
            print_color(f"  ... and {len(changes) - 5} more changes", Colors.DIM)

        while True:
            response = (
                input(f"\nApply these {len(changes)} changes? (y/n/a[ll]/q[uit]): ").lower().strip()
            )
            if response in ("y", "yes"):
                return True
            elif response in ("n", "no"):
                return False
            elif response in ("a", "all"):
                return True
            elif response in ("q", "quit"):
                sys.exit(0)
            else:
                print_color("Please enter y, n, a, or q", Colors.RED)

    def get_git_files(self, mode: str = "staged") -> List[Path]:
        try:
            if mode == "staged":
                result = subprocess.run(
                    ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            elif mode == "unstaged":
                result = subprocess.run(
                    ["git", "diff", "--name-only", "--diff-filter=ACM"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            elif mode == "all_changed":
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                files = []
                for line in result.stdout.strip().split("\n"):
                    if line:
                        status = line[:2]
                        filename = line[3:].strip()
                        if status != "??":
                            files.append(filename)
                return [Path(f) for f in files if f]
            else:
                return []

            files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
            return [Path(f) for f in files]
        except (subprocess.CalledProcessError, FileNotFoundError):
            return []

    def detect_indentation(self, content: str) -> Dict:
        lines = content.split("\n")
        tab_lines = 0
        space_lines = 0
        space_counts = []

        for line in lines:
            if not line.strip():
                continue
            if line.startswith("\t"):
                tab_lines += 1
            elif line.startswith(" "):
                space_lines += 1
                leading = len(line) - len(line.lstrip(" "))
                if leading > 0:
                    space_counts.append(leading)

        common_indent = None
        if space_counts:
            counter = Counter(space_counts)
            if counter:
                common_indent = counter.most_common(1)[0][0]

        return {
            "uses_tabs": tab_lines > 0,
            "uses_spaces": space_lines > 0,
            "common_indent": common_indent,
            "mixed": tab_lines > 0 and space_lines > 0,
            "total_lines": len(lines),
            "indented_lines": tab_lines + space_lines,
        }

    def fix_mixed_indentation(self, content: str) -> Tuple[str, List[str]]:
        lines = content.split("\n")
        fixed_lines = []
        changes = []

        for i, line in enumerate(lines, 1):
            original = line
            if "\t" in line:
                fixed_line = line.replace("\t", " " * self.spaces_per_tab)
                if fixed_line != original:
                    fixed_lines.append(fixed_line)
                    changes.append(f"Line {i}: Tabs → spaces")
                else:
                    fixed_lines.append(fixed_line)
            else:
                fixed_lines.append(line)

        return "\n".join(fixed_lines), changes

    def fix_trailing_spaces(self, content: str) -> Tuple[str, List[str]]:
        lines = content.split("\n")
        fixed_lines = []
        changes = []

        for i, line in enumerate(lines, 1):
            original_length = len(line)
            fixed_line = line.rstrip()
            if len(fixed_line) != original_length:
                fixed_lines.append(fixed_line)
                changes.append(f"Line {i}: Removed trailing spaces")
            else:
                fixed_lines.append(line)

        return "\n".join(fixed_lines), changes

    def ensure_final_newline(self, content: str) -> Tuple[str, List[str]]:
        changes = []
        if content and not content.endswith("\n"):
            content = content + "\n"
            changes.append("Added final newline")
        return content, changes

    def detect_encoding_and_decode(self, content: bytes, default_encoding: str = 'utf-8') -> Tuple[str, str, bool]:
        def try_decode(data: bytes, encoding: str) -> Optional[str]:
            try:
                return data.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                return None

        if content.startswith(b'\xef\xbb\xbf'):
            decoded = try_decode(content[3:], 'utf-8')
            if decoded is not None:
                return decoded, 'utf-8-sig', True

        decoded = try_decode(content, 'utf-8')
        if decoded is not None:
            return decoded, 'utf-8', True

        chardet_result = self.encoding_detector.detect_with_chardet(content)
        if chardet_result:
            encoding, confidence = chardet_result
            decoded = try_decode(content, encoding)
            if decoded is not None:
                return decoded, encoding, confidence > 0.8

        common_encodings = [
            'utf-16', 'utf-16-be', 'utf-16-le',
            'cp1251', 'cp1252', 'iso-8859-1', 'iso-8859-2',
            'koi8-r', 'cp866', 'mac_cyrillic',
            'shift_jis', 'euc-jp', 'gbk', 'big5'
        ]

        for encoding in common_encodings:
            decoded = try_decode(content, encoding)
            if decoded is not None:
                if self.looks_like_valid_text(decoded):
                    return decoded, encoding, False

        try:
            return content.decode(default_encoding, errors='replace'), default_encoding, False
        except (UnicodeDecodeError, LookupError):
            return content.decode('latin-1', errors='replace'), 'latin-1', False

    def looks_like_valid_text(self, text: str, threshold: float = 0.7) -> bool:
        if not text:
            return False

        printable = sum(1 for char in text if char.isprintable() or char in '\n\r\t')
        ratio = printable / len(text)
        control_chars = sum(1 for char in text if ord(char) < 32 and char not in '\n\r\t')
        control_ratio = control_chars / len(text)

        return ratio > threshold and control_ratio < 0.1

    def is_likely_binary(self, content: bytes, filename: str = None) -> bool:
        if filename:
            binary_extensions = {
                '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp',
                '.pdf', '.zip', '.tar', '.gz', '.bz2', '.xz', '.rar', '.7z',
                '.exe', '.dll', '.so', '.dylib', '.class',
                '.pyc', '.pyo', '.pyd', '.o', '.obj', '.a', '.lib',
                '.mp3', '.mp4', '.avi', '.mkv', '.mov',
                '.ttf', '.otf', '.woff', '.woff2',
                '.db', '.sqlite', '.mdb'
            }
            if any(filename.lower().endswith(ext) for ext in binary_extensions):
                return True

        sample = content[:1024] if len(content) > 1024 else content
        if b'\x00' in sample:
            return True

        binary_signatures = [
            (b'\x89PNG\r\n\x1a\n', 0),
            (b'\xff\xd8\xff', 0),
            (b'GIF87a', 0),
            (b'GIF89a', 0),
            (b'%PDF', 0),
            (b'PK\x03\x04', 0),
            (b'PK\x05\x06', 0),
            (b'PK\x07\x08', 0),
            (b'\x1f\x8b\x08', 0),
            (b'BZh', 0),
            (b'\xfd7zXZ', 0),
            (b'\x37\x7a\xbc\xaf\x27\x1c', 0),
            (b'MZ', 0),
            (b'\x7fELF', 0),
        ]

        for signature, offset in binary_signatures:
            if sample[offset:offset + len(signature)] == signature:
                return True

        return False

    def is_binary_content(self, text: str, encoding: str = 'utf-8') -> bool:
        if not text:
            return False

        non_printable = 0
        for char in text[:1000]:
            if not char.isprintable() and char not in '\n\r\t\f\v':
                non_printable += 1

        return (non_printable / min(len(text), 1000)) > 0.3

    def summarize_changes(self, changes: List[str]) -> str:
        categories = Counter()
        for change in changes:
            if 'trailing spaces' in change.lower():
                categories['trailing_spaces'] += 1
            elif 'tab' in change.lower() or 'indentation' in change.lower():
                categories['indentation'] += 1
            elif 'shebang' in change.lower():
                categories['shebang'] += 1
            elif 'json' in change.lower():
                categories['json'] += 1
            elif 'import' in change.lower():
                categories['imports'] += 1
            elif 'heading' in change.lower():
                categories['markdown'] += 1
            elif 'bom' in change.upper():
                categories['bom'] += 1
            else:
                categories['other'] += 1

        parts = []
        if categories.get('trailing_spaces'):
            parts.append(f"{categories['trailing_spaces']} trailing spaces")
        if categories.get('indentation'):
            parts.append(f"{categories['indentation']} indentation fixes")
        if categories.get('bom'):
            parts.append(f"{categories['bom']} BOM removals")
        if categories.get('json'):
            parts.append(f"{categories['json']} JSON formats")
        if categories.get('imports'):
            parts.append(f"{categories['imports']} import alignments")
        if categories.get('shebang'):
            parts.append(f"{categories['shebang']} shebang fixes")
        if categories.get('markdown'):
            parts.append(f"{categories['markdown']} markdown fixes")
        if categories.get('other'):
            parts.append(f"{categories['other']} other changes")

        return ', '.join(parts) if parts else "no changes"

    def process_file(
        self, filepath: Path, args, gitignore_matcher: Optional[GitignoreMatcher] = None
    ) -> bool:
        if '.git' in str(filepath.absolute()):
            if getattr(args, 'verbose', False):
                print_color(f"Skipped (.git directory): {filepath}", Colors.DIM)
            self.stats["files_skipped"] += 1
            return False

        if gitignore_matcher and gitignore_matcher.should_ignore(filepath):
            if getattr(args, 'verbose', False):
                print_color(f"Skipped (gitignore): {filepath}", Colors.DIM)
            self.stats["files_skipped"] += 1
            return False

        try:
            if not filepath.is_file():
                return False

            file_size = filepath.stat().st_size
            if file_size > getattr(args, 'max_file_size', 10 * 1024 * 1024):
                if getattr(args, 'verbose', False):
                    size_mb = file_size / (1024 * 1024)
                    print_color(f"Skipped (large file): {filepath} ({size_mb:.1f} MB)", Colors.YELLOW)
                return False

            with open(filepath, "rb") as f:
                raw_content = f.read()
        except PermissionError:
            if not getattr(args, 'quiet', False):
                print_color(f"Permission denied reading: {filepath}", Colors.RED)
            self.stats["files_skipped"] += 1
            return False
        except Exception as e:
            if not getattr(args, 'quiet', False):
                print_color(f"Error reading {filepath}: {e}", Colors.RED)
            self.stats["files_skipped"] += 1
            return False

        original_raw = raw_content

        changes = []
        try:
            content = raw_content.decode("utf-8-sig")
        except UnicodeDecodeError:
            if getattr(args, 'skip_binary', True):
                if getattr(args, 'verbose', False):
                    print_color(f"Skipped (binary/unreadable): {filepath}", Colors.DIM)
                self.stats["files_skipped"] += 1
                return False
            else:
                if not getattr(args, 'quiet', False):
                    print_color(f"Cannot decode file: {filepath}", Colors.YELLOW)
                self.stats["files_skipped"] += 1
                return False

        had_bom = raw_content.startswith(b"\xef\xbb\xbf")

        if getattr(args, 'remove_bom', False) and had_bom:
            changes.append("Removed BOM")

        if getattr(args, 'format_json', False) and filepath.suffix.lower() == ".json":
            formatted, changed = self.format_json(content)
            if changed:
                content = formatted
                changes.append("Formatted JSON")
                self.stats["json_formatted"] += 1

        if getattr(args, 'fix_mixed', False):
            fixed_content, indent_changes = self.fix_mixed_indentation(content)
            if fixed_content != content:
                content = fixed_content
                changes.extend(indent_changes)
                if indent_changes:
                    self.stats["tabs_replaced"] += len(indent_changes)
                    self.stats["lines_fixed"] += len(indent_changes)

        if getattr(args, 'fix_trailing', False):
            fixed_content, trailing_changes = self.fix_trailing_spaces(content)
            if fixed_content != content:
                content = fixed_content
                changes.extend(trailing_changes)
                if trailing_changes:
                    self.stats["lines_fixed"] += len(trailing_changes)

        if getattr(args, 'final_newline', False):
            content, newline_changes = self.ensure_final_newline(content)
            changes.extend(newline_changes)

        if not changes:
            return False

        if getattr(args, 'interactive', False) and not self.interactive_confirm(filepath, changes):
            return False

        if getattr(args, 'keep_bom', False) and had_bom:
            new_raw = self.add_bom(content.encode("utf-8"))
        else:
            new_raw = content.encode("utf-8")

        if new_raw == original_raw:
            return False

        if getattr(args, 'backup', False):
            try:
                backup_path = filepath.with_suffix(filepath.suffix + ".bak")
                with open(backup_path, "wb") as f:
                    f.write(original_raw)
            except Exception as e:
                if not getattr(args, 'quiet', False):
                    print_color(f"Failed to create backup for {filepath}: {e}", Colors.YELLOW)

        if not getattr(args, 'dry_run', False):
            try:
                with open(filepath, "wb") as f:
                    f.write(new_raw)

                if had_bom and getattr(args, 'remove_bom', False):
                    self.stats["bom_removed"] += 1

                self.stats["files_changed"] += 1
                if getattr(args, 'verbose', False):
                    change_summary = ", ".join([c.split(":")[0] for c in changes[:3]])
                    if len(changes) > 3:
                        change_summary += f" and {len(changes) - 3} more"
                    print_color(f"Fixed: {filepath} ({change_summary})", Colors.GREEN)
                return True
            except PermissionError:
                if not getattr(args, 'quiet', False):
                    print_color(f"Permission denied writing: {filepath}", Colors.RED)
                self.stats["files_skipped"] += 1
                return False
            except Exception as e:
                if not getattr(args, 'quiet', False):
                    print_color(f"Error writing {filepath}: {e}", Colors.RED)
                self.stats["files_skipped"] += 1
                return False
        else:
            self.stats["files_changed"] += 1
            if getattr(args, 'verbose', False):
                change_summary = ", ".join([c.split(":")[0] for c in changes[:3]])
                if len(changes) > 3:
                    change_summary += f" and {len(changes) - 3} more"
                print_color(f"Would fix: {filepath} ({change_summary})", Colors.GREEN)
            return True

    def compare_files(self, file1: Path, file2: Path, args):
        result = self.compare_files_indentation(file1, file2)

        if "error" in result:
            print_color(f"Error: {result['error']}", Colors.RED)
            return

        print_color(f"\n{Colors.CYAN}Comparison between {file1} and {file2}:{Colors.END}")
        print_color(f"File 1: {result['total_lines_file1']} lines", Colors.BLUE)
        print_color(f"File 2: {result['total_lines_file2']} lines", Colors.BLUE)

        if result["indent_matches"]:
            print_color("✓ Indentation styles match", Colors.GREEN)
        else:
            print_color(
                f"✗ Found {len(result['differences'])} indentation differences:",
                Colors.YELLOW,
            )

            for diff in result["differences"][:10]:
                print_color(f"\nLine {diff['line']}:", Colors.CYAN)
                print_color(
                    f"  {file1.name}: {'TAB' if diff['file1']['uses_tabs'] else 'SPACE'}",
                    Colors.RED if diff["file1"]["uses_tabs"] else Colors.GREEN,
                )
                print_color(
                    f"    Indent: {diff['file1']['indent']}, Preview: {diff['file1']['preview']}",
                    Colors.DIM,
                )
                print_color(
                    f"  {file2.name}: {'TAB' if diff['file2']['uses_tabs'] else 'SPACE'}",
                    Colors.RED if diff["file2"]["uses_tabs"] else Colors.GREEN,
                )
                print_color(
                    f"    Indent: {diff['file2']['indent']}, Preview: {diff['file2']['preview']}",
                    Colors.DIM,
                )

            if len(result["differences"]) > 10:
                print_color(
                    f"\n... and {len(result['differences']) - 10} more differences",
                    Colors.DIM,
                )

    def print_stats(self, args):
        if args.quiet:
            return

        print_color(f"\n{'='*60}", Colors.CYAN)
        print_color("PROCESSING STATISTICS", Colors.BOLD + Colors.CYAN)
        print_color(f"{'='*60}", Colors.CYAN)

        stats_items = [
            (f"Files processed:      ", self.stats["files_processed"], Colors.BLUE),
            (
                f"Files changed:        ",
                self.stats["files_changed"],
                Colors.GREEN if self.stats["files_changed"] > 0 else Colors.DIM,
            ),
            (
                f"Files skipped:        ",
                self.stats["files_skipped"],
                Colors.YELLOW if self.stats["files_skipped"] > 0 else Colors.DIM,
            ),
            (
                f"Binary files skipped: ",
                self.stats["binary_files_skipped"],
                Colors.YELLOW if self.stats["binary_files_skipped"] > 0 else Colors.DIM,
            ),
            (
                f"Tabs replaced:        ",
                self.stats["tabs_replaced"],
                Colors.GREEN if self.stats["tabs_replaced"] > 0 else Colors.DIM,
            ),
            (
                f"Lines fixed:          ",
                self.stats["lines_fixed"],
                Colors.GREEN if self.stats["lines_fixed"] > 0 else Colors.DIM,
            ),
            (
                f"BOM markers removed:  ",
                self.stats["bom_removed"],
                Colors.MAGENTA if self.stats["bom_removed"] > 0 else Colors.DIM,
            ),
            (
                f"JSON files formatted: ",
                self.stats["json_formatted"],
                Colors.MAGENTA if self.stats["json_formatted"] > 0 else Colors.DIM,
            ),
            (
                f"Mixed indent files:   ",
                self.stats["mixed_indent_files"],
                Colors.RED if self.stats["mixed_indent_files"] > 0 else Colors.DIM,
            ),
        ]

        for label, value, color in stats_items:
            print_color(f"{label}{value:,}", color)

        if self.stats["files_processed"] > 0:
            changed_percent = (self.stats["files_changed"] / self.stats["files_processed"]) * 100
            print_color(
                f"\n{changed_percent:.1f}% of files were modified",
                Colors.GREEN if changed_percent > 0 else Colors.DIM,
            )


def main():
    parser = argparse.ArgumentParser(
        description="Advanced tab/space indentation fixer with extended features",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tabfix --recursive --remove-bom -v -m -t .
  tabfix --git-staged --interactive
  tabfix --format-json data.json
  tabfix --diff file1.py file2.py
  tabfix --progress --recursive src/
""",
    )

    parser.add_argument("paths", nargs="*", help="Files or directories to process")
    parser.add_argument(
        "-s",
        "--spaces",
        type=int,
        default=4,
        help="Number of spaces per tab (default: 4)",
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="Process directories recursively"
    )

    git_group = parser.add_argument_group("Git integration")
    git_group.add_argument(
        "--git-staged", action="store_true", help="Process only staged files in git"
    )
    git_group.add_argument(
        "--git-unstaged", action="store_true", help="Process only unstaged files in git"
    )
    git_group.add_argument(
        "--git-all-changed",
        action="store_true",
        help="Process all changed files in git",
    )
    git_group.add_argument(
        "--no-gitignore", action="store_true", help="Do not use .gitignore patterns"
    )

    encoding_group = parser.add_argument_group('Encoding and binary file handling')
    encoding_group.add_argument('--skip-binary', action='store_true', default=True,
                              help='Skip files that appear to be binary (default: True)')
    encoding_group.add_argument('--no-skip-binary', action='store_false', dest='skip_binary',
                              help='Process files even if they appear to be binary')
    encoding_group.add_argument('--force-encoding', metavar='ENCODING',
                              help='Force specific encoding (skip auto-detection)')
    encoding_group.add_argument('--fallback-encoding', default='latin-1',
                              help='Fallback encoding when detection fails (default: latin-1)')
    encoding_group.add_argument('--warn-encoding', action='store_true',
                              help='Warn when encoding detection is uncertain')
    encoding_group.add_argument('--max-file-size', type=int, default=10*1024*1024,
                              help='Maximum file size to process in bytes (default: 10MB)')

    filetype_group = parser.add_argument_group('File type specific processing')
    filetype_group.add_argument('--smart-processing', action='store_true', default=True,
                              help='Enable smart processing for different file types (default: True)')
    filetype_group.add_argument('--no-smart-processing', action='store_false', dest='smart_processing',
                              help='Disable smart processing for different file types')
    filetype_group.add_argument('--preserve-quotes', action='store_true',
                              help='Preserve original string quotes in code files')

    parser.add_argument(
        "--diff",
        nargs=2,
        metavar=("FILE1", "FILE2"),
        help="Compare indentation between two files",
    )
    parser.add_argument(
        "--format-json",
        action="store_true",
        help="Format JSON files with proper indentation",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Interactive mode (confirm each change)",
    )
    parser.add_argument(
        "--progress", action="store_true", help="Show progress bar during processing"
    )
    parser.add_argument("--remove-bom", action="store_true", help="Remove UTF-8 BOM marker")
    parser.add_argument("--keep-bom", action="store_true", help="Preserve existing BOM marker")

    parser.add_argument(
        "-m",
        "--fix-mixed",
        action="store_true",
        help="Fix mixed tabs/spaces indentation",
    )
    parser.add_argument(
        "-t", "--fix-trailing", action="store_true", help="Remove trailing whitespace"
    )
    parser.add_argument(
        "-f",
        "--final-newline",
        action="store_true",
        help="Ensure file ends with newline",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show changes without modifying files"
    )
    parser.add_argument("--backup", action="store_true", help="Create backup files (.bak)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode (minimal output)")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")

    args = parser.parse_args()

    if args.no_color:
        global Colors
        Colors = type("Colors", (), {k: "" for k in dir(Colors) if not k.startswith("_")})()

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
        for path_str in args.paths or ["."]:
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
            if args.paths and args.paths != ["."]:
                print_color(f"No matching files found in: {', '.join(args.paths)}", Colors.YELLOW)
            else:
                print_color("No files to process in current directory.", Colors.YELLOW)
        return

    if args.progress and HAS_TQDM and not args.interactive:
        if not args.quiet:
            print_color(f"Processing {len(processed_files):,} files...", Colors.CYAN)
        iterator = tqdm(processed_files, desc="Processing", unit="file", disable=args.quiet)
    elif args.progress and not HAS_TQDM and not args.quiet:
        print_color("Progress: Install 'tqdm' for better progress bar", Colors.YELLOW)
        print_color(f"Processing {len(processed_files):,} files...", Colors.CYAN)
        iterator = enumerate(processed_files)
        total = len(processed_files)
    else:
        iterator = processed_files

    for item in iterator:
        if args.progress and not HAS_TQDM and not args.interactive:
            idx, filepath = item
            if idx % 100 == 0 and not args.quiet:
                percent = (idx / total) * 100
                print_color(
                    f"Progress: {idx:,}/{total:,} files ({percent:.1f}%)",
                    Colors.CYAN,
                    end="\r",
                )
            fixer.process_file(filepath, args, gitignore_matcher)
        else:
            filepath = item
            fixer.process_file(filepath, args, gitignore_matcher)

    if args.progress and not HAS_TQDM and not args.quiet and not args.interactive:
        print()

    fixer.print_stats(args)


if __name__ == "__main__":
    main()
