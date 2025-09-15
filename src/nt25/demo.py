import os
from nt25 import fio, calc, draw, DType, et, __version__, __data_path__

# import timeit
# timeit.timeit('', number=100, globals=globals())


def main():
  print(f"Hello from {__package__}({__version__})! ")

  # [Neo] some file I/O: csv, xlsx
  os.makedirs("output", exist_ok=True)

  fio.saveCSV(
    {
      "Name": ["Alice", "Bob", "Charlie"],
      "Age": [25.2, 30, 35],
      "City": ["New York", "Los Angeles", "Chicago"],
    },
    "output/out.csv",
  )

  data = fio.getXlsx(__data_path__ + "/test.xlsx")
  fio.saveCSV(data, "output/out2.csv")

  h = data[0]
  s = data[1]
  v = data[2]

  # [Neo] some poly calculates
  c = calc.poly(h, v)
  ce = calc.fl2el(c)
  print(c, ce)

  foo = calc.xn2y(h, v, degree=3, output=True)
  bar = calc.solveEq(foo["eq"], output=False)

  func = foo["func"]
  bfunc = bar[0]["func"]

  Y = range(1000, 2000, 200)
  X = [bfunc([y]) for y in Y]

  # [Neo] draw with title, data dots
  ref = draw.draw(X=h, Y=v)
  draw.title(ref, "title", x="xlabel", y="ylabel")
  draw.draw(type=DType.dot, X=X, Y=Y, ref=ref, color="red", s=120)
  draw.show()

  # [Neo] draw with function, split in two
  draw.draw(
    type=DType.func,
    Func=func,
    min=40,
    max=60,
    ref=ref,
    pos=121,
    label="func",
    color="red",
  )
  draw.draw(
    type=DType.func,
    Func=bfunc,
    min=0,
    max=4000,
    ref=ref,
    pos=122,
    label="bfunc",
    labelLocation="upper right",
  )
  draw.show()

  # [Neo] draw with 3d dots, and function in surface
  ref = draw.draw(DType.dot3d, X=h, Y=s, Z=v, color="red", pos=121)
  draw.title(ref, "三维", pos=121)

  foo = calc.xn2y([h, s], v, degree=3, output=True)
  func = foo["func"]

  # change default color
  draw.draw(
    DType.surface,
    h,
    s,
    Func=func,
    ref=ref,
    pos=121,
    cmap="Pastel2_r",
  )
  # auto-gen surface with dots, change default gird size
  draw.draw(DType.wireframe, h, s, v, ref=ref, pos=122, rstride=2, cstride=2)
  draw.show()

  # [Neo] and 3d solve equal
  bar = calc.solveEq(foo["eq"], output=True)

  if len(bar) > 0:
    print(f"solveEq(750, 1.5) ~ {bar[0]['func'](y=[750], x1=1.5):.4f}\n")

  exif = et.parseExif(__data_path__ + "/exif.jpg")
  print("exif:", exif)


if __name__ == "__main__":
  main()
