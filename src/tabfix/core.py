#!/usr/bin/env python3
"""
tabfix — Advanced tab/space indentation fixer with autoformatting.

Fixes applied in this version:
  [BUG-1]  BOM detection: UTF-32 checks now come BEFORE UTF-16 (were unreachable).
  [BUG-2]  fix_mixed_indentation: only leading whitespace is touched, not in-line tabs.
  [BUG-3]  files_changed no longer incremented during --dry-run / --check-only.
  [BUG-4]  disable_colors() propagates across all modules via module-level flag.
  [BUG-5]  process_file_with_changes: binary / UnicodeDecodeError fully handled.
  [BUG-6]  fix_json_issues: trailing-comma removal logic fixed.
  [BUG-7]  process_javascript: removed trailing-space padding of import lines
           (conflicted with --fix-trailing).
  [BUG-8]  mixed_indent_files stat is now actually incremented.
  [BUG-9]  Stats increments are thread-safe (threading.Lock).
  [BUG-10] interactive_confirm: handles EOF gracefully.

New features:
  [NEW-1]  TabFix.fix_string()         — process a raw string (used by API).
  [NEW-2]  TabFix.normalize_line_endings() + --normalize-endings flag (CRLF→LF).
  [NEW-3]  --check-only flag           — CI mode, exits with code 1 if changes needed.
  [NEW-4]  --json-report PATH          — saves machine-readable stats to a JSON file.
  [NEW-5]  TabFix.export_stats()       — public dict for programmatic use.
  [NEW-6]  files_would_change counter  — separate from files_changed for dry-run.
  [NEW-7]  crlf_normalized counter.
"""

import sys
import os
import argparse
import re
import json
import subprocess
import shutil
import fnmatch
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
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
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    BLUE    = "\033[94m"
    CYAN    = "\033[96m"
    MAGENTA = "\033[95m"
    END     = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"


# Module-level flag; call disable_colors() once to turn off
# ANSI output in ALL modules that import print_color from this module.
_use_colors: bool = True


def disable_colors() -> None:
    """Disable ANSI colour codes globally for the entire tabfix package."""
    global _use_colors
    _use_colors = False


def print_color(text: str, color: str = Colors.END, end: str = "\n") -> None:
    if sys.stdout.isatty() and _use_colors:
        print(f"{color}{text}{Colors.END}", end=end)
    else:
        print(text, end=end)


class GitignoreMatcher:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir.resolve()
        self.patterns: List[str] = []
        self._load_gitignore()

    def _load_gitignore(self) -> None:
        for candidate in (
            self.root_dir / ".gitignore",
            self.root_dir / ".git" / "info" / "exclude",
        ):
            if candidate.exists():
                try:
                    with open(candidate, encoding="utf-8") as fh:
                        for line in fh:
                            line = line.strip()
                            if not line or line.startswith("#") or line.startswith("!"):
                                continue
                            self.patterns.append(line if "/" in line else f"**/{line}")
                except OSError:
                    pass

        # Sensible hard-coded defaults
        self.patterns.extend([
            ".git/", ".svn/", ".hg/", ".bzr/",
            ".idea/", ".vscode/",
            "__pycache__/", "*.pyc", "*.pyo", "*.pyd",
            "*.so", "*.dylib",
            "*.egg-info/", "*.egg", "dist/", "build/",
            "*.log", "*.sqlite3", "*.db",
            "*.venv", "venv/",
            "node_modules/", "bower_components/",
            ".cache/", "coverage/",
            ".tox/", ".nox/",
            ".pytest_cache/", ".mypy_cache/", ".hypothesis/",
        ])

    def should_ignore(self, path: Path) -> bool:
        try:
            rel_str = str(path.resolve().relative_to(self.root_dir)).replace("\\", "/")
        except ValueError:
            return False
        if rel_str == ".":
            return False
        for pattern in self.patterns:
            if pattern.endswith("/"):
                d = pattern[:-1]
                if rel_str == d or rel_str.startswith(d + "/") or fnmatch.fnmatch(rel_str, d):
                    return True
            elif fnmatch.fnmatch(rel_str, pattern) or fnmatch.fnmatch(path.name, pattern):
                return True
        return False

class EncodingDetector:
    def __init__(self, confidence_threshold: float = 0.8) -> None:
        self.confidence_threshold = confidence_threshold

    def detect_with_chardet(self, content: bytes) -> Optional[Tuple[str, float]]:
        if HAS_CHARDET:
            try:
                r = chardet.detect(content)
                if r["encoding"] and r["confidence"] > self.confidence_threshold:
                    return r["encoding"], r["confidence"]
            except Exception:
                pass
        if HAS_CHARSET_NORMALIZER:
            try:
                r = charset_detect(content)
                if r and r["encoding"]:
                    return r["encoding"], r["confidence"]
            except Exception:
                pass
        return None

    def analyze_byte_patterns(self, content: bytes) -> str:
        if len(content) < 4:
            return "utf-8"
        # Check 4-byte BOMs BEFORE 2-byte BOMs (UTF-16 BOM is a prefix of UTF-32 BOM)
        if content.startswith(b"\xff\xfe\x00\x00"):
            return "utf-32-le"
        if content.startswith(b"\x00\x00\xfe\xff"):
            return "utf-32-be"
        if content.startswith(b"\xff\xfe"):
            return "utf-16-le"
        if content.startswith(b"\xfe\xff"):
            return "utf-16-be"

        utf8_valid = latin1_valid = 0
        n = len(content)
        i = 0
        while i < min(n, 1000):
            b = content[i]
            if b < 128:
                utf8_valid += 1
            elif 194 <= b <= 223 and i + 1 < n and 128 <= content[i + 1] <= 191:
                utf8_valid += 2; i += 1
            elif 224 <= b <= 239 and i + 2 < n and 128 <= content[i+1] <= 191 and 128 <= content[i+2] <= 191:
                utf8_valid += 3; i += 2
            elif 240 <= b <= 244 and i + 3 < n and 128 <= content[i+1] <= 191 and 128 <= content[i+2] <= 191 and 128 <= content[i+3] <= 191:
                utf8_valid += 4; i += 3
            latin1_valid += 1
            i += 1
        return "utf-8" if utf8_valid > latin1_valid * 1.1 else "latin-1"

    def get_encoding_for_region(self, filename: str) -> Optional[str]:
        fn = filename.lower()
        if any(x in fn for x in (".ru.", ".rus.", "russian")):
            return "cp1251"
        if any(x in fn for x in (".jp.", ".jpn.", "japanese")):
            return "shift_jis"
        if any(x in fn for x in (".cn.", ".chs.", "chinese")):
            return "gbk"
        if any(x in fn for x in (".tw.", ".cht.", "traditional")):
            return "big5"
        return None

