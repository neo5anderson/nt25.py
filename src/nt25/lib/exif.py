import os
import json
import time
import glob
import struct
import argparse
import subprocess

from math import ceil
from shutil import which
from random import randint
from dataclasses import dataclass

from pathlib import Path
from datetime import UTC, datetime, timedelta, timezone

from PIL import Image, ImageOps


@dataclass(frozen=True)
class _consts:
  version = "0.1.4"
  ext = (".jpg", ".jpeg", ".png", ".bmp", ".heic")

  type_png = b"\x89PNG\r\n\x1a\n"
  type_heic = b"ftypheic"

  bytes_image_start = b"\xff\xd8"
  bytes_image_end = b"\xff\xd9"
  bytes_app0 = b"\xff\xe0"
  bytes_app1 = b"\xff\xe1"
  bytes_app2 = b"\xff\xe2"

  bytes_quantization = b"\xff\xdb"
  bytes_huffman = b"\xff\xc4"
  bytes_frame_start = b"\xff\xc0"
  bytes_scan_start = b"\xff\xda"
  bytes_interoperability = b"\xff\xdd"
  bytes_comment = b"\xff\xfe"

  bytes_app1_blank = b"\xff\xe1\x00\x00"
  bytes_app1_add = b"Exif\x00\x00"

  pointer_exif = 0x8769
  pointer_gps = 0x8825

  width_optimized = 1080
  width_thumbnail = 352

  datetime_formatter = "%Y:%m:%d %H:%M:%S"
  epoch = datetime.fromtimestamp(0, tz=UTC)

  types = {
    1: 1,  # BYTE
    2: 1,  # ASCII
    3: 2,  # SHORT
    4: 4,  # LONG
    5: 8,  # RATIONAL (2 LONGs)
    7: 1,  # UNDEFINED
    9: 4,  # SLONG
    10: 8,  # SRATIONAL
  }

  adjust_heic = "eq=brightness=0.05:contrast=1.02:saturation=1.02"


@dataclass(frozen=True)
class _tags:
  Maker = "Maker"
  Model = "Model"
  Orientation = "Orientation"
  DateTime = "DateTime"
  ExifIDF = "ExifIFD"
  GPSInfoIDF = "GPSInfoIFD"

  Version = "Version"
  DateTimeOriginal = "DateTimeOriginal"
  UserComment = "UserComment"

  GPSLatitudeRef = "GPSLatitudeRef"
  GPSLatitude = "GPSLatitude"
  GPSLongitudeRef = "GPSLongitudeRef"
  GPSLongitude = "GPSLongitude"
  GPSTimeStamp = "GPSTimeStamp"
  GPSDateStamp = "GPSDateStamp"

  # JPEGFormat = "JPEGFormat"
  # JPEGFormatLength = "JPEGFormatLength"


Tag = _tags()
Consts = _consts()

T_IFD = {
  0x010F: Tag.Maker,
  0x0110: Tag.Model,
  0x0112: Tag.Orientation,
  0x0132: Tag.DateTime,
  0x8769: Tag.ExifIDF,
  0x8825: Tag.GPSInfoIDF,
}

T_EXIF = {
  0x9000: Tag.Version,
  0x9003: Tag.DateTimeOriginal,
  0x9286: Tag.UserComment,
}

T_GPS = {
  0x0001: Tag.GPSLatitudeRef,
  0x0002: Tag.GPSLatitude,
  0x0003: Tag.GPSLongitudeRef,
  0x0004: Tag.GPSLongitude,
  0x0007: Tag.GPSTimeStamp,
  0x001D: Tag.GPSDateStamp,
}

# T_TN = {
#   0x0201: Tag.JPEGFormat.value,
#   0x0202: Tag.JPEGFormatLength.value,
# }


def _check():
  return which("ffmpeg") is not None


def _run(cmd):
  return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")


def _str2ts(str):
  ts = -1

  try:
    ts = int(datetime.strptime(str, Consts.datetime_formatter).timestamp())
  except Exception:
    pass

  return ts


def _str2dt(str):
  d = None

  try:
    d = datetime.strptime(str, Consts.datetime_formatter)
  except Exception:
    pass

  return d


def _dt2str(dt):
  return None if dt is None else dt.strftime(Consts.datetime_formatter)


