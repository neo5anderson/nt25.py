import os
import time
import json
import struct
import argparse

from random import randint
from datetime import UTC, datetime, timedelta, timezone

from PIL import Image as pi
from exif import Image, DATETIME_STR_FORMAT

VERSION = "0.2.4"
MAX_WIDTH = 1000
THUMBNAIL_WIDTH = 352

COMMENT_SEGMENT = b"\xff\xfe"
EPOCH = datetime.fromtimestamp(0, UTC)
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".bmp")
# IMAGE_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".webp")


NOT_FOUND = "not found"
INTERNAL_FAILED = "internal failed"


def dms2dec(dms: tuple):
  d, m, s = dms
  return d + m / 60 + s / 3600


def dtFormatter(str):
  return datetime.strptime(str, DATETIME_STR_FORMAT)


def dt2str(dt):
  return None if dt is None else dt.strftime(DATETIME_STR_FORMAT)


def gpsDt2Dt(date, time, offset=8):
  d = dtFormatter(f"{date} {int(time[0])}:{int(time[1])}:{int(time[2])}")
  utc = d.replace(tzinfo=timezone.utc)
  return utc.astimezone(timezone(timedelta(hours=offset)))


def genThumbnail(file):
  _, ext = os.path.splitext(file)
  name = file[: -len(ext)] + ".thumbnail" + ext
  return optimizeFile(file, mw=THUMBNAIL_WIDTH, copyExif=False, name=name)


def optimizeFile(file, q=80, mw=MAX_WIDTH, copyExif=True, name=None):
  optimized = False

  if not os.path.exists(file):
    return optimized

  img = pi.open(file)
  w, h = img.size
  m = max(w, h)

  if m > mw:
    scale = mw / m
    w = int(scale * w)
    h = int(scale * h)
    img = img.resize((w, h))

  _, ext = os.path.splitext(file)
  end = ext.lower()

  if img.mode == "RGB":
    end = ".jpg"

  suffix = str(randint(1000, 9999)) + end
  ofile = file + suffix

  if end == ".png":
    img.save(ofile, optimize=True)
  elif end == ".jpg" or end == ".jpeg":
    img.save(ofile, quality=q, optimize=True)
  else:
    img.save(ofile, optimize=True)

  img.close()

  if not os.path.exists(ofile):
    return optimized

  if copyExif:
    transplant(file, ofile, optimize=False)

  optimized = os.path.getsize(ofile) < os.path.getsize(file) * 0.8

  if name is not None:
    os.replace(ofile, name)
  elif optimized:
    os.replace(ofile, file)
  else:
    os.remove(ofile)

  return optimized


def tryGet(img, key, default):
  value = default

  try:
    value = img[key]
  except Exception:
    pass

  return value


def dumpExif(file, optimize=False):
  result = {"version": VERSION}

  if not os.path.exists(file):
    result["file"] = NOT_FOUND
    return result

  with open(file, "rb") as f:
    img = Image(f)
    for key in img.get_all():
      try:
        result[key] = str(img[key])
      except Exception:
        # result["file"] = INTERNAL_FAILED
        pass

  if optimize:
    result["optimized"] = optimizeFile(file)  # type: ignore

  return result


