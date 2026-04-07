from pathlib import Path
import os

import pytest

from tabfix.core import TabFix, FileProcessor
from tabfix.__main__ import create_pre_commit_hook


def test_fix_string_keeps_colon_and_braces():
    content = "def {name}:\n\tpass\n"
    fixed, changes = TabFix().fix_string(content)
    assert "def {name}:" in fixed, "Colon or braces were altered"
    assert "    pass" in fixed, "Tabs should be converted to spaces"
    assert changes  # should report indentation fixes


@pytest.mark.parametrize("preserve", [False, True])
def test_json_preserve_quotes_flag(preserve):
    processor = FileProcessor(preserve_quotes=preserve)
    src = "{'a': 1,\n}"
    fixed, changes = processor.process_json(src, Path("sample.json"))

    # trailing comma should be removed in both modes
    assert ",\n" not in fixed

    if preserve:
        # single quotes stay untouched
        assert "'a'" in fixed
    else:
        # single quotes converted to double quotes when rewriting JSON
        assert '"a"' in fixed
        assert "'a'" not in fixed

    assert changes, "Should record at least one change"


def test_respect_strings_skips_docstrings():
    content = "def foo():\n\t\"\"\"\n\t\tTab inside docstring\n\t\"\"\"\n\tprint('x')\n"
    tf = TabFix()

    fixed_default, _ = tf.fix_mixed_indentation(content)
    assert "\tTab inside docstring" not in fixed_default
    assert "    print('x')" in fixed_default

    fixed_respect, _ = tf.fix_mixed_indentation_python(content)
    assert "\tTab inside docstring" in fixed_respect  # unchanged inside docstring
    assert "    print('x')" in fixed_respect          # outer code still converted


def test_detect_spaces_from_files(tmp_path: Path):
    f1 = tmp_path / "a.py"
    f1.write_text("if True:\n  x = 1\n  y = 2\n")
    f2 = tmp_path / "b.py"
    f2.write_text("def foo():\n  return 42\n")

    tf = TabFix()
    detected = tf.detect_spaces_from_files([f1, f2])
    assert detected == 2


def test_install_pre_commit_hook(tmp_path: Path):
    git_hooks = tmp_path / ".git" / "hooks"
    git_hooks.mkdir(parents=True)
    ok = create_pre_commit_hook(tmp_path, spaces=2)
    assert ok
    hook = git_hooks / "pre-commit"
    data = hook.read_text()
    assert "tabfix --check-only" in data
    assert os.access(hook, os.X_OK)