def _gpsDT(d, t, offset=8):
  d = _str2dt(f"{d} {int(t[0])}:{int(t[1])}:{int(t[2])}")

  if d is not None:
    utc = d.replace(tzinfo=timezone.utc)
    return utc.astimezone(timezone(timedelta(hours=offset)))


def _get(obj, key, default=None):
  return obj[key] if obj and key in obj else default


def _get_sub(obj, key, sub="value", default=None):
  value = default

  try:
    value = obj[key][sub]
  except Exception:
    pass

  return value


def _deg(values, ref):
  if values is None or ref is None:
    return None

  d, m, s = values
  deg = d + m / 60.0 + s / 3600.0

  if ref in [b"S", b"W"]:
    deg = -deg

  return deg


def _pack(fmt, value, endian="M"):
  prefix = "<" if endian == "I" else ">"
  return struct.pack(prefix + fmt, *value)


def _unpack(fmt, data, endian="M"):
  prefix = "<" if endian == "I" else ">"
  return struct.unpack(prefix + fmt, data)


def _gen_box(data, offset=0):
  box = {}

  if not data:
    return box

  if offset > 0:
    data = data[offset:]

  off = 0
  length = len(data)
  while off + 8 <= length:
    s, t = _unpack("I4s", data[off : off + 8])

    try:
      type = t.rstrip(b"\x00").decode("utf-8", errors="replace")

      if type in box:
        if not isinstance(box[type], list):
          first = box[type]
          box[type] = []
          box[type].append(first)

        box[type].append(data[off : off + s])
      else:
        box[type] = data[off : off + s]

      if "meta" == type:
        break

    except Exception:
      break

    off += s

  return box


def _get_heic_wh(iprp):
  items = _gen_box(iprp, 8)
  # _dump_items(items, ".iprp")

  ipco = _get(items, "ipco")
  items = _gen_box(ipco, 8)
  # _dump_items(items, ".ipco")

  ispe = _get(items, "ispe")
  if ispe and len(ispe) >= 2:
    w, h = _unpack("II", ispe[0][12:])
    width, height = _unpack("II", ispe[1][12:])

  return w, h, width, height


def _heic_exif_range(iinf, iloc):
  index = -1
  if not iinf or len(iinf) < 20 or not iloc or len(iloc) < 20:
    return -1, -1

  iinf_items = _gen_box(iinf[12 + 2 :])
  infe = _get(iinf_items, "infe")
  if infe and isinstance(infe, list):
    for i in range(len(infe)):
      if infe[i][16:20] == b"Exif":
        index = _unpack("H", infe[i][12:14])[0]
        break

  if index == -1:
    return -1, -1

  pos = 8
  version = int(iloc[pos])

  pos += 1 + 3
  length = iloc[pos] >> 4
  base_offset_size = iloc[pos + 1] >> 4
  index_size = base_offset_size if version <= 2 else 0

  pos += 2
  if version < 2:
    count = _unpack("H", iloc[pos : pos + 2])[0]
    pos += 2
  else:
    count = _unpack("I", iloc[pos : pos + 4])[0]
    pos += 4

  for _ in range(count):
    if version < 2:
      iid = _unpack("H", iloc[pos : pos + 2])[0]
      pos += 2
    else:
      iid = _unpack("I", iloc[pos : pos + 4])[0]
      pos += 4

    pos += 4
    base_offset = int.from_bytes(iloc[pos : pos + base_offset_size])
    pos += base_offset_size
    extent_count = _unpack("H", iloc[pos : pos + 2])[0]
    pos += 2

    for _ in range(extent_count):
      if iid == index:
        pos += index_size
        extend_offset = _unpack("I", iloc[pos : pos + length])[0]
        pos += length
        extend_length = _unpack("I", iloc[pos : pos + length])[0]
        pos += length

        start = base_offset + extend_offset + 4
        return start, start + extend_length
      else:
        pos += index_size + length + length

  return -1, -1


