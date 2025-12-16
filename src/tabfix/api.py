from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional, Union, Iterator
from dataclasses import dataclass, asdict, field
import json
from contextlib import contextmanager
from functools import wraps


@dataclass
class TabFixConfig:
    spaces: int = 4
    fix_mixed: bool = True
    fix_trailing: bool = True
    final_newline: bool = True
    remove_bom: bool = False
    keep_bom: bool = False
    format_json: bool = True
    max_file_size: int = 10 * 1024 * 1024
    skip_binary: bool = True
    fallback_encoding: str = "latin-1"
    warn_encoding: bool = False
    force_encoding: Optional[str] = None
    smart_processing: bool = True
    preserve_quotes: bool = False
    progress: bool = False
    dry_run: bool = False
    backup: bool = False
    verbose: bool = False
    quiet: bool = True
    no_color: bool = True
    git_staged: bool = False
    git_unstaged: bool = False
    git_all_changed: bool = False
    no_gitignore: bool = False
    recursive: bool = False
    interactive: bool = False
    paths: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TabFixConfig":
        valid_fields = {f.name for f in field(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


@dataclass
class FileResult:
    filepath: Path
    changed: bool
    changes: List[str]
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "filepath": str(self.filepath),
            "changed": self.changed,
            "changes": self.changes,
            "error": self.error,
        }
    
    def __str__(self) -> str:
        if self.error:
            return f"{self.filepath}: ERROR - {self.error}"
        if self.changed:
            return f"{self.filepath}: CHANGED ({len(self.changes)} changes)"
        return f"{self.filepath}: OK"


@dataclass
class BatchResult:
    total_files: int
    changed_files: int
    failed_files: int
    skipped_files: int
    results: List[FileResult]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_files": self.total_files,
            "changed_files": self.changed_files,
            "failed_files": self.failed_files,
            "skipped_files": self.skipped_files,
            "results": [r.to_dict() for r in self.results],
        }
    
    def __str__(self) -> str:
        return f"Processed {self.total_files} files: {self.changed_files} changed, {self.failed_files} failed, {self.skipped_files} skipped"


def catch_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if args and hasattr(args[0], 'config') and args[0].config.verbose:
                raise
            return None
    return wrapper


