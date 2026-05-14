from importlib.metadata import version
from sqlfluff_py.fix import fix_script

__version__ = version("sqlfluff_py")

__all__ = ["fix_script"]
