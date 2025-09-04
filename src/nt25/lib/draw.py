from enum import Enum
from random import sample

import numpy as np

from matplotlib.axes import Axes
from matplotlib import pyplot as plot

# import matplotlib.animation as animation


FONTS = ['PingFang SC', 'Microsoft YaHei', 'Arial']
COLORS = ['blue', 'red', 'orange', 'black', 'pink']

REFS = []


class DType(Enum):
  scatter = 1,
  line = 2,
  func = 3,


def onClose(event):
  global REFS

  for r in REFS:
    del r['figure']
    del r['subplot']

  REFS.clear()


def _getPlot(ref, pos, font='Roboto') -> Axes:
  global REFS

  if 'figure' not in ref:
    fig = plot.figure()
    fig.canvas.mpl_connect('close_event', onClose)

    plot.rcParams['font.sans-serif'] = [font] + FONTS
    plot.rcParams['axes.unicode_minus'] = False

    ref['figure'] = fig
    REFS.append(ref)

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


def _genParam(pIn, pDefault, count):
  if pIn is None:
    pIn = pDefault

  if count == 1:
    if isinstance(pIn, (list, tuple)):
      pIn = pIn[0]

  elif len(pIn) != count:
    # print(f"bad len {len(pIn)} != {count}")
    pIn = None

  return pIn


def _coord(ref, X, Y,  pos, label, color, randomColor, method,
           *args, **kwargs):
  if X is None or Y is None:
    print("no X/Y to draw")
    return

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

  pos = _genParam(pos, [111] * count, count)
  label = _genParam(label, [111] * count, count)
  color = _genParam(color, _genList(COLORS, count, random=randomColor), count)

  if pos is None or label is None or color is None:
    print("bad length")
    return

  if count == 1:
    p = _getPlot(ref, pos)
    method(p, X, Y, label=label, color=color, *args, **kwargs)

  elif (isinstance(pos, list) and
        isinstance(label, list) and isinstance(color, list)):

    for i in range(count):
      p = _getPlot(ref, pos[i])
      method(p, X[i], Y[i], label=label[i], color=color[i], *args, **kwargs)

  return ref


def title(ref, title, pos=111, x=None, y=None, z=None):
  result = False

  if 'subplot' in ref:
    sub = ref['subplot']

    if pos in sub:
      result = True
      sub[pos].set_title(title)

      if x:
        sub[pos].set_xlabel(x)

      if y:
        sub[pos].set_ylabel(y)

      if z:
        sub[pos].set_zlabel(z)

  return result


def d2d(type=DType.scatter, X=None, Y=None, Func=None, min=None, max=None,
        ref=None, pos=None, label=None, color=None,
        randomColor=False, labelLocation='upper left',
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

  ref = _coord(ref, X, Y, pos=pos, label=label, color=color,
               randomColor=randomColor, method=func, *args, **kwargs)

  if label is not None:
    plot.legend(loc=labelLocation)

  return ref


def show():
  plot.show()


def clear():
  plot.clf()