class TabFixAPI:
    def __init__(self, config: Optional[Union[TabFixConfig, Dict[str, Any]]] = None):
        if isinstance(config, dict):
            self.config = TabFixConfig.from_dict(config)
        elif isinstance(config, TabFixConfig):
            self.config = config
        else:
            self.config = TabFixConfig()
        
        from .core import TabFix, GitignoreMatcher
        self._core = TabFix(spaces_per_tab=self.config.spaces)
        self._gitignore_matcher: Optional[GitignoreMatcher] = None
    
    @contextmanager
    def context(self, **kwargs):
        original_config = self.config
        try:
            config_dict = original_config.to_dict()
            config_dict.update(kwargs)
            self.config = TabFixConfig.from_dict(config_dict)
            yield self
        finally:
            self.config = original_config
    
    @catch_errors
    def fix_string(self, content: str, filepath: Optional[Union[str, Path]] = None, **kwargs) -> Tuple[str, List[str]]:
        with self.context(**kwargs) as api:
            changes = []
            fixed_content = content
            
            if filepath:
                filepath = Path(filepath)
                if api.config.format_json and filepath.suffix.lower() == ".json":
                    formatted, changed = api._core.format_json(fixed_content)
                    if changed:
                        fixed_content = formatted
                        changes.append("Formatted JSON")
            
            if api.config.fix_mixed:
                fixed_content, indent_changes = api._core.fix_mixed_indentation(fixed_content)
                changes.extend(indent_changes)
            
            if api.config.fix_trailing:
                fixed_content, trailing_changes = api._core.fix_trailing_spaces(fixed_content)
                changes.extend(trailing_changes)
            
            if api.config.final_newline:
                fixed_content, newline_changes = api._core.ensure_final_newline(fixed_content)
                changes.extend(newline_changes)
            
            return fixed_content, changes
    
    @catch_errors
    def fix_file(self, filepath: Union[str, Path], **kwargs) -> FileResult:
        with self.context(**kwargs) as api:
            from .core import GitignoreMatcher
            
            filepath = Path(filepath)
            
            if not filepath.exists():
                return FileResult(filepath, False, [], f"File not found: {filepath}")
            
            if not filepath.is_file():
                return FileResult(filepath, False, [], f"Not a file: {filepath}")
            
            if api.config.no_gitignore == False:
                if api._gitignore_matcher is None:
                    root_dir = filepath.parent
                    gitignore_path = root_dir / ".gitignore"
                    if gitignore_path.exists():
                        api._gitignore_matcher = GitignoreMatcher(root_dir)
                
                if api._gitignore_matcher and api._gitignore_matcher.should_ignore(filepath):
                    return FileResult(filepath, False, [], "Ignored by .gitignore")
            
            file_size = filepath.stat().st_size
            if file_size > api.config.max_file_size:
                return FileResult(filepath, False, [], f"File too large: {file_size / 1024 / 1024:.1f}MB")
            
            class Args:
                pass
            
            args = Args()
            for key, value in api.config.to_dict().items():
                setattr(args, key, value)
            
            try:
                if hasattr(api._core, 'process_file_with_changes'):
                    changed, changes = api._core.process_file_with_changes(filepath, args, None)
                else:
                    changed = api._core.process_file(filepath, args, None)
                    changes = []
                
                return FileResult(filepath, changed, changes)
                
            except Exception as e:
                if api.config.verbose:
                    raise
                return FileResult(filepath, False, [], str(e))
    
    def fix_files(self, filepaths: List[Union[str, Path]], **kwargs) -> BatchResult:
        with self.context(**kwargs) as api:
            results = []
            changed_count = 0
            failed_count = 0
            skipped_count = 0
            
            for filepath in filepaths:
                result = api.fix_file(filepath)
                results.append(result)
                
                if result.error:
                    if "ignored" in result.error.lower() or "not found" in result.error.lower():
                        skipped_count += 1
                    else:
                        failed_count += 1
                elif result.changed:
                    changed_count += 1
            
            return BatchResult(
                total_files=len(results),
                changed_files=changed_count,
                failed_files=failed_count,
                skipped_files=skipped_count,
                results=results,
            )
    
    def fix_directory(self, directory: Union[str, Path], pattern: str = "**/*", **kwargs) -> BatchResult:
        with self.context(**kwargs) as api:
            directory = Path(directory)
            
            if not api.config.recursive:
                pattern = pattern.replace("**/", "")
            
            files = []
            for filepath in directory.glob(pattern):
                if filepath.is_file():
                    files.append(filepath)
            
            return api.fix_files(files)
    
    @catch_errors
    def check_file(self, filepath: Union[str, Path], **kwargs) -> Tuple[bool, List[str]]:
        with self.context(**kwargs) as api:
            api.config.dry_run = True
            api.config.check_only = True
            api.config.quiet = True
            
            result = api.fix_file(filepath)
            if result.error:
                return False, [result.error]
            return result.changed, result.changes
    
    def batch_check(self, filepaths: List[Union[str, Path]], **kwargs) -> Dict[str, Tuple[bool, List[str]]]:
        results = {}
        for filepath in filepaths:
            needs_fix, issues = self.check_file(filepath, **kwargs)
            results[str(filepath)] = (needs_fix, issues)
        return results
    
    @catch_errors
    def detect_indentation(self, content: str) -> Dict[str, Any]:
        return self._core.detect_indentation(content)
    
    def compare_files(self, file1: Union[str, Path], file2: Union[str, Path]) -> Dict[str, Any]:
        file1 = Path(file1)
        file2 = Path(file2)
        return self._core.compare_files_indentation(file1, file2)
    
    def get_git_files(self, mode: str = "staged") -> List[Path]:
        return self._core.get_git_files(mode)
    
    def fix_git_files(self, mode: str = "staged", **kwargs) -> BatchResult:
        files = self.get_git_files(mode)
        return self.fix_files(files, **kwargs)
    
    def create_config_file(self, filepath: Union[str, Path], format: str = "json"):
        filepath = Path(filepath)
        
        if format.lower() == "json":
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.config.to_dict(), f, indent=2, ensure_ascii=False)
        elif format.lower() == "toml":
            try:
                import tomli_w
                with open(filepath, 'wb') as f:
                    tomli_w.dump(self.config.to_dict(), f)
            except ImportError:
                raise ImportError("tomli-w is required for TOML format")
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def load_config_file(self, filepath: Union[str, Path]) -> "TabFixAPI":
        filepath = Path(filepath)
        
        if filepath.suffix.lower() == ".json":
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        elif filepath.suffix.lower() == ".toml":
            try:
                import tomllib
                with open(filepath, 'rb') as f:
                    data = tomllib.load(f)
            except ImportError:
                try:
                    import tomli as tomllib
                    with open(filepath, 'rb') as f:
                        data = tomllib.load(f)
                except ImportError:
                    raise ImportError("tomli is required for TOML format")
        else:
            raise ValueError(f"Unsupported config format: {filepath.suffix}")
        
        return TabFixAPI(data)
    
    def generate_pre_commit_hook(self, output_file: Union[str, Path] = ".pre-commit-config.yaml"):
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML is required to generate pre-commit hooks")
        
        from . import __version__
        
        config = {
            "repos": [{
                "repo": "https://github.com/hairpin01/tabfix",
                "rev": f"v{__version__}",
                "hooks": [{
                    "id": "tabfix",
                    "name": "tabfix",
                    "entry": "tabfix",
                    "args": [
                        "--fix-mixed",
                        "--fix-trailing", 
                        "--final-newline",
                        "--format-json",
                    ],
                    "language": "python",
                    "types_or": ["python", "javascript", "json", "yaml", "markdown", "html", "css"],
                    "stages": ["commit"],
                }]
            }]
        }
        
        output_file = Path(output_file)
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return output_file
    
    def get_stats(self) -> Dict[str, int]:
        return self._core.stats.copy()
    
    def reset_stats(self):
        self._core.stats = {
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
    
    def format_json_string(self, content: str, **kwargs) -> str:
        formatted, changed = self._core.format_json(content)
        return formatted
    
    def normalize_string(self, content: str, **kwargs) -> str:
        fixed, _ = self.fix_string(content, **kwargs)
        return fixed


def fix_string(content: str, **kwargs) -> str:
    api = TabFixAPI(kwargs)
    fixed, _ = api.fix_string(content, **kwargs)
    return fixed


def fix_file(filepath: Union[str, Path], **kwargs) -> bool:
    api = TabFixAPI(kwargs)
    result = api.fix_file(filepath, **kwargs)
    return result.changed and not result.error


def check_string(content: str, **kwargs) -> Tuple[bool, List[str]]:
    api = TabFixAPI(kwargs)
    return api.check_file("dummy.py", **kwargs)


def process_directory(directory: Union[str, Path], **kwargs) -> BatchResult:
    api = TabFixAPI(kwargs)
    return api.fix_directory(directory, **kwargs)


def create_default_config(output_file: Union[str, Path], format: str = "json"):
    api = TabFixAPI()
    api.create_config_file(output_file, format)


@contextmanager
def session(**kwargs):
    api = TabFixAPI(kwargs)
    try:
        yield api
    finally:
        pass