def parseExif(file, optimize=False):
  result = {}

  if not os.path.exists(file):
    result["file"] = NOT_FOUND
    return result

  with open(file, "rb") as f:
    img = Image(f)

  if optimize:
    result["optimized"] = optimizeFile(file)

  # width = tryGet(img, "pixel_x_dimension", -1)
  # height = tryGet(img, "pixel_y_dimension", -1)

  # if width < 0:
  #   width = tryGet(img, "image_width", -1)
  #   height = tryGet(img, "image_height", -1)

  create = tryGet(img, "datetime_original", None)
  modify = tryGet(img, "datetime", None)

  createDt = None if create is None else dtFormatter(create)
  modifyDt = None if modify is None else dtFormatter(modify)

  latitude = tryGet(img, "gps_latitude", None)
  latitude = None if latitude is None else dms2dec(latitude)

  latRef = tryGet(img, "gps_latitude_ref", default="N")
  if latRef != "N" and latitude:
    latitude = -latitude

  longitude = tryGet(img, "gps_longitude", None)
  longitude = None if longitude is None else dms2dec(longitude)

  longRef = tryGet(img, "gps_longitude_ref", default="E")
  if longRef != "E" and longitude:
    longitude = -longitude

  gpsDatetime = None
  gd = tryGet(img, "gps_datestamp", None)
  gt = tryGet(img, "gps_timestamp", None)

  if gd and gt:
    offset = int(time.localtime().tm_gmtoff / 3600)
    gpsDatetime = gpsDt2Dt(gd, gt, offset=offset)

  ts = -1 if createDt is None else int(createDt.timestamp())
  mTs = -1 if modifyDt is None else int(modifyDt.timestamp())
  gpsTs = -1 if gpsDatetime is None else int(gpsDatetime.timestamp())

  if ts > 0:
    offset = max(mTs, gpsTs) - ts
    offsetDelta = str(datetime.fromtimestamp(offset, UTC) - EPOCH)
  else:
    offset = None
    offsetDelta = None

  result.update(
    {
      # "width": width,
      # "height": height,
      "latitude": latitude,
      "longitude": longitude,
      "datetime.create": dt2str(createDt),
      "datetime.modify": dt2str(modifyDt),
      "datetime.gps": dt2str(gpsDatetime),
      "ts": ts,
      "offset": offset,
      "offset.delta": offsetDelta,
    }
  )

  return result


class InvalidImageDataError(ValueError):
  pass


def _segments(data):
  if data[0:2] != b"\xff\xd8":
    return []

  head = 2
  segments = [b"\xff\xd8"]

  while 1:
    if data[head : head + 2] == b"\xff\xda":
      segments.append(data[head:])
      break

    else:
      length = struct.unpack(">H", data[head + 2 : head + 4])[0]
      endPoint = head + length + 2
      seg = data[head:endPoint]
      segments.append(seg)
      head = endPoint

    if head >= len(data):
      raise InvalidImageDataError("Wrong JPEG data.")

  return segments


def _comment(segments, comment: str, enc="utf-8"):
  contains = False

  if len(segments) > 1:
    cb = comment.encode(enc)
    length = len(cb) + 2

    cbSeg = COMMENT_SEGMENT + length.to_bytes(2, byteorder="big") + cb

    for i in range(len(segments)):
      if segments[i][0:2] == COMMENT_SEGMENT:
        segments[i] = cbSeg
        contains = True
        break

    if not contains:
      length = len(segments)
      segments.insert(1 if length == 2 else length - 2, cbSeg)

  return segments


def _exif(segments):
  for seg in segments:
    if seg[0:2] == b"\xff\xe1" and seg[4:10] == b"Exif\x00\x00":
      return seg

  return b""


def _merge(segments, exif=b""):
  if len(segments) > 1:
    if (
      segments[1][0:2] == b"\xff\xe0"
      and segments[2][0:2] == b"\xff\xe1"
      and segments[2][4:10] == b"Exif\x00\x00"
    ):
      if exif:
        segments[2] = exif
        segments.pop(1)
      elif exif is None:
        segments.pop(2)
      else:
        segments.pop(1)

    elif segments[1][0:2] == b"\xff\xe0":
      if exif:
        segments[1] = exif

    elif segments[1][0:2] == b"\xff\xe1" and segments[1][4:10] == b"Exif\x00\x00":
      if exif:
        segments[1] = exif
      elif exif is None:
        segments.pop(1)

    else:
      if exif:
        segments.insert(1, exif)

  return b"".join(segments)