def _gen_jpg_segments_lite(data, app1=None, adjust=None):
  if not data or len(data) < 10 or Consts.bytes_image_start != data[0:2]:
    return []

  head = 2
  ignored = 0
  app1_added = False
  segments = [Consts.bytes_image_start]

  total = len(data)
  while True:
    if head + 2 >= total:
      break

    # fixed bytes fill
    if 0xFF != data[head]:
      head += 1

      if 0xFF == data[head + 1]:
        head += 1
      continue

    prefix = data[head : head + 2]
    length = _unpack("H", data[head + 2 : head + 4])[0]
    end = head + 2 + length

    if Consts.bytes_scan_start == prefix:
      if not app1_added:
        if app1 and len(app1) > 10:
          segments.append(app1)

      comment = f"nt25.ex.{Consts.version}"

      if adjust:
        comment += "\n" + "\n".join(adjust.split(","))

      segments.append(_comment_seg(comment))

      # k = end
      # while k < total - 1:
      #   if data[k] == 0xFF and data[k + 1] != 0x00:
      #     k += 2
      #     break
      #   k += 1
      # # almost k == total
      # segments.append(data[head:k])

      segments.append(data[head:])
      break

    else:
      if prefix in (
        Consts.bytes_app2,
        Consts.bytes_quantization,
        Consts.bytes_huffman,
        Consts.bytes_interoperability,
        Consts.bytes_frame_start,
      ):
        segments.append(data[head:end])

      elif (
        Consts.bytes_app1 == prefix
        and Consts.bytes_app1_add == data[head + 4 : head + 10]
      ):
        if app1:
          app1_added = True

          if len(app1) > 10:
            segments.append(app1)

        else:
          segments.append(data[head:end])

      # elif Consts.bytes_comment == prefix:
      #   print(f"comment: {data[head + 4 : end]}")

      else:
        ignored += 1

        # print(f"append: {prefix}, {length}")
        # segments.append(data[head:end])
        pass

      head = end

  return segments


def _ifd(data, start, endian, offset, match):
  tags = {}
  num = _unpack("H", data[offset : offset + 2], endian)[0]
  off = offset + 2

  for i in range(num):
    d = data[off : off + 12]
    tag, typ, count = _unpack("HHI", d[:8], endian)
    _data = d[8:12]

    type_size = Consts.types.get(typ, 1)
    data_len = type_size * count
    if data_len <= 4:
      bytes = _data[:data_len]
    else:
      val_off = _unpack("I", _data, endian)[0]
      bytes = data[start + val_off : start + val_off + data_len]

    value = None
    if typ == 2:  # ASCII
      try:
        value = bytes.rstrip(b"\x00").decode("utf-8", errors="replace")
      except Exception:
        value = bytes
    elif typ in (1, 7):  # BYTE / UNDEFINED
      if count == 1:
        value = bytes[0]
      else:
        value = list(bytes)
    elif typ == 3:  # SHORT (2 bytes)
      fmt = "H" * count
      value = (
        list(_unpack(fmt, bytes, endian))
        if count > 1
        else _unpack("H", bytes, endian)[0]
      )
    elif typ == 4:  # LONG (4 bytes)
      fmt = "I" * count
      value = (
        list(_unpack(fmt, bytes, endian))
        if count > 1
        else _unpack("I", bytes, endian)[0]
      )
    elif typ == 9:  # SLONG
      fmt = "i" * count
      value = (
        list(_unpack(fmt, bytes, endian))
        if count > 1
        else _unpack("i", bytes, endian)[0]
      )
    elif typ == 5:  # RATIONAL
      vals = []
      for j in range(count):
        n = _unpack("I", bytes[j * 8 : j * 8 + 4], endian)[0]
        d = _unpack("I", bytes[j * 8 + 4 : j * 8 + 8], endian)[0]
        vals.append(n if d == 0 else n / d)
      value = vals if count > 1 else vals[0]
    elif typ == 10:  # SRATIONAL
      vals = []
      for j in range(count):
        n = _unpack("i", bytes[j * 8 : j * 8 + 4], endian)[0]
        d = _unpack("i", bytes[j * 8 + 4 : j * 8 + 8], endian)[0]
        vals.append(n if d == 0 else n / d)
      value = vals if count > 1 else vals[0]
    else:
      value = bytes

    name = match.get(tag, hex(tag))
    if not name.startswith("0x"):
      tags[name] = {
        "tag": tag,
        "type": typ,
        "count": count,
        "value": value,
        "endian": endian,
        "raw": bytes,
        "prefix": data[off : off + 8],
      }

    off += 12

  next = _unpack("I", data[off : off + 4], endian)[0]
  return tags, next


