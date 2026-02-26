"""
tabfix.api — High-level programmatic API.

Fixes:
  [BUG-A1] process_string: called non-existent fix_string(); now delegates to
            TabFix.fix_string() which was added in core.py.
  [BUG-A2] process_git_changes: was calling the module-level process_files()
            helper, losing the formatter, backup_handler and config of `self`.
            Now uses self.process_file() directly.
  [BUG-A3] The inner Args class was fragile (relied on config.to_dict()).
            Replaced with argparse.Namespace for clarity and correctness.
  [BUG-A4] BackupHandler root_dir was always Path.cwd() even when processing
            files from another directory tree.

New features:
  [NEW-A1] TabFixAPI.check_string() — check a string without modifying it.
  [NEW-A2] BatchResult.to_json()    — convenient serialisation.
  [NEW-A3] process_directory respects max_workers config.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union

from .core import TabFix, Colors, print_color, GitignoreMatcher
from .config import TabFixConfig
from .autoformat import FileProcessor, get_available_formatters

@dataclass
class FileResult:
    filepath:        Path
    changed:         bool             = False
    changes:         List[str]        = field(default_factory=list)
    errors:          List[str]        = field(default_factory=list)
    needs_formatting: bool            = False
    backup_path:     Optional[Path]   = None
    timestamp:       float            = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filepath":         str(self.filepath),
            "changed":          self.changed,
            "changes":          self.changes,
            "errors":           self.errors,
            "needs_formatting": self.needs_formatting,
            "backup_path":      str(self.backup_path) if self.backup_path else None,
            "timestamp":        self.timestamp,
        }


@dataclass
class BatchResult:
    total_files:        int              = 0
    changed_files:      int              = 0
    failed_files:       int              = 0
    files_needing_format: int            = 0
    individual_results: List[FileResult] = field(default_factory=list)
    start_time:         float            = field(default_factory=time.time)
    end_time:           Optional[float]  = None

    def add_result(self, result: FileResult) -> None:
        self.individual_results.append(result)
        self.total_files += 1
        if result.changed:
            self.changed_files += 1
        if result.errors:
            self.failed_files += 1
        if result.needs_formatting:
            self.files_needing_format += 1

    def finish(self) -> None:
        self.end_time = time.time()

    @property
    def duration(self) -> float:
        return (self.end_time or time.time()) - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": {
                "total":        self.total_files,
                "changed":      self.changed_files,
                "failed":       self.failed_files,
                "needs_format": self.files_needing_format,
                "duration_sec": self.duration,
            },
            "results": [r.to_dict() for r in self.individual_results],
        }

    def to_json(self, indent: int = 2) -> str:
        """[NEW-A2] Convenience serialisation."""
        return json.dumps(self.to_dict(), indent=indent)

class BackupHandler:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir  = root_dir
        self.backup_dir = (
            root_dir / ".tabfix_backups" / datetime.now().strftime("%Y%m%d_%H%M%S")
        )

    def create_backup(self, filepath: Path) -> Optional[Path]:
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            # [BUG-A4] Use the file's own root if it's outside our root_dir
            try:
                rel = filepath.resolve().relative_to(self.root_dir.resolve())
            except ValueError:
                rel = Path(filepath.name)
            dest = self.backup_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(filepath, dest)
            return dest
        except Exception:
            return None

    def restore_backup(self, backup_path: Path, original_path: Path) -> bool:
        try:
            if backup_path.exists():
                shutil.copy2(backup_path, original_path)
                return True
        except Exception:
            pass
        return False

    def clean_backups(self) -> None:
        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir)

class GitIntegrator:
    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path

    def _run(self, args: List[str]) -> List[str]:
        import subprocess
        try:
            r = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return [l.strip() for l in r.stdout.splitlines() if l.strip()]
        except Exception:
            return []

    def get_staged_files(self)    -> List[Path]:
        return [self.repo_path / f for f in self._run(["diff", "--name-only", "--cached"])]

    def get_modified_files(self)  -> List[Path]:
        return [self.repo_path / f for f in self._run(["diff", "--name-only"])]

    def get_untracked_files(self) -> List[Path]:
        return [self.repo_path / f for f in self._run(["ls-files", "--others", "--exclude-standard"])]

def _config_to_namespace(config: TabFixConfig, check_only: bool = False) -> argparse.Namespace:
    """
    [BUG-A3] Build a proper argparse.Namespace from a TabFixConfig so that
    TabFix.process_file() can read settings via getattr().
    """
    d = config.to_dict() if hasattr(config, "to_dict") else vars(config)
    ns = argparse.Namespace(**d)
    if not hasattr(ns, "check_only"):
        ns.check_only = check_only
    if not hasattr(ns, "dry_run"):
        ns.dry_run = False
    if not hasattr(ns, "interactive"):
        ns.interactive = False
    if not hasattr(ns, "verbose"):
        ns.verbose = False
    if not hasattr(ns, "quiet"):
        ns.quiet = False
    if not hasattr(ns, "backup"):
        ns.backup = False
    if not hasattr(ns, "skip_binary"):
        ns.skip_binary = True
    if not hasattr(ns, "max_file_size"):
        ns.max_file_size = 10 * 1024 * 1024
    if not hasattr(ns, "normalize_endings"):
        ns.normalize_endings = False
    return ns

class TabFixAPI:
    def __init__(
        self,
        config:         Optional[TabFixConfig] = None,
        enable_backups: bool                   = False,
        max_workers:    int                    = 4,
    ) -> None:
        self.config     = config or TabFixConfig()
        self.tabfix     = TabFix(spaces_per_tab=self.config.spaces)
        self.max_workers = max_workers
        self.formatter: Optional[FileProcessor] = None
        self.backup_handler: Optional[BackupHandler] = None

        if enable_backups:
            self.backup_handler = BackupHandler(Path.cwd())

        if getattr(self.config, "smart_processing", False):
            try:
                self.formatter = FileProcessor(spaces_per_tab=self.config.spaces)
            except Exception:
                pass

    def process_string(
        self,
        content:  str,
        filepath: Optional[Path] = None,
    ) -> Tuple[str, FileResult]:
        """
        [BUG-A1] Previously called non-existent self.tabfix.fix_string().
        Now delegates to the newly added TabFix.fix_string().
        """
        result = FileResult(filepath=filepath or Path("<string>"))
        try:
            processed, changes = self.tabfix.fix_string(content)
            if changes:
                result.changed = True
                result.changes.extend(changes)

            if self.formatter and filepath:
                ok, msgs = self.formatter.process_file(filepath, check_only=True)
                if not ok:
                    result.needs_formatting = True
                    result.changes.extend(msgs)

            return processed, result

        except Exception as e:
            result.errors.append(str(e))
            return content, result

    def check_string(self, content: str) -> Tuple[bool, List[str]]:
        """[NEW-A1] Check whether a string would be modified without changing it."""
        _, changes = self.tabfix.fix_string(content)
        return bool(changes), changes

    def process_file(self, filepath: Path) -> FileResult:
        result = FileResult(filepath=filepath)

        if self.backup_handler:
            check = getattr(self.config, "check_only", False)
            dry   = getattr(self.config, "dry_run",    False)
            if not check and not dry:
                result.backup_path = self.backup_handler.create_backup(filepath)

        args = _config_to_namespace(self.config)

        try:
            changed = self.tabfix.process_file(filepath, args, None)
            result.changed = changed

            if self.formatter:
                ok, msgs = self.formatter.process_file(
                    filepath,
                    check_only=getattr(args, "check_only", False) or getattr(args, "dry_run", False),
                )
                if not ok and msgs:
                    if getattr(args, "check_only", False) or getattr(args, "dry_run", False):
                        result.needs_formatting = True
                        result.changes.extend(msgs)
                    else:
                        ok2, fix_msgs = self.formatter.process_file(filepath, check_only=False)
                        if ok2:
                            result.changed = True
                            result.changes.extend(fix_msgs)

        except Exception as e:
            result.errors.append(str(e))

        return result

    def process_directory(
        self,
        directory: Path,
        recursive: bool = True,
        callback:  Optional[Callable[[FileResult], None]] = None,
    ) -> BatchResult:
        batch = BatchResult()
        if not directory.exists():
            batch.failed_files += 1
            return batch

        pattern = "**/*" if recursive else "*"
        files   = [f for f in directory.glob(pattern) if f.is_file()]

        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = {ex.submit(self.process_file, f): f for f in files}
            for future in as_completed(futures):
                try:
                    res = future.result()
                    batch.add_result(res)
                    if callback:
                        callback(res)
                except Exception:
                    batch.failed_files += 1

        batch.finish()
        return batch

    def process_git_changes(
        self,
        repo_path:        Path,
        include_untracked: bool = False,
    ) -> BatchResult:
        """
        [BUG-A2] Was calling the module-level process_files() helper which
        creates a new TabFixAPI and discards self's formatter/backup config.
        Now uses self.process_file() directly.
        """
        git = GitIntegrator(repo_path)
        files: set = set(git.get_staged_files()) | set(git.get_modified_files())
        if include_untracked:
            files.update(git.get_untracked_files())

        batch = BatchResult()
        for fp in files:
            if fp.exists():
                batch.add_result(self.process_file(fp))
            else:
                batch.failed_files += 1
        batch.finish()
        return batch


    def revert_last_backup(self, batch_result: BatchResult) -> Tuple[int, int]:
        if not self.backup_handler:
            return 0, 0
        restored = failed = 0
        for res in batch_result.individual_results:
            if res.backup_path:
                bp = Path(res.backup_path) if isinstance(res.backup_path, str) else res.backup_path
                if self.backup_handler.restore_backup(bp, res.filepath):
                    restored += 1
                else:
                    failed += 1
        return restored, failed

class AsyncTabFixAPI:
    def __init__(self, config: Optional[TabFixConfig] = None) -> None:
        self.sync_api = TabFixAPI(config)

    async def process_file_async(self, filepath: Path) -> FileResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.sync_api.process_file, filepath)

    async def process_directory_async(
        self,
        directory:   Path,
        recursive:   bool = True,
        on_progress: Optional[Callable[[FileResult], Union[None, Awaitable[None]]]] = None,
    ) -> BatchResult:
        batch = BatchResult()
        if not directory.exists():
            return batch

        pattern = "**/*" if recursive else "*"
        files   = [f for f in directory.glob(pattern) if f.is_file()]
        tasks   = [self.process_file_async(f) for f in files]

        for coro in asyncio.as_completed(tasks):
            try:
                res = await coro
                batch.add_result(res)
                if on_progress:
                    r = on_progress(res)
                    if asyncio.iscoroutine(r):
                        await r
            except Exception:
                batch.failed_files += 1

        batch.finish()
        return batch

class DirectoryWatcher:
    def __init__(self, api: TabFixAPI, directory: Path, interval: float = 1.0) -> None:
        self.api       = api
        self.directory = directory
        self.interval  = interval
        self.running   = False
        self._mtimes:  Dict[Path, float] = {}

    def start(self, callback: Callable[[FileResult], None]) -> None:
        self.running = True
        self._scan_initial()
        import time as _time
        while self.running:
            for fp in self._detect_changes():
                res = self.api.process_file(fp)
                if res.changed or res.errors:
                    callback(res)
            _time.sleep(self.interval)

    def stop(self) -> None:
        self.running = False

    def _scan_initial(self) -> None:
        try:
            for f in self.directory.rglob("*"):
                if f.is_file():
                    self._mtimes[f] = f.stat().st_mtime
        except OSError:
            pass

    def _detect_changes(self) -> List[Path]:
        changed: List[Path] = []
        current: set = set()
        try:
            for f in self.directory.rglob("*"):
                if not f.is_file():
                    continue
                current.add(f)
                try:
                    mtime = f.stat().st_mtime
                    if f not in self._mtimes or self._mtimes[f] != mtime:
                        self._mtimes[f] = mtime
                        changed.append(f)
                except OSError:
                    pass
        except OSError:
            pass
        for f in set(self._mtimes) - current:
            del self._mtimes[f]
        return changed

def create_api(config: Optional[TabFixConfig] = None) -> TabFixAPI:
    return TabFixAPI(config)


def create_async_api(config: Optional[TabFixConfig] = None) -> AsyncTabFixAPI:
    return AsyncTabFixAPI(config)


def process_files(
    files:  List[Union[str, Path]],
    config: Optional[TabFixConfig] = None,
) -> BatchResult:
    api   = TabFixAPI(config)
    batch = BatchResult()
    for f in files:
        fp = Path(f) if isinstance(f, str) else f
        if fp.exists():
            batch.add_result(api.process_file(fp))
        else:
            batch.failed_files += 1
    batch.finish()
    return batch


def validate_config_file(filepath: Path) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    try:
        with open(filepath, encoding="utf-8") as fh:
            data = json.load(fh)
        # [BUG-A3] Simpler field lookup
        valid = set(TabFixConfig.__dataclass_fields__.keys())
        for key in data:
            if key not in valid:
                errors.append(f"Unknown field: {key!r}")
        return not errors, errors
    except Exception as e:
        return False, [str(e)]


def create_project_config(
    root_dir:     Path,
    project_type: Optional[str] = None,
    **overrides:  Any,
) -> TabFixConfig:
    config = TabFixConfig()
    defaults: Dict[str, Dict[str, Any]] = {
        "python":     {"spaces": 4, "fix_mixed": True,  "format_json": True,  "smart_processing": True},
        "javascript": {"spaces": 2, "fix_mixed": True,  "format_json": True,  "smart_processing": True},
        "go":         {"spaces": 4, "fix_mixed": False,                        "smart_processing": True},
    }
    if project_type in defaults:
        for k, v in defaults[project_type].items():
            setattr(config, k, v)
    for k, v in overrides.items():
        if hasattr(config, k):
            setattr(config, k, v)
    return config
