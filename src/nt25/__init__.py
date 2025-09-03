import importlib.metadata as meta

from .lib import fio, calc, draw
from .lib.draw import DType

__version__ = meta.version(str(__package__))
__all__ = ('__version__', 'fio', 'calc', 'draw', 'DType')
