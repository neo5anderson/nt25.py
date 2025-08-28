import importlib.metadata as meta

from .lib import t

__version__ = meta.version(str(__package__))
__all__ = ('__version__', 't')
