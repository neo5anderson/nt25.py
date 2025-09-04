import importlib.metadata as meta

from .lib import fio, calc, draw
from .lib.draw import DType

__version__ = meta.version(str(__package__))
__samples_path__ = __file__.replace('__init__.py', 'samples')

__all__ = ('__version__', '__samples_path__', 'fio', 'calc', 'draw', 'DType')
