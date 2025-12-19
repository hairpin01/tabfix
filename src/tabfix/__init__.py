__version__ = "1.3.0"

from .core import TabFix, Colors, print_color, GitignoreMatcher
from .config import TabFixConfig, ConfigLoader
from .autoformat import Formatter, FileProcessor, get_available_formatters

from .api import (
    TabFixAPI,
    AsyncTabFixAPI,
    FileResult,
    BatchResult,
    DirectoryWatcher,
    GitIntegrator,
    create_api,
    create_async_api,
    process_files,
    create_project_config,
    validate_config_file,
)

__all__ = [
    "TabFix",
    "Colors",
    "print_color",
    "GitignoreMatcher",
    "TabFixConfig",
    "ConfigLoader",
    "Formatter",
    "FileProcessor",
    "get_available_formatters",
    "TabFixAPI",
    "AsyncTabFixAPI",
    "FileResult",
    "BatchResult",
    "DirectoryWatcher",
    "GitIntegrator",
    "create_api",
    "create_async_api",
    "process_files",
    "create_project_config",
    "validate_config_file",
    "__version__",
]
