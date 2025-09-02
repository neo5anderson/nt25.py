import importlib.metadata as meta

from .lib import fio
from .lib.sqlite import SQLite
from .lib.exif import parseExif, shrinkFile

__version__ = meta.version(str(__package__))
__data_path__ = __file__.replace("__init__.py", "data")

__all__ = (
  "__version__",
  "__data_path__",
  "fio",
  "SQLite",
  "parseExif",
  "shrinkFile",
)
