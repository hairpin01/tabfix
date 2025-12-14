__version__ = "1.0.0"
__author__ = "hairpin01"
__license__ = "GNU General Public License v3.0"

from tabfix.core import TabFix
from tabfix.git_utils import GitignoreMatcher
from tabfix.color_utils import Colors

__all__ = ["TabFix", "GitignoreMatcher", "Colors", "__version__"]
