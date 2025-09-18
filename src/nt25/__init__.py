import importlib.metadata as meta

from .lib import fio, calc, draw, et, ef
from .lib.draw import DType
from .lib.sqlite import SQLite

__version__ = meta.version(str(__package__))
__data_path__ = __file__.replace("__init__.py", "data")

__all__ = (
  "__version__",
  "__data_path__",
  "fio",
  "calc",
  "draw",
  "et",
  "ef",
  "DType",
  "SQLite",
)
