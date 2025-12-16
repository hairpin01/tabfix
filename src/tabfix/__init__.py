from .api import (
    TabFixAPI,
    TabFixConfig,
    fix_string,
    fix_file,
    check_file,
    detect_indentation,
    create_config_file,
)

__version__ = "1.2.5"

__all__ = [
    "TabFixAPI",
    "TabFixConfig",
    "fix_string",
    "fix_file",
    "check_file",
    "detect_indentation",
    "create_config_file",
]
