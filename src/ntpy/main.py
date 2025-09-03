from ntpy import fio, calc, draw, DType, __version__

# import timeit
# timeit.timeit('', number=100, globals=globals())


def main():
  print(f"Hello from {__package__}({__version__})! ")

  # [Neo] some file I/O: csv, xlsx
  fio.saveCSV({
      'Name': ['Alice', 'Bob', 'Charlie'],
      'Age': [25.2, 30, 35],
      'City': ['New York', 'Los Angeles', 'Chicago']
  }, "out.csv", colsInline=False)

  data = fio.getXlsx('ds/qs.xlsx')
  fio.saveCSV(data, "out2.csv")

  h = data[0]
  s = data[1]
  v = data[2]

  # [Neo] some poly calculates
  c = calc.poly(h, v)
  ce = calc.fl2el(c)
  print(c, ce)

  foo = calc.xn2y(h, v, degree=3, output=True)
  bar = calc.solveEq(foo['eq'])

  func = foo['func']
  bfunc = bar[0]['func']

  Y = range(1000, 2000, 200)
  X = [bfunc(y) for y in Y]

  # [Neo] draw 2d with types
  ref = {}
  draw.d2d(X=h, Y=v, ref=ref)
  draw.d2d(type=DType.scatter, X=X, Y=Y, ref=ref, color='red', s=120)
  draw.d2d(type=DType.func, Func=func, min=40, max=60, ref=ref, color='red')
  draw.show()

  # [Neo] and 3d calcs
  foo = calc.xn2y([h, s], v, degree=3, output=False)
  bar = calc.solveEq(foo['eq'], output=True)

  if len(bar) > 0:
    print('s> 750, 1.5 ~', bar[0]['func'](y=750, x1=1.5))


if __name__ == "__main__":
  main()
