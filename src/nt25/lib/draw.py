from enum import Enum
from random import sample

import numpy as np

from matplotlib import pyplot as plot
from matplotlib.axes import Axes
from mpl_toolkits.mplot3d import Axes3D

from . import calc

# import matplotlib.animation as animation


FONTS = [
  "Microsoft YaHei",
  "PingFang SC",
  "Arial Unicode MS",
  "Noto Sans CJK SC",
  "Arial",
]

COLORS = ["blue", "red", "orange", "black", "pink"]

REFS = []


class DType(Enum):
  dot = 1
  line = 2
  func = 3
  dot3d = 4
  wireframe = 5
  surface = 6


def onClose(event):
  global REFS

  for r in REFS:
    del r["figure"]
    del r["subplot"]

  REFS.clear()


def _getPlot(ref, pos, is3D):
  global REFS

  if "figure" not in ref:
    fig = plot.figure()
    fig.canvas.mpl_connect("close_event", onClose)

    plot.rcParams["font.sans-serif"] = FONTS
    plot.rcParams["axes.unicode_minus"] = False

    ref["figure"] = fig
    REFS.append(ref)

  if "subplot" not in ref:
    ref["subplot"] = {}

  fig = ref["figure"]
  sub = ref["subplot"]

  if pos not in sub:
    sub[pos] = fig.add_subplot(pos, projection="3d") if is3D else fig.add_subplot(pos)

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


def title(ref, title, pos=111, x=None, y=None, z=None):
  result = False

  if "subplot" in ref:
    sub = ref["subplot"]

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


def _gen3DXY(X, Y, extend=0.2):
  dx = (max(X) - min(X)) * extend
  d0 = np.linspace(min(X) - dx, max(X) + dx)

  dy = (max(Y) - min(Y)) * extend
  d1 = np.linspace(min(Y) - dy, max(Y) + dy)

  return np.meshgrid(d0, d1)


def draw(
  type=DType.dot,
  X=None,
  Y=None,
  Z=None,
  Func=None,
  min=None,
  max=None,
  ref=None,
  pos=None,
  label=None,
  color=None,
  randomColor=False,
  labelLocation="upper left",
  *args,
  **kwargs,
):
  if ref is None:
    ref = {}

  is3D = False
  method = Axes.scatter

  match type:
    case DType.line:
      method = Axes.plot

    case DType.func:
      method = Axes.plot

      if Func is not None and min is not None and max is not None:
        if callable(Func):
          Func = (Func,)

        X = []
        Y = []

        for i in range(len(Func)):
          dx = np.linspace(
            min[i] if isinstance(min, (list, tuple)) else min,
            max[i] if isinstance(max, (list, tuple)) else max,
          )

          X.append(dx)
          Y.append([Func[i]([x]) for x in dx])

    case DType.dot3d:
      is3D = True
      method = Axes3D.scatter

    case DType.wireframe:
      is3D = True
      # rstride=2, cstride=2
      method = Axes3D.plot_wireframe

    case DType.surface:
      is3D = True
      # cmap='Pastel2_r', antialiased=True
      method = Axes3D.plot_surface

  if X is None or Y is None:
    print("no X/Y to draw")
    return

  Xa = np.array(X)
  Ya = np.array(Y)

  if Xa.shape != Ya.shape:
    print(f"bad shape {Xa.shape} != {Ya.shape}")
    return

  if type == DType.dot3d:
    if Z is None:
      print("Z cannot be None")
      return

    Za = np.array(Z)
    if Xa.shape != Za.shape:
      print(f"bad shape {Xa.shape} == {Ya.shape} != {Za.shape}")
      return

  elif is3D:
    if Z is not None and Func is None:
      Za = np.array(Z)
      if Xa.shape != Za.shape:
        print(f"bad shape {Xa.shape} == {Ya.shape} != {Za.shape}")
        return

      F = calc.xn2y([X, Y], Z, degree=3)
      Func = F["func"]

    if Func is None:
      print("Func cannot be None")
      return

    if callable(Func):
      X, Y = _gen3DXY(X, Y)
      Z = Func([X, Y])
    else:
      print("Func need callable")
      return

  count = 1
  # count = Xa.shape[0] if len(Xa.shape) > 1 else 1

  if len(Xa.shape) > 1:
    count = Xa.shape[0]
    if count == 1:
      X = X[0]
      Y = Y[0]

      if Z is not None and isinstance(Z, list):
        Z = Z[0]

  if is3D and type != DType.dot3d:
    count = 1

  pos = _genParam(pos, [111] * count, count)
  label = _genParam(label, [None] * count, count)
  color = _genParam(color, _genList(COLORS, count, random=randomColor), count)

  if pos is None or color is None:
    print("bad length")
    return

  if count == 1:
    p = _getPlot(ref, pos, is3D)
    _draw(method, p, type, X, Y, Z, label=label, color=color, *args, **kwargs)

  elif isinstance(pos, list) and isinstance(label, list) and isinstance(color, list):
    for i in range(count):
      p = _getPlot(ref, pos[i], is3D)
      _draw(
        method,
        p,
        type,
        X[i],
        Y[i],
        Z[i] if isinstance(Z, list) else None,
        label,
        color,
        *args,
        **kwargs,
      )

  if label is not None:
    plot.legend(loc=labelLocation)

  return ref


def _draw(method, p, type, x, y, z, label, color, *args, **kwargs):
  match type:
    case DType.dot3d | DType.wireframe:
      method(p, x, y, z, label=label, color=color, antialiased=True, *args, **kwargs)

    case DType.surface:
      method(p, x, y, z, label=label, antialiased=True, *args, **kwargs)

    case _:
      method(p, x, y, label=label, color=color, *args, **kwargs)


def show():
  plot.show()


def clear():
  plot.clf()
