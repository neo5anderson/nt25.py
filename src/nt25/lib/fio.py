import os
import csv
from typing import Iterable

import pandas as pd

ENCODINGS = ["utf-8", "utf-8-sig", "gbk"]


def _switchEnc(foo, encoding=None, *args, **kwargs):
  result = None

  if encoding is None:
    for enc in ENCODINGS if os.name != "nt" else reversed(ENCODINGS):
      try:
        result = foo(encoding=enc, *args, **kwargs)
        break
      except Exception as e:
        print(e)

  else:
    result = foo(encoding=encoding, *args, **kwargs)

  return result


def _getCSV(file, width, startLine, startCol, encoding):
  f = open(file, encoding=encoding)
  cf = csv.reader(f)

  count = 0
  result = [[] for _ in range(width - startCol)]

  for line in cf:
    if count >= startLine:
      maxWidth = len(line)
      for i in range(startCol, width):
        x = line[i].strip() if maxWidth > i else ""

        try:
          result[i - startCol].append(float(x))
        except ValueError:
          result[i - startCol].append(x)

    count += 1

  f.close()
  return result


def _getCSV2(file, encoding=None, colsInline=True):
  df = pd.read_csv(file, encoding=encoding)

  row = df.to_numpy()
  r = row.T if colsInline else row

  return r.tolist()


def getCSV(file, width=2, startLine=1, startCol=0, encoding=None):
  return _switchEnc(
    foo=_getCSV,
    encoding=encoding,
    file=file,
    width=width,
    startLine=startLine,
    startCol=startCol,
  )


def getCSV2(file, encoding=None):
  return _switchEnc(foo=_getCSV2, encoding=encoding, file=file)


def saveCSV(data, file, encoding=None, colsInline=True):
  if encoding is None:
    encoding = "utf-8"

  with open(file, "w", newline="", encoding=encoding) as f:
    content = []

    for d in data:
      if isinstance(d, str):
        content.append(data[d])
      elif isinstance(d, Iterable):
        content.append(d)

    if colsInline:
      content = list(map(list, zip(*content)))

    cf = csv.writer(f)
    cf.writerows(content)


def saveCSV2(data, file, encoding=None, float_format=None, colsInline=True):
  if data is not None:
    df = pd.DataFrame(data)

    if colsInline:
      df = df.T

    df.to_csv(file, index=False, encoding=encoding, float_format=float_format)


def getXlsx(file, sheet=0, colsInLine=True):
  df = pd.read_excel(file, sheet_name=sheet)

  row = df.to_numpy()
  r = row.T if colsInLine else row

  return r.tolist()


def saveXlsx(data, file, colsInline=True):
  if data is not None:
    df = pd.DataFrame(data)

    if colsInline:
      df = df.T

    df.to_excel(file, index=False)


def ls(path, matcher=None):
  ls = []
  append = True

  for root, _, files in os.walk(path):
    for f in files:
      p = os.path.join(root, f)
      s = os.path.getsize(p)

      if matcher:
        append = matcher(f)

      if append:
        ls.append((f, p, s))

  return ls