def _gen_ifd(tags, endian, offset):
  data = b""
  entries = []

  offset += 2 + len(tags) * 12 + 4

  for name, info in tags.items():
    typ = info["type"]
    count = info["count"]
    raw = info["raw"]
    prefix = info["prefix"]

    type_size = Consts.types.get(typ, 1)
    data_len = type_size * count

    if data_len <= 4:
      field = raw.ljust(4, b"\x00")
    else:
      field = _pack("I", (offset,), endian)
      data += raw
      offset += len(raw)

    entry = prefix + field
    entries.append(entry)

  num = _pack("H", (len(entries),), endian)
  next = _pack("I", (0,), endian)

  return bytearray(num + b"".join(entries) + next + data)


def _parse_exif(data):
  result = {"ifd": {}, "exif": {}, "gps": {}, "tn": {}}
  cursor = 0

  if data is None or len(data) < 10:
    return result

  if len(data) >= 4 and Consts.bytes_app1 == data[:2]:
    cursor = 4
    # exifLength = _unpack("H", data[2:4], endian="M")[0]
    # print(f"exif length = {exifLength}, data.len = {len(data)}")

  if Consts.bytes_app1_add != data[cursor : cursor + 6]:
    return result

  cursor += 6
  start = cursor

  if data[cursor : cursor + 2] == b"II":
    endian = "I"  # little
  elif data[cursor : cursor + 2] == b"MM":
    endian = "M"  # big
  else:
    return result

  cursor += 2

  magic = _unpack("H", data[cursor : cursor + 2], endian)[0]
  if magic != 0x2A:
    return result

  cursor += 2

  offset = _unpack("I", data[cursor : cursor + 4], endian)[0]
  cursor = start + offset

  ifd0, offset = _ifd(data, start, endian, cursor, T_IFD)
  result["ifd"] = ifd0

  # if offset > 0:
  #   tag, _ = _ifd(data, start, endian, start + offset, T_TN)
  #   result["tn"] = tag

  if Tag.ExifIDF in ifd0:
    pointer = ifd0[Tag.ExifIDF]["raw"]
    offset = _unpack("I", pointer[:4], endian)[0]
    if offset > 0:
      tag, _ = _ifd(data, start, endian, start + offset, T_EXIF)
      result["exif"] = tag

  if Tag.GPSInfoIDF in ifd0:
    pointer = ifd0[Tag.GPSInfoIDF]["raw"]
    offset = _unpack("I", pointer[:4], endian)[0]
    if offset > 0:
      tag, _ = _ifd(data, start, endian, start + offset, T_GPS)
      result["gps"] = tag

  return result


def _exif2json(exif):
  result = {}

  result["maker"] = _get_sub(exif["ifd"], Tag.Maker)
  result["model"] = _get_sub(exif["ifd"], Tag.Model)

  orientation = _get_sub(exif["ifd"], Tag.Orientation)
  if orientation:
    result["orientation"] = orientation

  try:
    raw = exif["exif"][Tag.Version]["raw"]
    v = raw.decode("utf-8")
    result["exif.version"] = f"{int(v[:2])}.{int(v[2:].rstrip('0') or '0')}"
  except Exception:
    pass

  # comment = _get(exif["exif"], Tag.UserComment)
  # result["comment"] = comment

  modify = _get_sub(exif["ifd"], Tag.DateTime)
  create = _get_sub(exif["exif"], Tag.DateTimeOriginal)

  createDT = _str2dt(create)
  modifyDT = _str2dt(modify)

  result["datetime.create"] = _dt2str(createDT)
  result["datetime.modify"] = _dt2str(modifyDT)

  lat = _get_sub(exif["gps"], Tag.GPSLatitude)
  lat_ref = _get_sub(exif["gps"], Tag.GPSLatitudeRef)
  lon = _get_sub(exif["gps"], Tag.GPSLongitude)
  lon_ref = _get_sub(exif["gps"], Tag.GPSLongitudeRef)

  result["latitude"] = _deg(lat, lat_ref)
  result["longitude"] = _deg(lon, lon_ref)

  gpsDate = _get_sub(exif["gps"], Tag.GPSDateStamp)
  gpsTime = _get_sub(exif["gps"], Tag.GPSTimeStamp)

  gpsTs = -1
  if gpsDate is not None and gpsTime is not None:
    offset = int(time.localtime().tm_gmtoff / 3600)
    gpsDT = _gpsDT(gpsDate, gpsTime, offset=offset)

    if gpsDT is not None:
      gpsTs = int(gpsDT.timestamp())
      result["datetime.gps"] = _dt2str(gpsDT)

  createTs = int(_str2ts(create))
  modifyTs = int(_str2ts(modify))

  result["ts"] = createTs

  if createTs > 0:
    offset = int(max(modifyTs, gpsTs) - createTs)
    result["offset"] = offset
    result["offsetDelta"] = str(datetime.fromtimestamp(offset, tz=UTC) - Consts.epoch)

  return result


