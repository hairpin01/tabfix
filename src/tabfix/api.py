from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional, Union, Callable, Awaitable
from dataclasses import dataclass, field
import json
import os
import shutil
import asyncio
import subprocess
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from .core import TabFix
from .config import TabFixConfig
from .autoformat import FileProcessor, get_available_formatters


@dataclass
class FileResult:
    filepath: Path
    changed: bool = False
    changes: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    needs_formatting: bool = False
    backup_path: Optional[Path] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'filepath': str(self.filepath),
            'changed': self.changed,
            'changes': self.changes,
            'errors': self.errors,
            'needs_formatting': self.needs_formatting,
            'backup_path': str(self.backup_path) if self.backup_path else None,
            'timestamp': self.timestamp
        }


@dataclass
class BatchResult:
    total_files: int = 0
    changed_files: int = 0
    failed_files: int = 0
    files_needing_format: int = 0
    individual_results: List[FileResult] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    def add_result(self, result: FileResult):
        self.individual_results.append(result)
        self.total_files += 1
        if result.changed:
            self.changed_files += 1
        if result.errors:
            self.failed_files += 1
        if result.needs_formatting:
            self.files_needing_format += 1

    def finish(self):
        self.end_time = time.time()

    @property
    def duration(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            'summary': {
                'total': self.total_files,
                'changed': self.changed_files,
                'failed': self.failed_files,
                'needs_format': self.files_needing_format,
                'duration_seconds': self.duration
            },
            'results': [r.to_dict() for r in self.individual_results]
        }


class BackupHandler:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.backup_dir = root_dir / ".tabfix_backups" / datetime.now().strftime("%Y%m%d_%H%M%S")

    def create_backup(self, filepath: Path) -> Optional[Path]:
        try:
            if not self.backup_dir.exists():
                self.backup_dir.mkdir(parents=True, exist_ok=True)

            rel_path = filepath.relative_to(self.root_dir)
            dest = self.backup_dir / rel_path
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
            return False
        except Exception:
            return False

    def clean_backups(self):
        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir)


class GitIntegrator:
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    def _run_git(self, args: List[str]) -> List[str]:
        try:
            result = subprocess.run(
                ['git'] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except subprocess.CalledProcessError:
            return []

    def get_staged_files(self) -> List[Path]:
        files = self._run_git(['diff', '--name-only', '--cached'])
        return [self.repo_path / f for f in files]

    def get_modified_files(self) -> List[Path]:
        files = self._run_git(['diff', '--name-only'])
        return [self.repo_path / f for f in files]

    def get_untracked_files(self) -> List[Path]:
        files = self._run_git(['ls-files', '--others', '--exclude-standard'])
        return [self.repo_path / f for f in files]


class TabFixAPI:
    def __init__(self, config: Optional[TabFixConfig] = None, enable_backups: bool = False):
        self.config = config or TabFixConfig()
        self.tabfix = TabFix(spaces_per_tab=self.config.spaces)
        self.formatter = None
        self.backup_handler = None

        if enable_backups:
            self.backup_handler = BackupHandler(Path.cwd())

        if self.config.smart_processing:
            try:
                self.formatter = FileProcessor(spaces_per_tab=self.config.spaces)
            except Exception:
                pass

    def process_string(self, content: str, filepath: Optional[Path] = None) -> Tuple[str, FileResult]:
        result = FileResult(filepath=filepath or Path("string"))

        try:
            processed, changes = self.tabfix.fix_string(content)
            if changes:
                result.changed = True
                result.changes.extend(changes)

            if self.formatter and filepath:
                success, messages = self.formatter.process_file(
                    filepath,
                    check_only=True
                )
                if not success:
                    result.needs_formatting = True
                    result.changes.append(f"Needs formatting: {', '.join(messages)}")

            return processed, result

        except Exception as e:
            result.errors.append(str(e))
            return content, result

    def process_file(self, filepath: Path) -> FileResult:
        result = FileResult(filepath=filepath)

        if self.backup_handler and not (self.config.dry_run or self.config.check_only):
            result.backup_path = self.backup_handler.create_backup(filepath)

        class Args:
            def __init__(self, config):
                for key, value in config.to_dict().items():
                    setattr(self, key, value)
                if not hasattr(self, 'check_only'):
                    setattr(self, 'check_only', getattr(config, 'check_only', False))

        args = Args(self.config)

        try:
            changed = self.tabfix.process_file(filepath, args, None)
            result.changed = changed

            if self.formatter:
                success, messages = self.formatter.process_file(
                    filepath,
                    check_only=getattr(args, 'check_only', False) or getattr(args, 'dry_run', False)
                )
                if not success and messages:
                    if getattr(args, 'check_only', False) or getattr(args, 'dry_run', False):
                        result.needs_formatting = True
                        result.changes.extend(messages)
                    else:
                        success, fix_messages = self.formatter.process_file(filepath, check_only=False)
                        if success:
                            result.changed = True
                            result.changes.extend(fix_messages)

            return result

        except Exception as e:
            result.errors.append(str(e))
            return result

    def process_directory(self,
                         directory: Path,
                         recursive: bool = True,
                         callback: Optional[Callable[[FileResult], None]] = None) -> BatchResult:
        result = BatchResult()

        if not directory.exists():
            result.failed_files += 1
            return result

        pattern = "**/*" if recursive else "*"
        files = list(directory.glob(pattern))

        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_file = {
                executor.submit(self.process_file, file): file
                for file in files if file.is_file()
            }

            for future in as_completed(future_to_file):
                try:
                    file_result = future.result()
                    result.add_result(file_result)
                    if callback:
                        callback(file_result)
                except Exception as e:
                    result.failed_files += 1

        result.finish()
        return result

    def process_git_changes(self, repo_path: Path, include_untracked: bool = False) -> BatchResult:
        git = GitIntegrator(repo_path)
        files = set(git.get_staged_files() + git.get_modified_files())

        if include_untracked:
            files.update(git.get_untracked_files())

        return process_files(list(files), self.config)

    def revert_last_backup(self, batch_result: BatchResult) -> Tuple[int, int]:
        if not self.backup_handler:
            return 0, 0

        restored = 0
        failed = 0

        for res in batch_result.individual_results:
            if res.backup_path and res.filepath.exists():
                if self.backup_handler.restore_backup(Path(res.backup_path), res.filepath):
                    restored += 1
                else:
                    failed += 1

        return restored, failed


class AsyncTabFixAPI:
    def __init__(self, config: Optional[TabFixConfig] = None):
        self.sync_api = TabFixAPI(config)

    async def process_file_async(self, filepath: Path) -> FileResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.sync_api.process_file, filepath)

    async def process_directory_async(
        self,
        directory: Path,
        recursive: bool = True,
        on_progress: Optional[Callable[[FileResult], Awaitable[None]]] = None
    ) -> BatchResult:
        result = BatchResult()

        if not directory.exists():
            return result

        pattern = "**/*" if recursive else "*"
        files = [f for f in directory.glob(pattern) if f.is_file()]

        tasks = [self.process_file_async(f) for f in files]

        for coro in asyncio.as_completed(tasks):
            try:
                file_result = await coro
                result.add_result(file_result)
                if on_progress:
                    if asyncio.iscoroutinefunction(on_progress):
                        await on_progress(file_result)
                    else:
                        on_progress(file_result)
            except Exception:
                result.failed_files += 1

        result.finish()
        return result


