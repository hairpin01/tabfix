"""
tabfix — Advanced tab/space indentation fixer with autoformatting.
"""

__version__ = "1.2.8"

from .core import (
    TabFix,
    Colors,
    print_color,
    disable_colors,
    GitignoreMatcher,
)
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
    # core
    "TabFix",
    "Colors",
    "print_color",
    "disable_colors",
    "GitignoreMatcher",
    # config
    "TabFixConfig",
    "ConfigLoader",
    # autoformat
    "Formatter",
    "FileProcessor",
    "get_available_formatters",
    # api
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
    # meta
    "__version__",
]
