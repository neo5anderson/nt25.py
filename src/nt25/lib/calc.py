import re
from typing import Iterable
import numpy as np

from sympy import symbols, Eq, solve

from sklearn.metrics import r2_score as r2
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures


def str2e(s) -> str:
  return s if len(s) < 5 else f"{float(s):.4e}"


def fl2el(fl) -> list[str]:
  return list(map(lambda f: str2e(str(f)), fl))


def poly(x, y, degree=2) -> Iterable:
  return np.polyfit(x, y, degree).tolist()


def polyResults(coef, x) -> Iterable:
  return np.poly1d(coef)(x).tolist()


def polyRoots(coef) -> Iterable:
  return np.roots(coef).tolist()


def xn2y(X, y, degree=2, output=False, foo="xn2y"):
  poly = PolynomialFeatures(degree=degree, include_bias=False)

  Xa = np.array(X)
  if len(Xa.shape) == 1:
    Xa = np.array([X])

  x = Xa.T
  xp = poly.fit_transform(x)

  model = LinearRegression()
  model.fit(xp, y)
  # y1 = model.predict(xp)

  coef = model.coef_
  names = poly.get_feature_names_out().tolist()

  eq = f"{model.intercept_:.4e} + "
  for i in range(len(names)):
    ex = names[i].replace("^", "**").replace(" ", "*")
    eq += f"({coef[i]:.4e})*{ex} + "

  eq = re.sub(r"x(\d+)", r"x[\1]", eq[:-3])
  func = _genFunc(foo, "x", eq)

  y2 = [func(x[i]) for i in range(len(x))]
  yr2 = r2(y, y2)

  if output:
    q = eq.replace(" + ", " + \\\n\t").replace("*x", " * x").replace("e+00", "")

    print(f"{foo}: degree = {degree}, R² = {yr2:.4%}\n  y = {q}\n")

  return {
    "func": func,
    "r2": yr2,
    "eq": eq,
  }


def _genFunc(name, args, expr):
  local = {}
  src = compile(f"def {name}({args}):\n\treturn {expr}", "<string>", "exec")
  exec(src, {}, local)
  return local[name]


def solveEq(eq, output=False, foo="solve"):
  (x0, x1, y) = symbols("x:2,y")
  eq = re.sub(r"x\[(\d+)\]", r"x\1", eq)
  solution = solve(Eq(eval(eq), y), x0)

  real = []
  for s in solution:
    sol = str(s)
    if "I" in sol:
      continue

    func = _genFunc(foo, "y, x1=0", sol.replace("y", "y[0]"))
    s4e = re.sub(r"([-]?\d*\.\d+)", lambda m: str2e(m.group(0)), sol)

    if output:
      print(f"{foo}: {eq}\n\n  x0 = {s4e}\n")

    real.append(
      {
        "org": eq,
        "func": func,
        "eq": sol,
        "eq.4e": s4e,
      }
    )

  return real
