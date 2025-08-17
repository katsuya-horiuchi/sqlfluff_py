from importlib.metadata import version
from sqlfluff_py.fix import get_script

__version__ = version("sqlfluff_py")

__all__ = ["get_script"]
