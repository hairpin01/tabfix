__version__ = "1.2.5.2"

from .core import TabFix, Colors, print_color, GitignoreMatcher
from .config import TabFixConfig, ConfigLoader


__all__ = [
    "TabFix",
    "Colors", 
    "print_color",
    "GitignoreMatcher",
    "TabFixConfig",
    "ConfigLoader",
    "__version__",
]
