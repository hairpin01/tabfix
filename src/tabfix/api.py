from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional, Union, Generator
from dataclasses import dataclass, asdict
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial

from .core import TabFix, GitignoreMatcher
from .config import TabFixConfig, ConfigLoader
from .autoformat import Formatter, FileProcessor, get_available_formatters


@dataclass
class FileResult:
    filepath: Path
    changed: bool = False
    changes: List[str] = None
    errors: List[str] = None
    needs_formatting: bool = False

    def __post_init__(self):
        if self.changes is None:
            self.changes = []
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            'filepath': str(self.filepath),
            'changed': self.changed,
            'changes': self.changes,
            'errors': self.errors,
            'needs_formatting': self.needs_formatting
        }


@dataclass
class BatchResult:
    total_files: int = 0
    changed_files: int = 0
    failed_files: int = 0
    files_needing_format: int = 0
    individual_results: List[FileResult] = None

    def __post_init__(self):
        if self.individual_results is None:
            self.individual_results = []

    def add_result(self, result: FileResult):
        self.individual_results.append(result)
        self.total_files += 1
        if result.changed:
            self.changed_files += 1
        if result.errors:
            self.failed_files += 1
        if result.needs_formatting:
            self.files_needing_format += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_files': self.total_files,
            'changed_files': self.changed_files,
            'failed_files': self.failed_files,
            'files_needing_format': self.files_needing_format,
            'results': [r.to_dict() for r in self.individual_results]
        }


class TabFixAPI:
    def __init__(self, config: Optional[TabFixConfig] = None):
        self.config = config or TabFixConfig()
        self.tabfix = TabFix(spaces_per_tab=self.config.spaces)
        self.formatter = None

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

        class Args:
            def __init__(self, config):
                for key, value in config.to_dict().items():
                    setattr(self, key, value)

        args = Args(self.config)

        try:
            changed = self.tabfix.process_file(filepath, args, None)
            result.changed = changed

            if self.formatter:
                success, messages = self.formatter.process_file(
                    filepath,
                    check_only=args.dry_run or args.check_only
                )
                if not success and messages:
                    if args.dry_run or args.check_only:
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

    def process_directory(self, directory: Path, recursive: bool = True) -> BatchResult:
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
                except Exception as e:
                    result.failed_files += 1

        return result

    def check_directory(self, directory: Path, recursive: bool = True) -> BatchResult:
        original_config = self.config
        self.config = TabFixConfig(**original_config.to_dict())
        self.config.dry_run = True
        self.config.check_only = True

        result = self.process_directory(directory, recursive)

        self.config = original_config
        return result

    def autoformat_file(self, filepath: Path) -> FileResult:
        result = FileResult(filepath=filepath)

        if not self.formatter:
            result.errors.append("Autoformat not available")
            return result

        try:
            success, messages = self.formatter.process_file(filepath, check_only=False)
            if success:
                result.changed = True
                result.changes.extend(messages)
            else:
                result.errors.extend(messages)
        except Exception as e:
            result.errors.append(str(e))

        return result

    def autoformat_directory(self, directory: Path, recursive: bool = True) -> BatchResult:
        result = BatchResult()

        if not self.formatter:
            result.failed_files = 1
            return result

        pattern = "**/*" if recursive else "*"
        files = list(directory.glob(pattern))

        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_file = {
                executor.submit(self.autoformat_file, file): file
                for file in files if file.is_file()
            }

            for future in as_completed(future_to_file):
                try:
                    file_result = future.result()
                    result.add_result(file_result)
                except Exception as e:
                    result.failed_files += 1

        return result

    def get_file_stats(self, filepath: Path) -> Dict[str, Any]:
        try:
            with open(filepath, 'rb') as f:
                content = f.read().decode('utf-8-sig')

            stats = self.tabfix.detect_indentation(content)
            stats['encoding'] = 'utf-8-sig'
            stats['size'] = filepath.stat().st_size
            stats['lines'] = len(content.splitlines())

            return stats
        except Exception as e:
            return {'error': str(e)}

    def compare_files(self, file1: Path, file2: Path) -> Dict[str, Any]:
        class Args:
            quiet = True
            no_color = True

        args = Args()
        return self.tabfix.compare_files_indentation(file1, file2)

    def generate_config_file(self, filepath: Path = None) -> bool:
        if not filepath:
            filepath = Path.cwd() / '.tabfixrc.json'

        try:
            with open(filepath, 'w') as f:
                json.dump(self.config.to_dict(), f, indent=2)
            return True
        except Exception:
            return False

    def list_formatters(self) -> Dict[str, List[str]]:
        available = get_available_formatters()

        categories = {
            'python': ['black', 'autopep8', 'isort', 'ruff', 'yapf'],
            'javascript': ['prettier'],
            'go': ['gofmt'],
            'rust': ['rustfmt'],
            'cpp': ['clang-format'],
        }

        result = {}
        for category, formatters in categories.items():
            result[category] = [f for f in formatters if f in available]

        result['available'] = available
        return result


# Factory functions
def create_api(config: Optional[TabFixConfig] = None) -> TabFixAPI:
    return TabFixAPI(config)


def create_default_config() -> TabFixConfig:
    return TabFixConfig()


def create_custom_config(**kwargs) -> TabFixConfig:
    return TabFixConfig(**kwargs)


# Helper functions
def process_files(files: List[Union[str, Path]], config: Optional[TabFixConfig] = None) -> BatchResult:
    api = TabFixAPI(config)
    result = BatchResult()

    for file_str in files:
        filepath = Path(file_str) if isinstance(file_str, str) else file_str
        if filepath.exists():
            result.add_result(api.process_file(filepath))
        else:
            result.failed_files += 1

    return result


def process_directory_parallel(
    directory: Path,
    config: Optional[TabFixConfig] = None,
    max_workers: int = 4,
    recursive: bool = True
) -> BatchResult:
    api = TabFixAPI(config)
    return api.process_directory(directory, recursive)


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

    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]
    except Exception as e:
        return False, [str(e)]


def create_project_config(
    root_dir: Path,
    project_type: Optional[str] = None,
    **overrides
) -> TabFixConfig:
    config = TabFixConfig()

    if project_type == 'python':
        config.spaces = 4
        config.fix_mixed = True
        config.format_json = True
        config.smart_processing = True

    elif project_type == 'javascript':
        config.spaces = 2
        config.fix_mixed = True
        config.format_json = True
        config.smart_processing = True

    elif project_type == 'go':
        config.spaces = 4
        config.fix_mixed = False
        config.smart_processing = True

    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return config


def export_results(results: BatchResult, format: str = 'json', output_file: Optional[Path] = None) -> str:
    if format == 'json':
        output = json.dumps(results.to_dict(), indent=2)
    elif format == 'csv':
        import csv
        import io

        output_io = io.StringIO()
        writer = csv.writer(output_io)
        writer.writerow(['File', 'Changed', 'Needs Formatting', 'Changes', 'Errors'])

        for result in results.individual_results:
            writer.writerow([
                str(result.filepath),
                result.changed,
                result.needs_formatting,
                '; '.join(result.changes),
                '; '.join(result.errors)
            ])

        output = output_io.getvalue()
    else:
        output = str(results)

    if output_file:
        output_file.write_text(output)

    return output