def removeExif(file, optimize=False):
  result = {}

  if not os.path.exists(file):
    result["file"] = NOT_FOUND
    return result

  with open(file, "rb") as f:
    data = f.read()

  segments = _segments(data)

  if len(segments) > 1:
    segments = list(
      filter(
        lambda seg: not (seg[0:2] == b"\xff\xe1" and seg[4:10] == b"Exif\x00\x00"),
        segments,
      )
    )

    segments = _comment(segments, "nt25.et")
    data = b"".join(segments)

    with open(file, "wb+") as f:
      f.write(data)
      result["result"] = True

      if optimize:
        result["optimized"] = optimizeFile(file)

  return result


def transplant(src, dst, optimize=False):
  result = {}

  if not os.path.exists(src) or not os.path.exists(dst):
    result["file"] = NOT_FOUND
    return result

  with open(src, "rb") as f:
    s = f.read()

  segments = _segments(s)
  exif = _exif(segments)

  if optimize:
    result["optimized"] = optimizeFile(dst, copyExif=False)

  with open(dst, "rb") as f:
    data = f.read()

  segments = _segments(data)

  if len(segments) > 1:
    segments = _comment(segments, "nt25.et")
    data = _merge(segments, exif)

    with open(dst, "wb+") as f:
      f.write(data)
      result["result"] = True

  return result


def main():
  parser = argparse.ArgumentParser(description="EXIF tool")
  parser.add_argument("-v", "--version", action="store_true", help="echo version")
  parser.add_argument("-f", "--file", type=str, help="image file")
  parser.add_argument(
    "-d", "--dump", action="store_true", help="dump meta, use: -d -f FILE"
  )
  parser.add_argument("-c", "--copy", type=str, help="copy meta, use: -c SRC -f DST")
  parser.add_argument(
    "-r", "--rm", action="store_true", help="remove meta, use: -r -f FILE"
  )
  parser.add_argument(
    "-o",
    "--optimize",
    action="store_true",
    help="optimize jpg file, work with -r, -d, -c, -f",
  )

  parser.add_argument(
    "-s",
    "--shrink",
    type=str,
    help=f"shrink file/folder with max width {MAX_WIDTH}",
  )
  parser.add_argument(
    "-m",
    "--max",
    type=int,
    default=MAX_WIDTH,
    help="set max width when shrinking",
  )
  parser.add_argument(
    "-t",
    "--thumbnail",
    action="store_true",
    help="generate thumbnail when shrinking",
  )

  args = parser.parse_args()

  result = {}

  if args.version:
    result = {"version": VERSION}

  if args.file is not None:
    opt = True if args.optimize else False

    if args.dump:
      r = dumpExif(args.file, optimize=opt)
    elif args.copy:
      r = transplant(args.copy, args.file, optimize=opt)
    elif args.rm:
      r = removeExif(args.file, optimize=opt)
    else:
      r = parseExif(args.file, optimize=opt)

    result.update(r)  # type: ignore

  if args.shrink is not None:
    max = args.max if args.max is not None else MAX_WIDTH

    if os.path.isdir(args.shrink):
      total = 0
      shrink = 0
      thumbnail = 0

      for d, _, f in os.walk(args.shrink):
        for file in f:
          _, e = os.path.splitext(file)
          if e.lower() in IMAGE_EXT:
            path = os.path.join(d, file)
            total += 1

            if optimizeFile(path, mw=max):
              shrink += 1

            if args.thumbnail:
              thumbnail += 1
              genThumbnail(path)

      r = {"total": total, "shrink": shrink, "thumbnail": thumbnail}

    elif os.path.isfile(args.shrink):
      r = {"result": optimizeFile(args.shrink, mw=max)}

      if args.thumbnail:
        r.update({"thumbnail": genThumbnail(args.shrink)})

    if r is not None:
      result.update(r)  # type: ignore

  if len(result) > 0:
    print(
      json.dumps(
        result,
        indent=2,
      )
    )
  else:
    print(
      "usage: et [-h] [-v] [-f FILE [-d] [-o] [-r]]\n"
      "\t\t[-c SRC -f DST] [-s FILE [-t] [-m MAX]]"
    )


if __name__ == "__main__":
  main()
