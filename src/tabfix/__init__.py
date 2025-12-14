__version__ = "1.0.0"
__author__ = "hairpin01"
__license__ = "GNU General Public License v3.0"

try:
    from .tabfix import main, TabFix, GitignoreMatcher, Colors
except ImportError:
    try:
        from .__main__ import main, TabFix, GitignoreMatcher, Colors
    except ImportError:
        print("Warning: Could not import classes from tabfix module")
        main = None
        TabFix = None
        GitignoreMatcher = None
        Colors = None

__all__ = ["main", "TabFix", "GitignoreMatcher", "Colors", "__version__"]
