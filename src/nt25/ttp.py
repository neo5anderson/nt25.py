import re
import os
import time
import glob
import argparse

from threading import Thread, Lock
from multiprocessing import cpu_count

from PIL import Image
import numpy as np
import matplotlib.colors as mcolors

gTLock = Lock()
gForceQuit = False

gMaxValue = 0
gShadowValue = 0

gCrop = None
gArea = None
gLast = None
gColors = None

kTifLevel = 255


def nsort(s):
  sub = re.split(r"(\d+)", s)
  sub = [int(c) if c.isdigit() else c for c in sub]
  return sub


def genGradColors(gradStart, gradStop):
  # ks = kTifLevel * kTifLevel
  # yc = np.linspace(mcolors.to_rgba(gradStart),
  #                  mcolors.to_rgba(gradStop), ks) * ks
  # colors = [yc[ks - (i - kTifLevel) * (i - kTifLevel)]
  #           for i in range(0, kTifLevel)]

  colors = (
    np.linspace(mcolors.to_rgba(gradStart), mcolors.to_rgba(gradStop), kTifLevel)
    * kTifLevel
  )

  return np.vstack([[0, 0, 0, 0], colors]).astype(np.uint8)


def splitArray(array, times):
  chunk = len(array) // times
  left = len(array) % times

  result = []
  for i in range(times):
    start = i * chunk + min(i, left)
    end = start + chunk + (1 if i < left else 0)
    result.append(array[start:end])

  return result


def dump(array):
  shp = array.shape
  for i in range(shp[0]):
    print(array[i])


def ttp(array, path, maxValue):
  global gTLock, gForceQuit, gCrop, gArea, gColors, gMaxValue, gLast

  if gCrop is None or gArea is None or gColors is None:
    return

  for tif in array:
    name = os.path.splitext(os.path.basename(tif))[0]
    out = os.path.join(path, name + ".png")

    image = Image.open(tif)
    ta = np.array(image)
    ta = ta[gCrop[0] : gCrop[1], gCrop[2] : gCrop[3]]

    ta[ta < 0] = 0

    with gTLock:
      if ta.max() > gMaxValue:
        gMaxValue = ta.max()

      if gShadowValue > 0:
        leap = maxValue / 40
        ta = np.where(np.logical_and(gArea > 0, ta < gShadowValue), gShadowValue, ta)
        ta = np.where(gLast > ta + leap, gLast - leap, ta)
        gLast = np.array(ta)
        gArea = np.where(ta > gShadowValue, 1, gArea)

    ta[ta > maxValue] = maxValue
    ta = ta / maxValue * kTifLevel
    Image.fromarray(gColors[ta.astype(np.uint8)], mode="RGBA").save(out)

    if gForceQuit:
      break
    else:
      print(".", end="", flush=True)


def main():
  global gForceQuit, gCrop, gArea, gColors, gMaxValue, gLast

  threadCounts = int(cpu_count() / 2)

  parser = argparse.ArgumentParser(description="TIFF -> PNG")
  parser.add_argument(
    "-d",
    "--dir",
    help="Directory to handle",
    default=".",
    type=str,
    required=False,
  )
  parser.add_argument(
    "-s",
    "--gradStart",
    help="Gradient color to Start",
    default="#00FFFF",
    type=str,
    required=False,
  )
  parser.add_argument(
    "-t",
    "--gradStop",
    help="Gradient color to Stop",
    default="#00008B",
    type=str,
    required=False,
  )
  parser.add_argument(
    "--TB",
    help="Crop TIFF from Top to Bottom",
    nargs="+",
    # default=[1700, 3000], type=int, required=False,)
    # default=[1350, 4250], type=int, required=False,)
    default=[1400, 3550],
    type=int,
    required=False,
  )
  # default=[2890, 2895], type=int, required=False,)
  parser.add_argument(
    "--LR",
    help="Crop TIFF from Left to Right",
    nargs="+",
    default=[750, 2300],
    type=int,
    required=False,
  )
  # default=[1650, 1655], type=int, required=False,)
  parser.add_argument(
    "-m",
    "--maxValue",
    help="Map Max Value",
    default=16,
    type=int,
    required=False,
  )
  parser.add_argument(
    "-v",
    "--shadowValue",
    help="keep Value in Shadow",
    default=1,
    type=int,
    required=False,
  )
  parser.add_argument(
    "-c",
    "--threadCounts",
    help="Minimum number of Threads",
    default=threadCounts,
    type=int,
    required=False,
  )

  args = parser.parse_args()
  folder = args.dir
  gradStart = args.gradStart
  gradStop = args.gradStop

  gColors = genGradColors(gradStart, gradStop)

  TB = args.TB
  LR = args.LR
  gCrop = [TB[0], TB[1], LR[0], LR[1]]
  gArea = np.zeros([TB[1] - TB[0], LR[1] - LR[0]], dtype=np.uint8)
  gLast = np.zeros([TB[1] - TB[0], LR[1] - LR[0]])

  maxValue = args.maxValue
  threadCounts = args.threadCounts

  gShadowValue = args.shadowValue

  if gShadowValue > 0:
    print(f"Shadow Value: {gShadowValue}")
    threadCounts = 1

  if threadCounts > 1:
    print(f"Multi-threads to work: {threadCounts}T")

  files = glob.glob(os.path.join(folder, "*.tif"))
  files = sorted(files, key=nsort)

  if len(files) == 0:
    print("no TIF found")
    return

  path = os.path.join(folder, "out")
  if not os.path.exists(path):
    os.makedirs(path)

  tfs = splitArray(files, threadCounts)

  td = []
  for tif in tfs:
    if tif is not None and len(tif) > 0:
      t = Thread(
        target=ttp,
        args=(
          tif,
          path,
          maxValue,
        ),
      )
      t.daemon = True
      t.start()
      td.append(t)

  while True:
    working = False
    for t in td:
      if t.is_alive():
        working = True
        break

    if working:
      try:
        time.sleep(0.5)
      except KeyboardInterrupt:
        if not gForceQuit:
          print("\n> WARN: Trying to terminate threads...")

        gForceQuit = True
    else:
      break

  if gForceQuit:
    print("> WARN: Force quit!")
  else:
    print(f"\nTotal Max value: {maxValue}/{gMaxValue:.2f}")


if __name__ == "__main__":
  main()
