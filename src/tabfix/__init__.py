__version__ = "1.2.0"

from .core import TabFix, Colors, print_color, GitignoreMatcher
from .config import TabFixConfig, ConfigLoader
from .autoformat import Formatter, FormatterManager, FileProcessor, get_available_formatters, create_autoformat_config


from .api import (
    TabFixAPI,
    FileResult,
    BatchResult,
    create_api,
    create_default_config,
    create_custom_config,
    process_files,
    process_directory_parallel,
    validate_config_file,
    create_project_config,
    export_results,
)

__all__ = [
    # core
    "TabFix",
    "Colors",
    "print_color",
    "GitignoreMatcher",
    "TabFixConfig",
    "ConfigLoader",

    # autoformat
    "Formatter",
    "FormatterManager",
    "FileProcessor",
    "get_available_formatters",
    "create_autoformat_config",
    # api
    "TabFixAPI",
    "FileResult",
    "BatchResult",
    "create_api",
    "create_default_config",
    "create_custom_config",
    "process_files",
    "process_directory_parallel",
    "validate_config_file",
    "create_project_config",
    "export_results",

    "__version__",
]