def _find_ifd_tag(data, tag, endian):
  index = -1

  if data and len(data) > 14:
    num = _unpack("H", data[:2], endian)[0]
    offset = 2

    for i in range(num):
      if tag == _unpack("H", data[offset : offset + 2], endian)[0]:
        index = offset + 8
        break

      offset += 12

  return index


def _gen_exif_lite(data, removeOrientation=True):
  if not data or len(data) < 10:
    return b""

  app1 = _parse_exif(data)

  ifd = app1["ifd"]
  exif = app1["exif"]
  gps = app1["gps"]

  # tn = app1["tn"]
  # if len(tn) > 0:
  #   with open("thumbnail.jpg", "wb") as f:
  #     offset = _get(tn, Tag.JPEGFormat)
  #     length = _get(tn, Tag.JPEGFormatLength)
  #     # [TODO] shrink image end
  #     f.write(seg[offset + 10 : length])

  app1Bytes = bytearray(data[: 10 + 2 + 2])
  endian = "I" if data[10:12] == b"II" else "M"
  app1Bytes += _pack("I", (8,), endian)

  offset = 8
  if removeOrientation and Tag.Orientation in ifd:
    del ifd[Tag.Orientation]

  ifdBytes = _gen_ifd(ifd, endian, offset)

  exifBytes = bytearray()
  if Tag.ExifIDF in ifd:
    index = _find_ifd_tag(ifdBytes, Consts.pointer_exif, endian)
    if index > 0:
      offset = 8 + len(ifdBytes)
      lengthBytes = _pack("I", (offset,), endian)
      ifdBytes[index] = lengthBytes[0]
      ifdBytes[index + 1] = lengthBytes[1]
      ifdBytes[index + 2] = lengthBytes[2]
      ifdBytes[index + 3] = lengthBytes[3]

      if Tag.UserComment in exif:
        # cv = f"nt25.ex"
        # raw = cv.encode("utf-8")
        # count = len(raw)

        # c = exif[Tag.UserComment]
        # c["value"] = cv
        # c["raw"] = raw
        # c["count"] = count
        # c["prefix"] = c["prefix"][:4] + _pack("I", (count,), endian)
        del exif[Tag.UserComment]

      exifBytes = _gen_ifd(exif, endian, offset)

  gpsBytes = bytearray()
  if Tag.GPSInfoIDF in ifd:
    index = _find_ifd_tag(ifdBytes, Consts.pointer_gps, endian)
    if index > 0:
      offset = 8 + len(ifdBytes) + len(exifBytes)
      lengthBytes = _pack("I", (offset,), endian)
      ifdBytes[index] = lengthBytes[0]
      ifdBytes[index + 1] = lengthBytes[1]
      ifdBytes[index + 2] = lengthBytes[2]
      ifdBytes[index + 3] = lengthBytes[3]
      gpsBytes = _gen_ifd(gps, endian, offset)

  app1Bytes += bytes(ifdBytes) + bytes(exifBytes) + bytes(gpsBytes)

  lengthBytes = _pack("H", (len(app1Bytes) - 2,))
  app1Bytes[2] = lengthBytes[0]
  app1Bytes[3] = lengthBytes[1]

  return bytes(app1Bytes)


def parseExif(file):
  result = {}

  if not os.path.isfile(file):
    return result

  info = _file(file)
  app1 = _parse_exif(_get(info, "exif"))
  result = _exif2json(app1)
  return result


def mergeExif(exif, to, removeOrientation=True, adjust=None):
  result = False

  exif = _gen_exif_lite(exif, removeOrientation)
  with open(to, "rb") as f:
    data = f.read()

  segments = _gen_jpg_segments_lite(data, exif, adjust)
  if len(segments) > 2:
    with open(to, "wb") as f:
      s = b"".join(segments)
      f.write(s)
      result = True

  return result


def _comment_seg(comment, enc="utf-8"):
  cb = comment.encode(enc)
  length = len(cb) + 2
  return Consts.bytes_comment + length.to_bytes(2) + cb


