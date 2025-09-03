from enum import Enum
from random import sample

import numpy as np

from matplotlib.axes import Axes
from matplotlib import pyplot as plot

# import matplotlib.animation as animation


FONTS = ['PingFang SC', 'Microsoft YaHei', 'Arial']
COLORS = ['blue', 'red', 'orange', 'black', 'pink']


def _getPlot(ref, pos, font='Roboto') -> Axes:
  if 'figure' not in ref:
    ref['figure'] = plot.figure()
    plot.rcParams['font.sans-serif'] = [font] + FONTS
    # plot.rcParams['font.sans-serif'] = ['Arial']
    plot.rcParams['axes.unicode_minus'] = False

  if 'subplot' not in ref:
    ref['subplot'] = {}

  fig = ref['figure']
  sub = ref['subplot']

  if pos not in sub:
    sub[pos] = fig.add_subplot(pos)

  return sub[pos]


def _genList(refer: list, length, random=False):
  r = []

  while len(r) < length:
    r += sample(refer, len(refer)) if random else refer

  return r[:length]


def _coord(ref, X, Y, color, pos, randomColor, method, *args, **kwargs):
  Xa = np.array(X)
  Ya = np.array(Y)

  if Xa.shape != Ya.shape:
    print(f"bad shape {Xa.shape} != {Ya.shape}")
    return

  count = 1
  # count = Xa.shape[0] if len(Xa.shape) > 1 else 1

  if len(Xa.shape) > 1:
    count = Xa.shape[0]
    if count == 1:
      X = X[0]
      Y = Y[0]

  if color is None:
    color = _genList(COLORS, count, random=randomColor)

  if count == 1:
    if isinstance(color, (list, tuple)):
      color = color[0]
  elif len(color) != count:
    print(f"bad color.len {len(color)} != {count}")
    return

  if pos is None:
    pos = [111] * count

  if count == 1:
    if isinstance(pos, (list, tuple)):
      pos = pos[0]
  elif len(pos) != count:
    print(f"bad pos.len {len(pos)} != {count}")
    return

  if count > 1 and isinstance(pos, list):
    for i in range(count):
      p = _getPlot(ref, pos[i])
      method(p, X[i], Y[i], color=color[i], *args, **kwargs)
  else:
    p = _getPlot(ref, pos)
    method(p, X, Y, color=color, *args, **kwargs)

  return ref


class DType(Enum):
  scatter = 1,
  line = 2,
  func = 3,


def d2d(type=DType.scatter, X=None, Y=None, Func=None, min=None, max=None,
        ref=None, color=None, pos=None, randomColor=False, show=False,
        *args, **kwargs):
  if ref is None:
    ref = {}

  match type:
    case DType.scatter:
      func = Axes.scatter

    case DType.line:
      func = Axes.plot

    case DType.func:
      func = Axes.plot
      if Func is not None and min is not None and max is not None:
        if callable(Func):
          Func = (Func,)

        X = []
        Y = []

        for i in range(len(Func)):
          dx = np.linspace(min[i] if isinstance(min, (list, tuple)) else min,
                           max[i] if isinstance(max, (list, tuple)) else max)

          X.append(dx)
          Y.append([Func[i]([x]) for x in dx])

  ref = _coord(ref, X, Y, color=color, pos=pos, randomColor=randomColor,
               method=func, *args, **kwargs)

  if show:
    plot.show()

  return ref


def show():
  plot.show()


def clear():
  plot.clf()