class DirectoryWatcher:
    def __init__(self, api: TabFixAPI, directory: Path, interval: float = 1.0):
        self.api = api
        self.directory = directory
        self.interval = interval
        self.running = False
        self._mtimes = {}

    def start(self, callback: Callable[[FileResult], None]):
        self.running = True
        self._scan_initial()

        while self.running:
            changes = self._detect_changes()
            for filepath in changes:
                result = self.api.process_file(filepath)
                if result.changed or result.errors:
                    callback(result)
            time.sleep(self.interval)

    def stop(self):
        self.running = False

    def _scan_initial(self):
        for f in self.directory.rglob("*"):
            if f.is_file():
                self._mtimes[f] = f.stat().st_mtime

    def _detect_changes(self) -> List[Path]:
        changed = []
        current_files = set()

        for f in self.directory.rglob("*"):
            if f.is_file():
                current_files.add(f)
                mtime = f.stat().st_mtime
                if f not in self._mtimes or self._mtimes[f] != mtime:
                    self._mtimes[f] = mtime
                    changed.append(f)

        deleted = set(self._mtimes.keys()) - current_files
        for f in deleted:
            del self._mtimes[f]

        return changed


def create_api(config: Optional[TabFixConfig] = None) -> TabFixAPI:
    return TabFixAPI(config)

def create_async_api(config: Optional[TabFixConfig] = None) -> AsyncTabFixAPI:
    return AsyncTabFixAPI(config)

def process_files(files: List[Union[str, Path]], config: Optional[TabFixConfig] = None) -> BatchResult:
    api = TabFixAPI(config)
    result = BatchResult()

    for file_str in files:
        filepath = Path(file_str) if isinstance(file_str, str) else file_str
        if filepath.exists():
            result.add_result(api.process_file(filepath))
        else:
            result.failed_files += 1

    result.finish()
    return result

def validate_config_file(filepath: Path) -> Tuple[bool, List[str]]:
    errors = []
    try:
        with open(filepath, 'r') as f:
            config_data = json.load(f)
        valid_fields = {f.name for f in TabFixConfig.__dataclass_fields__.values()}
        for key in config_data:
            if key not in valid_fields:
                errors.append(f"Unknown field: {key}")
        return len(errors) == 0, errors
    except Exception as e:
        return False, [str(e)]

def create_project_config(root_dir: Path, project_type: Optional[str] = None, **overrides) -> TabFixConfig:
    config = TabFixConfig()
    defaults = {
        'python': {'spaces': 4, 'fix_mixed': True, 'format_json': True, 'smart_processing': True},
        'javascript': {'spaces': 2, 'fix_mixed': True, 'format_json': True, 'smart_processing': True},
        'go': {'spaces': 4, 'fix_mixed': False, 'smart_processing': True}
    }

    if project_type in defaults:
        for k, v in defaults[project_type].items():
            setattr(config, k, v)

    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return config