def _file(file):
  result = {}

  type = None
  width = -1
  height = -1

  with open(file, "rb") as f:
    header = f.read(16)

    if Consts.bytes_image_start == header[:2]:
      type = ".jpg"

      f.seek(0)
      data = f.read()

      head = 2
      while True:
        if head + 2 >= len(data):
          break

        # fixed bytes fill
        if 0xFF != data[head]:
          head += 1

          if 0xFF == data[head + 1]:
            head += 1
          continue

        prefix = data[head : head + 2]
        length = _unpack("H", data[head + 2 : head + 4])[0]
        end = head + 2 + length

        if Consts.bytes_scan_start == prefix:
          break

        elif Consts.bytes_frame_start == prefix:
          height, width = _unpack("HH", data[head + 5 : head + 9])

        elif (
          Consts.bytes_app1 == prefix
          and Consts.bytes_app1_add == data[head + 4 : head + 10]
        ):
          result["exif"] = data[head:end]

        if "exif" in result and height > 0 and width > 0:
          break

        head = end

    elif Consts.type_heic == header[4:12]:
      type = ".heic"
      f.seek(0)
      data = f.read()

      box = _gen_box(data)
      meta = _get(box, "meta")
      items = _gen_box(meta, 12)

      iprp = _get(items, "iprp")
      w, h, width, height = _get_heic_wh(iprp)
      result["rows"] = int(ceil(width / w))
      result["cols"] = int(ceil(height / h))

      iinf = _get(items, "iinf")
      iloc = _get(items, "iloc")
      exif_start, exif_offset = _heic_exif_range(iinf, iloc)
      result["exif"] = Consts.bytes_app1_blank + data[exif_start:exif_offset]

    elif header.startswith(Consts.type_png):
      f.seek(16)
      width, height = _unpack("II", f.read(8))

      typ = f.read(2)
      type = ".png" if typ[1] > 2 else ".png.jpg"

    elif header.startswith(b"BM"):
      f.seek(18)
      type = ".bmp.jpg"
      width, height = _unpack("II", f.read(8), "I")

  result["type"] = type
  result["width"] = width
  result["height"] = height

  return result


def _shrink(file, output, maxWidth=None, merge=True, magic=False, adjust=None):
  shrink = False

  info = _file(file)
  type = _get(info, "type")
  w = _get(info, "width", -1)
  h = _get(info, "height", -1)
  r = _get(info, "rows", -1)
  c = _get(info, "cols", -1)

  if not type:
    return shrink

  if magic:
    if not _check():
      return shrink

    path = str(Path(file).resolve())
    shell = ["ffmpeg", "-hide_banner", "-i", path]

    if type == ".heic":
      if r < 0 or c < 0:
        return shrink

      if not os.path.exists(".ex"):
        os.mkdir(".ex")

      tile_file = os.path.join(".", ".ex", "%03d.jpg")
      merged_file = os.path.join(".", ".ex", "ex.jpg")

      # [TODO] adjust by maker & model
      # app1 = _parse_exif(_get(info, "exif"))
      # maker = _get_sub(app1["ifd"], Tag.Maker)
      # model = _get_sub(app1["ifd"], Tag.Model)
      # print(f"{maker}, {model}, {adjust}")

      if adjust:
        shell += ["-vf", adjust]

      shell += [
        "-map",
        "0",
        tile_file,
      ]
      sr = _run(shell)

      if sr.returncode != 0:
        return shrink

      shell = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        tile_file,
        "-vf",
        f"tile={r}x{c}",
        "-frames:v",
        "1",
        "-y",
        merged_file,
      ]

      sr = _run(shell)
      if sr.returncode != 0:
        if not os.path.exists(merged_file):
          return shrink

      shell = ["ffmpeg", "-hide_banner", "-i", merged_file, "-vf", f"crop={w}:{h}:0:0"]
      type = ".heic.jpg"

    if maxWidth and w > maxWidth:
      m = max(w, h)
      if m > maxWidth:
        scale = maxWidth / m
        w = int(ceil(scale * w))
        shell += ["-vf", f"scale={w}:-1"]

    suffix = str(randint(100, 999)) + type
    ofile = file + suffix

    shell += ["-y", path + suffix]
    sr = _run(shell)

    if type.startswith(".heic"):
      for t in glob.glob(os.path.join(".ex", "*.jpg")):
        try:
          os.remove(t)
        except Exception:
          pass

    if sr.returncode != 0:
      if not os.path.exists(ofile):
        return shrink

  else:
    img = Image.open(file)
    img = ImageOps.exif_transpose(img)

    w, h = img.size

    if maxWidth is not None:
      m = max(w, h)
      if m > maxWidth:
        scale = maxWidth / m
        w = int(scale * w)
        h = int(scale * h)
        img = img.resize((w, h))

    _, ext = os.path.splitext(file)
    end = ext.lower()

    if img.mode == "RGB":
      end = ".jpg"

    suffix = str(randint(1000, 9999)) + end
    ofile = file + suffix
    img.save(ofile, optimize=True)
    img.close()

    if not os.path.exists(ofile):
      return shrink

  if type.endswith(".jpg"):
    if merge:
      exif = _get(info, "exif")
    else:
      exif = b""

    mergeExif(exif, ofile, type == ".jpg")

  times = float(os.path.getsize(ofile)) / os.path.getsize(file)
  shrink = times < 1

  if file == output and not shrink:
    os.remove(ofile)
  else:
    os.replace(ofile, output)

  # print(f" > {output} has shrink {times:.1%}")
  return shrink


