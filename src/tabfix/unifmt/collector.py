import subprocess
from pathlib import Path
from typing import List, Optional
import fnmatch


class FileCollector:
    def __init__(self, config):
        self.config = config

    def collect_files(self) -> List[Path]:
        all_files = []

        for pattern in self.config.include_patterns or ["**/*"]:
            for file_path in self.config.root_dir.glob(pattern):
                if file_path.is_file() and self._should_include(file_path):
                    all_files.append(file_path)

        return sorted(set(all_files))

    def _should_include(self, file_path: Path) -> bool:
        try:
            rel_path = file_path.relative_to(self.config.root_dir)
        except ValueError:
            return False

        for pattern in self.config.exclude_patterns:
            if fnmatch.fnmatch(str(rel_path), pattern):
                return False

        if self.config.respect_gitignore:
            if self._is_gitignored(file_path):
                return False

        for file_type in self.config.file_types.values():
            if any(str(rel_path).endswith(ext) for ext in file_type.extensions):
                return True

        return not self.config.file_types

    def _is_gitignored(self, file_path: Path) -> bool:
        git_dir = self._find_git_dir(file_path)
        if not git_dir:
            return False

        try:
            result = subprocess.run(
                ["git", "check-ignore", "-q", str(file_path)],
                cwd=git_dir,
                capture_output=True
            )
            return result.returncode == 0
        except:
            return False

    def _find_git_dir(self, file_path: Path) -> Optional[Path]:
        current = file_path.parent
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        return None