class FileProcessor:
    def __init__(self, spaces_per_tab: int = 4, preserve_quotes: bool = False) -> None:
        self.spaces_per_tab  = spaces_per_tab
        self.preserve_quotes = preserve_quotes
        self.processors = {
            ".py":          self.process_python,
            ".js":          self.process_javascript,
            ".jsx":         self.process_javascript,
            ".ts":          self.process_typescript,
            ".tsx":         self.process_typescript,
            ".json":        self.process_json,
            ".yaml":        self.process_yaml,
            ".yml":         self.process_yaml,
            ".md":          self.process_markdown,
            ".markdown":    self.process_markdown,
            ".html":        self.process_html,
            ".htm":         self.process_html,
            ".css":         self.process_css,
            ".scss":        self.process_scss,
            ".sass":        self.process_sass,
            ".xml":         self.process_xml,
            ".svg":         self.process_xml,
            ".txt":         self.process_text,
            ".csv":         self.process_csv,
            ".ini":         self.process_ini,
            ".cfg":         self.process_ini,
            ".toml":        self.process_toml,
            ".sh":          self.process_shell,
            ".bash":        self.process_shell,
            ".zsh":         self.process_shell,
            ".dockerfile":  self.process_docker,
            "dockerfile":   self.process_docker,
            ".gitignore":   self.process_gitignore,
            ".editorconfig": self.process_editorconfig,
        }

    def process_by_extension(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        suffix = filepath.suffix.lower()
        if filepath.name.lower() == "dockerfile":
            suffix = "dockerfile"
        return self.processors.get(suffix, self.process_generic)(content, filepath)

    def process_python(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes: List[str] = []
        lines = content.split("\n")
        if lines and lines[0].startswith("#!") and "python" in lines[0] and "python3" not in lines[0]:
            lines[0] = "#!/usr/bin/env python3"
            changes.append("Fixed shebang to python3")
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            if line != stripped and (line.strip().startswith("#") or not line.strip()):
                lines[i] = stripped
                changes.append(f"Line {i+1}: Removed trailing spaces in comment/blank")
        return "\n".join(lines), changes

    def process_javascript(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        """
        Previous version padded import lines with trailing spaces for alignment,
        which directly conflicted with --fix-trailing.  Removed that behaviour.
        """
        changes: List[str] = []
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "export ", "from ")):
                rstripped = line.rstrip()
                if rstripped != line:
                    lines[i] = rstripped
                    changes.append(f"Line {i+1}: Removed trailing spaces in import/export")
        return "\n".join(lines), changes

    def process_typescript(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        return self.process_javascript(content, filepath)

    def process_json(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes: List[str] = []
        try:
            parsed = json.loads(content)
            formatted = json.dumps(parsed, indent=self.spaces_per_tab, ensure_ascii=False, sort_keys=False)
            if not formatted.endswith("\n"):
                formatted += "\n"
            if formatted != content:
                changes.append("Formatted JSON")
                return formatted, changes
        except json.JSONDecodeError as e:
            fixed = self.fix_json_issues(content, preserve_quotes=self.preserve_quotes)
            if fixed != content:
                changes.append(f"Fixed JSON syntax: {str(e)[:50]}")
                return fixed, changes
        return content, changes

    def fix_json_issues(self, content: str, preserve_quotes: bool = False) -> str:
        """Correctly removes trailing commas before ] or }."""
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if not line.strip().endswith(","):
                continue
            # Find next non-empty line
            for j in range(i + 1, len(lines)):
                nxt = lines[j].strip()
                if not nxt:
                    continue
                # If next meaningful content is a closing bracket/brace, strip comma
                if nxt and nxt[0] in ("]", "}"):
                    lines[i] = line.rstrip()[:-1]   # remove trailing comma
                break

        fixed = "\n".join(lines)

        if preserve_quotes:
            return fixed

        # Replace single quotes with double quotes (outside of strings)
        in_string = escape_next = False
        result: List[str] = []
        for ch in fixed:
            if escape_next:
                result.append(ch); escape_next = False
            elif ch == "\\":
                result.append(ch); escape_next = True
            elif ch == '"':
                result.append(ch); in_string = not in_string
            elif ch == "'" and not in_string:
                result.append('"')
            else:
                result.append(ch)
        return "".join(result)

    def process_yaml(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes: List[str] = []
        try:
            import yaml
            yaml.safe_load(content)
        except ImportError:
            pass
        except Exception:
            return content, changes
        lines = content.split("\n")
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            if line != stripped:
                lines[i] = stripped
                changes.append(f"Line {i+1}: Removed trailing spaces")
        return "\n".join(lines), changes

    def process_markdown(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes: List[str] = []
        lines = content.split("\n")
        in_code_block = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            if stripped.startswith("#"):
                hashes = len(stripped) - len(stripped.lstrip("#"))
                if hashes < len(stripped) and stripped[hashes] != " ":
                    lines[i] = line.replace("#" * hashes, "#" * hashes + " ", 1)
                    changes.append(f"Line {i+1}: Fixed heading formatting")
            if stripped.startswith(("- ", "* ", "+ ")) and len(stripped) > 2 and stripped[2] == " ":
                lines[i] = line.replace(stripped[:3], stripped[:2], 1)
                changes.append(f"Line {i+1}: Fixed list formatting")
        return "\n".join(lines), changes

    def process_html(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes: List[str] = []
        lines = content.split("\n")
        for i, line in enumerate(lines):
            new = line.replace("<br>", "<br/>").replace("<hr>", "<hr/>")
            if new != line:
                lines[i] = new
                changes.append(f"Line {i+1}: Fixed self-closing tags")
        return "\n".join(lines), changes

    def process_css(self, c: str, fp: Path) -> Tuple[str, List[str]]:
        return self.process_generic(c, fp)

    def process_scss(self, c: str, fp: Path) -> Tuple[str, List[str]]:
        return self.process_generic(c, fp)

    def process_sass(self, c: str, fp: Path) -> Tuple[str, List[str]]:
        return self.process_generic(c, fp)

    def process_xml(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes: List[str] = []
        lines = content.split("\n")
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            if line != stripped:
                lines[i] = stripped
                changes.append(f"Line {i+1}: Removed trailing spaces")
        return "\n".join(lines), changes

    def process_text(self, c: str, fp: Path) -> Tuple[str, List[str]]:
        return self.process_generic(c, fp)

    def process_csv(self, c: str, fp: Path) -> Tuple[str, List[str]]:
        return self.process_generic(c, fp)

    def process_ini(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes: List[str] = []
        lines = content.split("\n")
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            if line != stripped:
                lines[i] = stripped
                changes.append(f"Line {i+1}: Removed trailing spaces")
        return "\n".join(lines), changes

    def process_toml(self, c: str, fp: Path) -> Tuple[str, List[str]]:
        return self.process_generic(c, fp)

    def process_shell(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes: List[str] = []
        lines = content.split("\n")
        if lines and lines[0].startswith("#!") and "bash" in lines[0] and "-e" not in lines[0]:
            lines[0] = "#!/usr/bin/env bash"
            changes.append("Standardized bash shebang")
        return "\n".join(lines), changes

    def process_docker(self, c: str, fp: Path) -> Tuple[str, List[str]]:
        return self.process_generic(c, fp)

    def process_gitignore(self, c: str, fp: Path) -> Tuple[str, List[str]]:
        return self.process_generic(c, fp)

    def process_editorconfig(self, c: str, fp: Path) -> Tuple[str, List[str]]:
        return self.process_generic(c, fp)

    def process_generic(self, content: str, filepath: Path) -> Tuple[str, List[str]]:
        changes: List[str] = []
        lines = content.split("\n")
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            if line != stripped:
                lines[i] = stripped
                changes.append(f"Line {i+1}: Removed trailing spaces")
        return "\n".join(lines), changes


class TabFix:
    def __init__(self, spaces_per_tab: int = 4) -> None:
        self.spaces_per_tab    = spaces_per_tab
        self.stats: Dict[str, int] = {
            "files_processed":      0,
            "files_changed":        0,
            "files_would_change":   0,
            "tabs_replaced":        0,
            "lines_fixed":          0,
            "bom_removed":          0,
            "json_formatted":       0,
            "mixed_indent_files":   0,
            "crlf_normalized":      0,
            "files_skipped":        0,
            "binary_files_skipped": 0,
        }
        self._lock             = threading.Lock()
        self.encoding_detector = EncodingDetector()
        self.file_processor    = FileProcessor(spaces_per_tab)

    def _inc(self, key: str, amount: int = 1) -> None:
        """Thread-safe stats increment."""
        with self._lock:
            self.stats[key] += amount

    def export_stats(self) -> Dict[str, Any]:
        """Return a copy of the stats dict (safe to call from any thread)."""
        with self._lock:
            return dict(self.stats)

    def remove_bom(self, content: bytes) -> Tuple[bytes, bool]:
        if content.startswith(b"\xef\xbb\xbf"):
            return content[3:], True
        return content, False

    def add_bom(self, content: bytes) -> bytes:
        return b"\xef\xbb\xbf" + content

    def format_json(self, content: str) -> Tuple[str, bool]:
        try:
            parsed    = json.loads(content)
            formatted = json.dumps(parsed, indent=self.spaces_per_tab, ensure_ascii=False)
            if not formatted.endswith("\n"):
                formatted += "\n"
            if formatted != content:
                return formatted, True
        except (json.JSONDecodeError, TypeError):
            pass
        return content, False

    def normalize_line_endings(self, content: str) -> Tuple[str, bool]:
        """Convert CRLF (\\r\\n) and stray CR (\\r) to LF (\\n)."""
        if "\r" not in content:
            return content, False
        return content.replace("\r\n", "\n").replace("\r", "\n"), True

    def fix_mixed_indentation(self, content: str) -> Tuple[str, List[str]]:
        """
        Only replaces tabs that are part of LEADING whitespace.
        In-line tabs (inside strings, TSV data, printf-alignment) are left alone.
        """
        lines: List[str] = []
        changes: List[str] = []
        for i, line in enumerate(content.split("\n"), 1):
            if "\t" not in line:
                lines.append(line)
                continue
            body    = line.lstrip()
            leading = line[: len(line) - len(body)]
            if "\t" in leading:
                new_leading = leading.replace("\t", " " * self.spaces_per_tab)
                fixed = new_leading + body
                lines.append(fixed)
                changes.append(f"Line {i}: Tabs → spaces")
            else:
                lines.append(line)
        return "\n".join(lines), changes

    def fix_mixed_indentation_python(self, content: str) -> Tuple[str, List[str]]:
        """
        Python-aware variant: skips lines inside triple-quoted strings/docstrings.
        """
        in_string = False
        delim = None
        lines: List[str] = []
        changes: List[str] = []

        for i, line in enumerate(content.split("\n"), 1):
            stripped = line.lstrip()
            # toggle string state on triple quotes that are not escaped
            if not in_string:
                if stripped.startswith(("'''", '"""')):
                    delim = stripped[:3]
                    in_string = True
            else:
                if delim and delim in line:
                    # close string if delimiter appears (naive but ok for fixer)
                    in_string = False

            if in_string or "\t" not in line:
                lines.append(line)
                continue

            body    = line.lstrip()
            leading = line[: len(line) - len(body)]
            if "\t" in leading:
                new_leading = leading.replace("\t", " " * self.spaces_per_tab)
                fixed = new_leading + body
                lines.append(fixed)
                changes.append(f"Line {i}: Tabs → spaces")
            else:
                lines.append(line)

        return "\n".join(lines), changes

    def fix_trailing_spaces(self, content: str) -> Tuple[str, List[str]]:
        lines: List[str] = []
        changes: List[str] = []
        for i, line in enumerate(content.split("\n"), 1):
            fixed = line.rstrip()
            if fixed != line:
                changes.append(f"Line {i}: Removed trailing spaces")
            lines.append(fixed)
        return "\n".join(lines), changes

    def ensure_final_newline(self, content: str) -> Tuple[str, List[str]]:
        if content and not content.endswith("\n"):
            return content + "\n", ["Added final newline"]
        return content, []

    def fix_string(self, content: str) -> Tuple[str, List[str]]:
        """
        Returns (processed_content, list_of_change_descriptions).
        Used by TabFixAPI.process_string().
        """
        all_changes: List[str] = []

        content, was_crlf = self.normalize_line_endings(content)
        if was_crlf:
            all_changes.append("Normalized CRLF → LF")

        fixed, ch = self.fix_mixed_indentation(content)
        if fixed != content:
            content = fixed
            all_changes.extend(ch)

        fixed, ch = self.fix_trailing_spaces(content)
        if fixed != content:
            content = fixed
            all_changes.extend(ch)

        fixed, ch = self.ensure_final_newline(content)
        if fixed != content:
            content = fixed
            all_changes.extend(ch)

        return content, all_changes

    def detect_indentation(self, content: str) -> Dict[str, Any]:
        tab_lines = space_lines = 0
        space_counts: List[int] = []
        for line in content.split("\n"):
            if not line.strip():
                continue
            if line.startswith("\t"):
                tab_lines += 1
            elif line.startswith(" "):
                space_lines += 1
                leading = len(line) - len(line.lstrip(" "))
                if leading:
                    space_counts.append(leading)
        common = Counter(space_counts).most_common(1)[0][0] if space_counts else None
        lines  = content.split("\n")
        return {
            "uses_tabs":      tab_lines > 0,
            "uses_spaces":    space_lines > 0,
            "common_indent":  common,
            "mixed":          tab_lines > 0 and space_lines > 0,
            "total_lines":    len(lines),
            "indented_lines": tab_lines + space_lines,
        }

    def detect_spaces_from_files(self, files: List[Path], sample_limit: int = 50) -> Optional[int]:
        """Infer most common indent size from a set of files."""
        counts: List[int] = []
        for fp in files[:sample_limit]:
            try:
                text = fp.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            info = self.detect_indentation(text)
            if info["common_indent"]:
                counts.append(info["common_indent"])
        return Counter(counts).most_common(1)[0][0] if counts else None

    def detect_encoding_and_decode(self, content: bytes, default_encoding: str = "utf-8") -> Tuple[str, str, bool]:
        def try_dec(data: bytes, enc: str) -> Optional[str]:
            try:
                return data.decode(enc)
            except (UnicodeDecodeError, LookupError):
                return None

        if content.startswith(b"\xef\xbb\xbf"):
            decoded = try_dec(content[3:], "utf-8")
            if decoded is not None:
                return decoded, "utf-8-sig", True

        decoded = try_dec(content, "utf-8")
        if decoded is not None:
            return decoded, "utf-8", True

        cr = self.encoding_detector.detect_with_chardet(content)
        if cr:
            decoded = try_dec(content, cr[0])
            if decoded is not None:
                return decoded, cr[0], cr[1] > 0.8

        for enc in ["utf-16", "utf-16-be", "utf-16-le", "cp1251", "cp1252",
                    "iso-8859-1", "iso-8859-2", "koi8-r", "cp866",
                    "shift_jis", "euc-jp", "gbk", "big5"]:
            decoded = try_dec(content, enc)
            if decoded is not None and self.looks_like_valid_text(decoded):
                return decoded, enc, False

        try:
            return content.decode(default_encoding, errors="replace"), default_encoding, False
        except (UnicodeDecodeError, LookupError):
            return content.decode("latin-1", errors="replace"), "latin-1", False

    def looks_like_valid_text(self, text: str, threshold: float = 0.7) -> bool:
        if not text:
            return False
        printable = sum(1 for c in text if c.isprintable() or c in "\n\r\t")
        ctrl      = sum(1 for c in text if ord(c) < 32 and c not in "\n\r\t")
        return (printable / len(text)) > threshold and (ctrl / len(text)) < 0.1

    def is_likely_binary(self, content: bytes, filename: Optional[str] = None) -> bool:
        if filename:
            binary_exts = {
                ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp",
                ".pdf", ".zip", ".tar", ".gz", ".bz2", ".xz", ".rar", ".7z",
                ".exe", ".dll", ".so", ".dylib", ".class",
                ".pyc", ".pyo", ".pyd", ".o", ".obj", ".a", ".lib",
                ".mp3", ".mp4", ".avi", ".mkv", ".mov",
                ".ttf", ".otf", ".woff", ".woff2",
                ".db", ".sqlite", ".mdb",
            }
            if any(filename.lower().endswith(e) for e in binary_exts):
                return True
        sample = content[:1024]
        if b"\x00" in sample:
            return True
        for sig in [b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a",
                    b"%PDF", b"PK\x03\x04", b"\x1f\x8b\x08", b"MZ", b"\x7fELF"]:
            if sample.startswith(sig):
                return True
        return False


    def compare_files_indentation(self, file1: Path, file2: Path) -> Dict[str, Any]:
        try:
            c1 = file1.read_text(encoding="utf-8-sig")
            c2 = file2.read_text(encoding="utf-8-sig")
        except OSError as e:
            return {"error": str(e)}

        lines1, lines2 = c1.split("\n"), c2.split("\n")
        diffs: List[Dict] = []
        for i in range(max(len(lines1), len(lines2))):
            l1 = lines1[i] if i < len(lines1) else ""
            l2 = lines2[i] if i < len(lines2) else ""
            i1 = len(l1) - len(l1.lstrip())
            i2 = len(l2) - len(l2.lstrip())
            t1 = "\t" in l1[:i1]
            t2 = "\t" in l2[:i2]
            if i1 != i2 or t1 != t2:
                diffs.append({
                    "line": i + 1,
                    "file1": {"indent": i1, "uses_tabs": t1, "preview": l1[:50] + ("..." if len(l1) > 50 else "")},
                    "file2": {"indent": i2, "uses_tabs": t2, "preview": l2[:50] + ("..." if len(l2) > 50 else "")},
                })
        return {
            "differences":       diffs,
            "total_lines_file1": len(lines1),
            "total_lines_file2": len(lines2),
            "indent_matches":    not diffs,
        }

    def compare_files(self, file1: Path, file2: Path, args) -> None:
        r = self.compare_files_indentation(file1, file2)
        if "error" in r:
            print_color(f"Error: {r['error']}", Colors.RED)
            return
        print_color(f"\n{Colors.CYAN}Comparison: {file1}  vs  {file2}{Colors.END}")
        print_color(f"File 1: {r['total_lines_file1']} lines", Colors.BLUE)
        print_color(f"File 2: {r['total_lines_file2']} lines", Colors.BLUE)
        if r["indent_matches"]:
            print_color("✓ Indentation styles match", Colors.GREEN)
        else:
            print_color(f"✗ {len(r['differences'])} difference(s):", Colors.YELLOW)
            for d in r["differences"][:10]:
                print_color(f"\n  Line {d['line']}:", Colors.CYAN)
                for key, fp in (("file1", file1), ("file2", file2)):
                    side  = d[key]
                    kind  = "TAB" if side["uses_tabs"] else "SPC"
                    color = Colors.RED if side["uses_tabs"] else Colors.GREEN
                    print_color(f"    {fp.name}: {kind} indent={side['indent']}  {side['preview']}", color)
            if len(r["differences"]) > 10:
                print_color(f"  ... and {len(r['differences']) - 10} more", Colors.DIM)

    def get_git_files(self, mode: str = "staged") -> List[Path]:
        try:
            if mode == "staged":
                res = subprocess.run(
                    ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                    capture_output=True, text=True, check=True,
                )
                return [Path(f) for f in res.stdout.splitlines() if f.strip()]

            elif mode == "unstaged":
                res = subprocess.run(
                    ["git", "diff", "--name-only", "--diff-filter=ACM"],
                    capture_output=True, text=True, check=True,
                )
                return [Path(f) for f in res.stdout.splitlines() if f.strip()]

            elif mode == "all_changed":
                res = subprocess.run(
                    ["git", "status", "--porcelain"],
                    capture_output=True, text=True, check=True,
                )
                files = []
                for line in res.stdout.splitlines():
                    if line and line[:2] != "??":
                        name = line[3:].strip()
                        if " -> " in name:         # handle renames
                            name = name.split(" -> ")[-1]
                        files.append(name)
                return [Path(f) for f in files if f]

        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        return []

    def interactive_confirm(self, filepath: Path, changes: List[str]) -> bool:
        if not changes:
            return True
        print_color(f"\n{Colors.CYAN}File:{Colors.END} {filepath}")
        print_color(f"{Colors.YELLOW}Proposed changes:{Colors.END}")
        for i, ch in enumerate(changes[:5], 1):
            print_color(f"  {i}. {ch}")
        if len(changes) > 5:
            print_color(f"  ... and {len(changes) - 5} more", Colors.DIM)
        while True:
            try:
                r = input(f"\nApply {len(changes)} change(s)? [y/n/a(ll)/q(uit)]: ").lower().strip()
            except EOFError:
                return False
            if r in ("y", "yes"):     return True
            if r in ("n", "no"):      return False
            if r in ("a", "all"):     return True
            if r in ("q", "quit"):    sys.exit(0)
            print_color("Please enter y, n, a, or q", Colors.RED)

    def summarize_changes(self, changes: List[str]) -> str:
        cats: Counter = Counter()
        for ch in changes:
            cl = ch.lower()
            if "trailing" in cl:           cats["trailing"] += 1
            elif "tab" in cl or "indent" in cl: cats["indent"] += 1
            elif "crlf" in cl or "ending" in cl: cats["endings"] += 1
            elif "bom" in ch.upper():      cats["bom"] += 1
            elif "json" in cl:             cats["json"] += 1
            elif "import" in cl or "export" in cl: cats["imports"] += 1
            elif "shebang" in cl:          cats["shebang"] += 1
            elif "heading" in cl or "list" in cl:  cats["markdown"] += 1
            else:                          cats["other"] += 1
        parts = []
        for k, label in [("trailing","trailing spaces"), ("indent","indentation fixes"),
                          ("endings","CRLF→LF"), ("bom","BOM removals"), ("json","JSON formats"),
                          ("imports","import fixes"), ("shebang","shebang fixes"),
                          ("markdown","markdown fixes"), ("other","other")]:
            if cats[k]:
                parts.append(f"{cats[k]} {label}")
        return ", ".join(parts) or "no changes"

    def process_file(
        self,
        filepath:          Path,
        args,
        gitignore_matcher: Optional[GitignoreMatcher] = None,
    ) -> bool:
        """
        Process a single file.  Returns True if the file was changed
        (or would be changed in dry-run / check-only mode).
        """
        # --- Skip .git internals ---
        if ".git" in filepath.as_posix().split("/"):
            self._inc("files_skipped")
            return False

        if gitignore_matcher and gitignore_matcher.should_ignore(filepath):
            if getattr(args, "verbose", False):
                print_color(f"Skipped (gitignore): {filepath}", Colors.DIM)
            self._inc("files_skipped")
            return False

        try:
            if not filepath.is_file():
                return False
            size = filepath.stat().st_size
            if size > getattr(args, "max_file_size", 10 * 1024 * 1024):
                if getattr(args, "verbose", False):
                    print_color(f"Skipped (too large, {size/1048576:.1f} MB): {filepath}", Colors.YELLOW)
                return False
            with open(filepath, "rb") as fh:
                raw = fh.read()
        except PermissionError:
            if not getattr(args, "quiet", False):
                print_color(f"Permission denied reading: {filepath}", Colors.RED)
            self._inc("files_skipped")
            return False
        except OSError as e:
            if not getattr(args, "quiet", False):
                print_color(f"Error reading {filepath}: {e}", Colors.RED)
            self._inc("files_skipped")
            return False

        if getattr(args, "skip_binary", True) and self.is_likely_binary(raw, filepath.name):
            self._inc("binary_files_skipped")
            return False

        original_raw = raw
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            self._inc("binary_files_skipped")
            if getattr(args, "verbose", False):
                print_color(f"Skipped (binary/unreadable): {filepath}", Colors.DIM)
            return False

        had_bom  = raw.startswith(b"\xef\xbb\xbf")
        changes: List[str] = []

        if getattr(args, "normalize_endings", False):
            content, was_crlf = self.normalize_line_endings(content)
            if was_crlf:
                changes.append("Normalized CRLF → LF")
                self._inc("crlf_normalized")

        if getattr(args, "remove_bom", False) and had_bom:
            changes.append("Removed BOM")

        if getattr(args, "format_json", False) and filepath.suffix.lower() == ".json":
            fmt, changed = self.format_json(content)
            if changed:
                content = fmt
                changes.append("Formatted JSON")
                self._inc("json_formatted")

        if getattr(args, "smart_processing", True):
            # Respect CLI/Config flag: do not rewrite quotes when preserving them
            self.file_processor.preserve_quotes = getattr(args, "preserve_quotes", False)
            content, sc = self.file_processor.process_by_extension(content, filepath)
            changes.extend(sc)

        if getattr(args, "fix_mixed", False):
            if filepath.suffix.lower() == ".py" and getattr(args, "respect_strings", False):
                fixed, ic = self.fix_mixed_indentation_python(content)
            else:
                fixed, ic = self.fix_mixed_indentation(content)
            if fixed != content:
                if self.detect_indentation(content)["mixed"]:
                    self._inc("mixed_indent_files")
                content = fixed
                changes.extend(ic)
                self._inc("tabs_replaced", len(ic))
                self._inc("lines_fixed",   len(ic))

        if getattr(args, "fix_trailing", False):
            fixed, tc = self.fix_trailing_spaces(content)
            if fixed != content:
                content = fixed
                changes.extend(tc)
                self._inc("lines_fixed", len(tc))

        if getattr(args, "final_newline", False):
            content, nc = self.ensure_final_newline(content)
            changes.extend(nc)

        if not changes:
            self._inc("files_processed")
            return False

        if getattr(args, "interactive", False) and not self.interactive_confirm(filepath, changes):
            self._inc("files_processed")
            return False

        # Encode back
        if getattr(args, "keep_bom", False) and had_bom:
            new_raw = self.add_bom(content.encode("utf-8"))
        elif had_bom and not getattr(args, "remove_bom", False):
            new_raw = self.add_bom(content.encode("utf-8"))
        else:
            new_raw = content.encode("utf-8")

        if new_raw == original_raw:
            self._inc("files_processed")
            return False

        self._inc("files_processed")
        summary = self.summarize_changes(changes)

        # dry-run / check-only: do NOT increment files_changed
        if getattr(args, "dry_run", False) or getattr(args, "check_only", False):
            self._inc("files_would_change")
            if getattr(args, "verbose", False):
                print_color(f"Would fix: {filepath} ({summary})", Colors.YELLOW)
            return True

        if getattr(args, "backup", False):
            try:
                filepath.with_suffix(filepath.suffix + ".bak").write_bytes(original_raw)
            except OSError as e:
                if not getattr(args, "quiet", False):
                    print_color(f"Warning: backup failed for {filepath}: {e}", Colors.YELLOW)

        try:
            filepath.write_bytes(new_raw)
            if had_bom and getattr(args, "remove_bom", False):
                self._inc("bom_removed")
            self._inc("files_changed")
            if getattr(args, "verbose", False):
                print_color(f"Fixed: {filepath} ({summary})", Colors.GREEN)
            return True
        except PermissionError:
            if not getattr(args, "quiet", False):
                print_color(f"Permission denied writing: {filepath}", Colors.RED)
            self._inc("files_skipped")
            return False
        except OSError as e:
            if not getattr(args, "quiet", False):
                print_color(f"Error writing {filepath}: {e}", Colors.RED)
            self._inc("files_skipped")
            return False

    def process_file_with_changes(
        self,
        filepath:          Path,
        args,
        gitignore_matcher: Optional[GitignoreMatcher] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Like process_file() but also returns the change-description list.
        """
        if gitignore_matcher and gitignore_matcher.should_ignore(filepath):
            self._inc("files_skipped")
            return False, []

        try:
            if not filepath.is_file():
                return False, []
            if filepath.stat().st_size > getattr(args, "max_file_size", 10 * 1024 * 1024):
                return False, []
            with open(filepath, "rb") as fh:
                raw = fh.read()
        except OSError:
            return False, []

        if getattr(args, "skip_binary", True) and self.is_likely_binary(raw, filepath.name):
            self._inc("binary_files_skipped")
            return False, []

        original_raw = raw
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            self._inc("binary_files_skipped")
            return False, []

        had_bom  = raw.startswith(b"\xef\xbb\xbf")
        changes: List[str] = []

        if getattr(args, "normalize_endings", False):
            content, was_crlf = self.normalize_line_endings(content)
            if was_crlf:
                changes.append("Normalized CRLF → LF")

        if getattr(args, "remove_bom", False) and had_bom:
            changes.append("Removed BOM")

        if getattr(args, "format_json", False) and filepath.suffix.lower() == ".json":
            fmt, changed = self.format_json(content)
            if changed:
                content = fmt
                changes.append("Formatted JSON")

        if getattr(args, "fix_mixed", False):
            if filepath.suffix.lower() == ".py" and getattr(args, "respect_strings", False):
                fixed, ic = self.fix_mixed_indentation_python(content)
            else:
                fixed, ic = self.fix_mixed_indentation(content)
            if fixed != content:
                content = fixed
                changes.extend(ic)

        if getattr(args, "fix_trailing", False):
            fixed, tc = self.fix_trailing_spaces(content)
            if fixed != content:
                content = fixed
                changes.extend(tc)

        if getattr(args, "final_newline", False):
            content, nc = self.ensure_final_newline(content)
            changes.extend(nc)

        if not changes:
            return False, []

        if getattr(args, "interactive", False) and not self.interactive_confirm(filepath, changes):
            return False, []

        new_raw = content.encode("utf-8")
        if getattr(args, "keep_bom", False) and had_bom:
            new_raw = self.add_bom(new_raw)

        if new_raw == original_raw:
            return False, []

        if getattr(args, "dry_run", False) or getattr(args, "check_only", False):
            return True, changes

        if getattr(args, "backup", False):
            try:
                filepath.with_suffix(filepath.suffix + ".bak").write_bytes(original_raw)
            except OSError:
                pass

        try:
            filepath.write_bytes(new_raw)
            if had_bom and getattr(args, "remove_bom", False):
                self._inc("bom_removed")
            self._inc("files_changed")
            return True, changes
        except OSError:
            self._inc("files_skipped")
            return False, []

    def print_stats(self, args) -> None:
        if getattr(args, "quiet", False):
            return

        s = self.stats
        print_color(f"\n{'='*60}", Colors.CYAN)
        print_color("PROCESSING STATISTICS", Colors.BOLD + Colors.CYAN)
        print_color(f"{'='*60}", Colors.CYAN)

        rows = [
            ("Files processed:       ", s["files_processed"],
             Colors.BLUE),
            ("Files changed:         ", s["files_changed"],
             Colors.GREEN  if s["files_changed"]        > 0 else Colors.DIM),
            ("Files would change:    ", s["files_would_change"],
             Colors.YELLOW if s["files_would_change"]   > 0 else Colors.DIM),
            ("Files skipped:         ", s["files_skipped"],
             Colors.YELLOW if s["files_skipped"]        > 0 else Colors.DIM),
            ("Binary files skipped:  ", s["binary_files_skipped"],
             Colors.YELLOW if s["binary_files_skipped"] > 0 else Colors.DIM),
            ("Tabs replaced:         ", s["tabs_replaced"],
             Colors.GREEN  if s["tabs_replaced"]        > 0 else Colors.DIM),
            ("Lines fixed:           ", s["lines_fixed"],
             Colors.GREEN  if s["lines_fixed"]          > 0 else Colors.DIM),
            ("CRLF normalized:       ", s["crlf_normalized"],
             Colors.GREEN  if s["crlf_normalized"]      > 0 else Colors.DIM),
            ("BOM markers removed:   ", s["bom_removed"],
             Colors.MAGENTA if s["bom_removed"]         > 0 else Colors.DIM),
            ("JSON files formatted:  ", s["json_formatted"],
             Colors.MAGENTA if s["json_formatted"]      > 0 else Colors.DIM),
            ("Mixed-indent files:    ", s["mixed_indent_files"],
             Colors.RED    if s["mixed_indent_files"]   > 0 else Colors.DIM),
        ]
        for label, value, color in rows:
            print_color(f"{label}{value:,}", color)

        if s["files_processed"] > 0:
            pct = s["files_changed"] / s["files_processed"] * 100
            print_color(
                f"\n{pct:.1f}% of processed files were modified",
                Colors.GREEN if pct > 0 else Colors.DIM,
            )
        json_report = getattr(args, "json_report", None)
        if json_report:
            try:
                with open(Path(json_report), "w", encoding="utf-8") as fh:
                    json.dump(self.export_stats(), fh, indent=2)
                print_color(f"\nStats saved → {json_report}", Colors.CYAN)
            except OSError as e:
                print_color(f"Failed to write JSON report: {e}", Colors.RED)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Advanced tab/space indentation fixer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tabfix -r --fix-mixed --fix-trailing .
  tabfix --git-staged --interactive
  tabfix --format-json data.json
  tabfix --diff file1.py file2.py
  tabfix --check-only -r src/       # CI: exit 1 if any file needs changes
  tabfix --normalize-endings -r .
  tabfix --json-report stats.json -r .
""",
    )
    parser.add_argument("paths", nargs="*", default=["."])
    parser.add_argument("-s", "--spaces", type=int, default=4)
    parser.add_argument("-r", "--recursive", action="store_true")

    g = parser.add_argument_group("Git")
    g.add_argument("--git-staged",      action="store_true")
    g.add_argument("--git-unstaged",    action="store_true")
    g.add_argument("--git-all-changed", action="store_true")
    g.add_argument("--no-gitignore",    action="store_true")

    e = parser.add_argument_group("Encoding")
    e.add_argument("--skip-binary",     action="store_true", default=True)
    e.add_argument("--no-skip-binary",  action="store_false", dest="skip_binary")
    e.add_argument("--max-file-size",   type=int, default=10 * 1024 * 1024)

    f = parser.add_argument_group("Formatting")
    f.add_argument("-m", "--fix-mixed",         action="store_true")
    f.add_argument("-t", "--fix-trailing",       action="store_true")
    f.add_argument("-f", "--final-newline",      action="store_true")
    f.add_argument("--remove-bom",               action="store_true")
    f.add_argument("--keep-bom",                 action="store_true")
    f.add_argument("--format-json",              action="store_true")
    f.add_argument("--normalize-endings",        action="store_true")
    f.add_argument("--smart-processing",         action="store_true", default=True)
    f.add_argument("--no-smart-processing",      action="store_false", dest="smart_processing")

    m = parser.add_argument_group("Mode")
    m.add_argument("-i", "--interactive", action="store_true")
    m.add_argument("--progress",          action="store_true")
    m.add_argument("--dry-run",           action="store_true")
    m.add_argument("--check-only",        action="store_true",
                   help="Report changes needed and exit 1 if any (CI-friendly)")
    m.add_argument("--backup",            action="store_true")
    m.add_argument("--diff",              nargs=2, metavar=("FILE1", "FILE2"))
    m.add_argument("--json-report",       metavar="PATH")

    o = parser.add_argument_group("Output")
    o.add_argument("-v", "--verbose", action="store_true")
    o.add_argument("-q", "--quiet",   action="store_true")
    o.add_argument("--no-color",      action="store_true")

    args = parser.parse_args()

    if args.no_color:
        disable_colors()

    if getattr(args, "remove_bom", False) and getattr(args, "keep_bom", False):
        print_color("Cannot use both --remove-bom and --keep-bom", Colors.RED)
        sys.exit(1)

    fixer = TabFix(spaces_per_tab=args.spaces)

    if args.diff:
        fixer.compare_files(Path(args.diff[0]), Path(args.diff[1]), args)
        return

    files_to_process: List[Path] = []
    if args.git_staged or args.git_unstaged or args.git_all_changed:
        mode = "staged" if args.git_staged else ("unstaged" if args.git_unstaged else "all_changed")
        files_to_process = fixer.get_git_files(mode)
    else:
        for ps in args.paths:
            p = Path(ps)
            if not p.exists():
                if not args.quiet:
                    print_color(f"Warning: not found: {p}", Colors.YELLOW)
                continue
            if p.is_file():
                files_to_process.append(p)
            elif p.is_dir():
                files_to_process.extend(
                    f for f in p.glob("**/*" if args.recursive else "*") if f.is_file()
                )

    if not files_to_process:
        if not args.quiet:
            print_color("No files to process", Colors.YELLOW)
        return

    gitignore_matcher: Optional[GitignoreMatcher] = None
    if not args.no_gitignore:
        root = Path.cwd()
        for fp in files_to_process:
            cand = (fp if fp.is_absolute() else Path.cwd() / fp).parent
            if (cand / ".gitignore").exists():
                root = cand
                break
        gitignore_matcher = GitignoreMatcher(root)

    files_to_process = [
        fp for fp in files_to_process
        if not gitignore_matcher or not gitignore_matcher.should_ignore(fp)
    ]
    if not files_to_process:
        if not args.quiet:
            print_color("No files after .gitignore filter", Colors.YELLOW)
        return

    it = tqdm(files_to_process, desc="Processing", unit="file", disable=args.quiet) \
        if args.progress and HAS_TQDM and not args.interactive else files_to_process

    for fp in it:
        fixer.process_file(fp, args, gitignore_matcher)

    fixer.print_stats(args)

    if getattr(args, "check_only", False) and fixer.stats["files_would_change"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