def shrinkFile(
  file,
  optimizeWidth=Consts.width_optimized,
  thumbnailWidth=Consts.width_thumbnail,
  override=True,
  magic=False,
  adjust=None,
):
  result = False

  if not os.path.exists(file):
    return result

  name, ext = os.path.splitext(file)
  if ext.lower() == ".heic":
    magic = True

  if override:
    result = _shrink(file, file, magic=magic, adjust=adjust)
  else:
    result = _shrink(file, name + "-new" + ext, magic=magic, adjust=adjust)
    if result:
      file = name + "-new" + ext
    else:
      return result

  _shrink(file, name + "-o" + ext, maxWidth=optimizeWidth, merge=False, magic=magic)
  _shrink(
    file, name + "-thumbnail" + ext, maxWidth=thumbnailWidth, merge=False, magic=magic
  )

  return result


def main():
  parser = argparse.ArgumentParser(description="EXIF tool")
  parser.add_argument("-v", "--version", action="store_true", help="echo version")
  parser.add_argument("-f", "--file", type=str, help="parse image Exif info")
  parser.add_argument("-t", "--to", type=str, help="merge exif to file")
  parser.add_argument(
    "-m",
    "--magic",
    action="store_true",
    help="shrink with magic",
    default=False,
  )
  parser.add_argument(
    "-o",
    "--override",
    action="store_true",
    help="override original file",
    default=False,
  )
  parser.add_argument(
    "-a",
    "--adjust",
    type=str,
    help="output with adjust arguments",
    default=None,
  )
  parser.add_argument(
    "-s",
    "--shrink",
    type=str,
    help="shrink file or folder with optimize and thumbnail generated",
  )

  args = parser.parse_args()

  if args.file:
    if args.to:
      info = _file(args.file)
      exif = _get(info, "exif")
      result = {"merge": mergeExif(exif, args.to)}
    else:
      result = parseExif(args.file)

  elif args.shrink:
    if not args.adjust:
      args.adjust = Consts.adjust_heic

    if os.path.isdir(args.shrink):
      files = []
      for d, _, f in os.walk(args.shrink):
        for file in f:
          _, e = os.path.splitext(file)
          if e.lower() in Consts.ext:
            files.append(os.path.join(d, file))

      shrink = 0
      for f in files:
        if shrinkFile(f, override=args.override, magic=args.magic, adjust=args.adjust):
          shrink += 1

      result = {
        "total": len(files),
        "shrink": shrink,
        "override": args.override,
        "magic": args.magic,
        "adjust": args.adjust,
      }

    else:
      result = {
        "result": shrinkFile(
          args.shrink, override=args.override, magic=args.magic, adjust=args.adjust
        ),
        "override": args.override,
        "magic": args.magic,
        "adjust": args.adjust,
      }

  elif args.version:
    result = {"version": Consts.version, "magic": _check()}
  else:
    print("usage: ex [-h] [-v] [-f FILE [-t FILE]] [[-o] [-m] -s FILE]")
    return

  print(json.dumps(result, indent=2))


if __name__ == "__main__":
  main()
