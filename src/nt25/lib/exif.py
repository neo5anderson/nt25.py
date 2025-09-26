import os
import json
import time
import glob
import struct
import argparse
import subprocess

from enum import Enum
from math import ceil
from shutil import which
from random import randint

from pathlib import Path
from datetime import UTC, datetime, timedelta, timezone

from PIL import Image, ImageOps


IMAGE_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".heic")
MAGIC_EXT = ".heic"

FT_PNG = b"\x89PNG\r\n\x1a\n"
FT_HEIC = b"ftypheic"

S_SOI = b"\xff\xd8"
S_EOI = b"\xff\xd9"
S_ICC = b"\xff\xe0"
S_APP1 = b"\xff\xe1"
S_DQT = b"\xff\xdb"
S_DHT = b"\xff\xc4"
S_DCT = b"\xff\xc0"
S_SOS = b"\xff\xda"
S_DRI = b"\xff\xdd"
S_COM = b"\xff\xfe"
S_APP1410 = b"Exif\x00\x00"
S_APP100 = b"\xff\xe1\x00\x00"

TP_EXIF = 0x8769
TP_GPS = 0x8825

VERSION = "0.1.1"


class Tag(Enum):
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


T_IFD = {
  0x010F: Tag.Maker.value,
  0x0110: Tag.Model.value,
  0x0112: Tag.Orientation.value,
  0x0132: Tag.DateTime.value,
  0x8769: Tag.ExifIDF.value,
  0x8825: Tag.GPSInfoIDF.value,
}

T_EXIF = {
  # 0x9000: Tag.Version.value,
  0x9003: Tag.DateTimeOriginal.value,
  0x9286: Tag.UserComment.value,
}

T_GPS = {
  0x0001: Tag.GPSLatitudeRef.value,
  0x0002: Tag.GPSLatitude.value,
  0x0003: Tag.GPSLongitudeRef.value,
  0x0004: Tag.GPSLongitude.value,
  0x0007: Tag.GPSTimeStamp.value,
  0x001D: Tag.GPSDateStamp.value,
}

# T_TN = {
#   0x0201: Tag.JPEGFormat.value,
#   0x0202: Tag.JPEGFormatLength.value,
# }

TYPE_SIZES = {
  1: 1,  # BYTE
  2: 1,  # ASCII
  3: 2,  # SHORT
  4: 4,  # LONG
  5: 8,  # RATIONAL (2 LONGs)
  7: 1,  # UNDEFINED
  9: 4,  # SLONG
  10: 8,  # SRATIONAL
}

OPTIMIZE_WIDTH = 1080
THUMBNAIL_WIDTH = 352

DATETIME_STR_FORMAT = "%Y:%m:%d %H:%M:%S"
EPOCH = datetime.fromtimestamp(0, tz=UTC)


def _check():
  return which("ffmpeg") is not None


def _run(cmd):
  return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")


def _str2ts(str):
  ts = -1

  try:
    ts = int(datetime.strptime(str, DATETIME_STR_FORMAT).timestamp())
  except Exception:
    pass

  return ts


def _str2dt(str):
  d = None

  try:
    d = datetime.strptime(str, DATETIME_STR_FORMAT)
  except Exception:
    pass

  return d


def _dt2str(dt):
  return None if dt is None else dt.strftime(DATETIME_STR_FORMAT)


def _gpsDT(d, t, offset=8):
  d = _str2dt(f"{d} {int(t[0])}:{int(t[1])}:{int(t[2])}")

  if d is not None:
    utc = d.replace(tzinfo=timezone.utc)
    return utc.astimezone(timezone(timedelta(hours=offset)))


def _pack(fmt, value, endian="M"):
  prefix = "<" if endian == "I" else ">"
  return struct.pack(prefix + fmt, *value)


def _unpack(fmt, data, endian="M"):
  prefix = "<" if endian == "I" else ">"
  return struct.unpack(prefix + fmt, data)


def _sof(data):
  precision = data[0]
  height = _unpack("H", data[1:3])[0]
  width = _unpack("H", data[3:5])[0]

  nf = data[5]
  components = []
  pos = 6

  for _ in range(nf):
    cid = data[pos]
    hv = data[pos + 1]
    tq = data[pos + 2]
    h, v = hv >> 4, hv & 0x0F
    components.append({"id": cid, "H": h, "V": v, "Tq": tq})
    pos += 3

  return {
    "precision": precision,
    "width": width,
    "height": height,
    "components": components,
  }


def _box(f):
  start = f.tell()
  header = f.read(8)
  if len(header) < 8:
    return None, None, None

  size, box_type = struct.unpack(">I4s", header)
  return size, box_type.decode("utf-8"), start


def _find_box(f, target, parent_end=None):
  while True:
    pos = f.tell()
    if parent_end and pos >= parent_end:
      return (None, None)

    size, box_type, start = _box(f)
    # print(f"find: {start}, {size}, {box_type}")

    if not size:
      return (None, None)

    if box_type == target:
      return (start, size)

    f.seek(start + size)


def _uint(f, size):
  if size == 0:
    return 0

  return int.from_bytes(f.read(size))


def _find_iloc(f, iloc_start, iloc_size, exif_item_id):
  f.seek(iloc_start + 8)  # 跳过 header
  version = f.read(1)[0]
  f.read(3)  # flags

  tmp = f.read(2)
  offset_size = tmp[0] >> 4
  length_size = tmp[0] & 0xF
  base_offset_size = tmp[1] >> 4
  index_size = tmp[1] & 0xF if version in (1, 2) else 0

  if version < 2:
    item_count = struct.unpack(">H", f.read(2))[0]
  else:
    item_count = struct.unpack(">I", f.read(4))[0]

  # ilocList = []

  for _ in range(item_count):
    if version < 2:
      item_id = struct.unpack(">H", f.read(2))[0]
    else:
      item_id = struct.unpack(">I", f.read(4))[0]

    f.read(4)
    # construction_method = struct.unpack(">H", f.read(2))[0] & 0x0FFF
    # data_reference_index = struct.unpack(">H", f.read(2))[0]

    base_offset = _uint(f, base_offset_size)
    extent_count = struct.unpack(">H", f.read(2))[0]

    for _ in range(extent_count):
      if index_size > 0:
        _ = _uint(f, index_size)  # extent_index
      extent_offset = _uint(f, offset_size)
      extent_length = _uint(f, length_size)

      if item_id == exif_item_id:
        return base_offset + extent_offset, extent_length
      # ilocList.append((base_offset + extent_offset, extent_length))

  # return ilocList
  return None, None


def _from_heic(file):
  with open(file, "rb") as f:
    meta_pos = _find_box(f, "meta")
    if not meta_pos:
      print("No meta box found.")
      return
    meta_start, meta_size = meta_pos
    f.seek(meta_start + 12)

    iinf_start, iinf_size = _find_box(f, "iinf", meta_start + meta_size)
    if not iinf_start:
      print("No iinf.")
      return

    f.seek(iinf_start + 12)
    entry_count = struct.unpack(">H", f.read(2))[0]

    exif_item_id = None
    for _ in range(entry_count):
      size, box_type, start = _box(f)
      if box_type == "infe":
        version = f.read(1)[0]
        f.read(3)  # flags
        if version >= 2:
          item_id = struct.unpack(">H", f.read(2))[0]
          f.read(2)  # protection
          item_type = f.read(4).decode("utf-8")
          if item_type == "Exif":
            exif_item_id = item_id
            break
      f.seek(start + size)

    if not exif_item_id:
      print("No Exif item in iinf.")
      return

    f.seek(meta_start + 12)
    iloc_start, iloc_size = _find_box(f, "iloc", meta_start + meta_size)
    if not iloc_start:
      print("No iloc.")
      return

    exif_offset, exif_length = _find_iloc(f, iloc_start, iloc_size, exif_item_id)
    if not exif_offset:
      print("No Exif offset found in iloc.")
      return

    f.seek(0)
    mdat_start, _ = _find_box(f, "mdat")
    if not mdat_start:
      print("No mdat.")
      return

    f.seek(exif_offset + 4)
    data = f.read(exif_length)

    return S_APP100 + data


def _extract_exif(file):
  type, _, _ = _gen_shrink_type(file)
  if type == ".heic":
    return _from_heic(file)

  with open(file, "rb") as f:
    data = f.read()

  exif = b""
  if data[0:2] == S_SOI:
    head = 2

    while True:
      prefix = data[head : head + 2]
      length = _unpack("H", data[head + 2 : head + 4])[0]
      end = head + 2 + length

      if prefix == S_SOS:
        break

      elif prefix == S_APP1 and data[head + 4 : head + 10] == S_APP1410:
        exif = data[head:end]
        break

      head = end
      if head >= len(data):
        break

  return exif


def _gen_segments_lite(data):
  if data is None or data[0:2] != S_SOI:
    return []

  head = 2
  segments = [S_SOI]
  ignored = 0

  while True:
    if data[head : head + 2] == S_SOS:
      segments.append(data[head:])
      break
    else:
      prefix = data[head : head + 2]
      length = _unpack("H", data[head + 2 : head + 4])[0]
      end = head + 2 + length

      if prefix in (S_DQT, S_DHT, S_DCT, S_DRI):
        segments.append(data[head:end])

      elif prefix == S_APP1 and data[head + 4 : head + 10] == S_APP1410:
        segments.append(data[head:end])

      else:
        ignored += 1
        pass

      head = end

    if head >= len(data):
      break

  return segments


def _ifd(data, start, endian, offset, match):
  tags = {}
  num = _unpack("H", data[offset : offset + 2], endian)[0]
  off = offset + 2

  for i in range(num):
    d = data[off : off + 12]
    tag, typ, count = _unpack("HHI", d[:8], endian)
    _data = d[8:12]

    type_size = TYPE_SIZES.get(typ, 1)
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

    type_size = TYPE_SIZES.get(typ, 1)
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


def _get(entry, tag: Tag, default=None):
  value = default

  try:
    value = entry[tag.value]["value"]
  except Exception:
    pass

  return value


def _val(entry):
  if not entry:
    return None

  try:
    return _unpack("I", entry["raw"][:4], entry["endian"])[0]
  except Exception:
    return None


def _deg(values, ref):
  if values is None or ref is None:
    return None

  d, m, s = values
  deg = d + m / 60.0 + s / 3600.0

  if ref in [b"S", b"W"]:
    deg = -deg

  return deg


def _parse_exif(data):
  result = {"ifd": {}, "exif": {}, "gps": {}, "tn": {}}
  cursor = 0

  if data is None or len(data) < 4:
    return result

  if len(data) >= 4 and data[:2] == S_APP1:
    cursor = 4
    # exifLength = _unpack("H", data[2:4], endian="M")[0]
    # print(f"exif length = {exifLength}, data.len = {len(data)}")

  if data[cursor : cursor + 6] != S_APP1410:
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

  offset = _val(ifd0.get(Tag.ExifIDF.value))
  if offset:
    tag, _ = _ifd(data, start, endian, start + offset, T_EXIF)
    result["exif"] = tag

  offset = _val(ifd0.get(Tag.GPSInfoIDF.value))
  if offset:
    tag, _ = _ifd(data, start, endian, start + offset, T_GPS)
    result["gps"] = tag

  return result


def _exif2json(exif):
  result = {}

  result["maker"] = _get(exif["ifd"], Tag.Maker)
  result["model"] = _get(exif["ifd"], Tag.Model)

  result["orientation"] = _get(exif["ifd"], Tag.Orientation)
  modify = _get(exif["ifd"], Tag.DateTime)

  # comment = _get(exif["exif"], Tag.UserComment)
  # result["comment"] = comment

  create = _get(exif["exif"], Tag.DateTimeOriginal)

  createDT = _str2dt(create)
  modifyDT = _str2dt(modify)

  result["datetime.create"] = _dt2str(createDT)
  result["datetime.modify"] = _dt2str(modifyDT)

  lat = _get(exif["gps"], Tag.GPSLatitude)
  lat_ref = _get(exif["gps"], Tag.GPSLatitudeRef)
  lon = _get(exif["gps"], Tag.GPSLongitude)
  lon_ref = _get(exif["gps"], Tag.GPSLongitudeRef)

  result["latitude"] = _deg(lat, lat_ref)
  result["longitude"] = _deg(lon, lon_ref)

  gpsDate = _get(exif["gps"], Tag.GPSDateStamp)
  gpsTime = _get(exif["gps"], Tag.GPSTimeStamp)

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
    result["offsetDelta"] = str(datetime.fromtimestamp(offset, tz=UTC) - EPOCH)

  return result


def _find_pf(data, tag, endian):
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


def _gen_string(comment, enc):
  cb = comment.encode(enc)
  length = len(cb) + 2
  return length.to_bytes(2) + cb


def _comment(segments, comment, enc="utf-8"):
  contains = False

  if len(segments) > 1:
    cb = S_COM + _gen_string(comment, enc)

    for i in range(len(segments)):
      if segments[i][0:2] == S_COM:
        segments[i] = cb
        contains = True
        break

    if not contains:
      length = len(segments)
      segments.insert(1 if length == 2 else length - 2, cb)

  return segments


def _gen_exif_lite(seg, removeOrientation=True):
  app1 = _parse_exif(seg)

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

  app1Bytes = bytearray(seg[: 10 + 2 + 2])
  endian = "I" if seg[10:12] == b"II" else "M"
  app1Bytes += _pack("I", (8,), endian)

  offset = 8
  if removeOrientation and Tag.Orientation.value in ifd:
    del ifd[Tag.Orientation.value]

  ifdBytes = _gen_ifd(ifd, endian, offset)

  exifBytes = bytearray()
  if Tag.ExifIDF.value in ifd:
    index = _find_pf(ifdBytes, TP_EXIF, endian)
    if index > 0:
      offset = 8 + len(ifdBytes)
      lengthBytes = _pack("I", (offset,), endian)
      ifdBytes[index] = lengthBytes[0]
      ifdBytes[index + 1] = lengthBytes[1]
      ifdBytes[index + 2] = lengthBytes[2]
      ifdBytes[index + 3] = lengthBytes[3]

      if Tag.UserComment.value in exif:
        cv = "nt25..."
        raw = cv.encode("utf-8")
        count = len(raw)

        c = exif[Tag.UserComment.value]
        c["value"] = cv
        c["raw"] = raw
        c["count"] = count
        c["prefix"] = c["prefix"][:4] + _pack("I", (count,), endian)
        # del exif[Tag.UserComment.value]

      exifBytes = _gen_ifd(exif, endian, offset)

  gpsBytes = bytearray()
  if Tag.GPSInfoIDF.value in ifd:
    index = _find_pf(ifdBytes, TP_GPS, endian)
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

  exif = _extract_exif(file)
  app1 = _parse_exif(exif)
  result = _exif2json(app1)
  return result


def mergeExif(exif, to, removeOrientation=True):
  result = False

  if not exif or len(exif) < 4:
    return result

  exif = _gen_exif_lite(exif, removeOrientation)
  with open(to, "rb") as f:
    data = f.read()

  segments = _gen_segments_lite(data)

  if len(segments) > 1:
    segmentLite = []
    for seg in segments:
      prefix = seg[0:2]

      if prefix in (S_SOS, S_DQT, S_DHT, S_DCT, S_DRI):
        segmentLite.append(seg)

      elif prefix == S_SOI:
        segmentLite.append(seg)

        if len(exif) > 0:
          segmentLite.append(exif)

    with open(to, "wb") as f:
      f.write(b"".join(segmentLite))
      result = True

  return result


def genComment(file):
  result = False

  if not os.path.isfile(file):
    return result

  with open(file, "rb") as f:
    data = f.read()

  segments = _gen_segments_lite(data)
  if len(segments) > 1:
    _comment(segments, "nt25.ex")
    with open(file, "wb") as f:
      f.write(b"".join(segments))
      result = True

  return result


def get_heic_size(filename):
  with open(filename, "rb") as f:
    # 找 meta box
    meta_pos = _find_box(f, "meta")
    if not meta_pos:
      raise ValueError("No meta box found")
    meta_start, meta_size = meta_pos
    f.seek(meta_start + 12)  # skip fullbox header

    # 找 iprp (ItemPropertiesBox)
    iprp_pos = _find_box(f, "iprp", meta_start + meta_size)
    if not iprp_pos:
      raise ValueError("No iprp box found")
    iprp_start, iprp_size = iprp_pos

    # 找 ipco (ItemPropertyContainerBox)
    f.seek(iprp_start + 8)
    ipco_pos = _find_box(f, "ipco", iprp_start + iprp_size)
    if not ipco_pos:
      raise ValueError("No ipco box found")
    ipco_start, ipco_size = ipco_pos

    # 遍历 ipco 里的 box，找 ispe
    f.seek(ipco_start + 8)
    while f.tell() < ipco_start + ipco_size:
      size, box_type, start = _box(f)
      if not size:
        break
      if box_type == "ispe":
        f.seek(start + 12)  # 跳过 FullBox header
        width = struct.unpack(">I", f.read(4))[0]
        height = struct.unpack(">I", f.read(4))[0]
        print(width, height)

      f.seek(start + size)


def _gen_shrink_type(file):
  type = "null"
  width = -1
  height = -1

  with open(file, "rb") as f:
    header = f.read(16)

    if header[:2] == S_SOI:
      type = ".jpg"

      f.seek(0)
      data = f.read()

      i = 2
      while i < len(data):
        if S_SOS == data[i : i + 2]:
          break

        length = _unpack("H", data[i + 2 : i + 4])[0]
        if S_DCT == data[i : i + 2]:
          height, width = _unpack("HH", data[i + 5 : i + 9])
          break

        i += 2 + length

    elif header[4:12] == FT_HEIC:
      type = ".heic"

    elif header.startswith(FT_PNG):
      f.seek(16)
      width, height = _unpack("II", f.read(8))

      typ = f.read(2)
      type = ".png" if typ[1] > 2 else ".png.jpg"

    elif header.startswith(b"BM"):
      f.seek(18)
      type = ".bmp.jpg"
      width, height = _unpack("II", f.read(8), "I")

  return type, width, height


def getWH(file: str) -> tuple[str, int, int]:
  with open(file, "rb") as f:
    header = f.read(16)

    type = "null"
    height = -1
    width = -1

    if header.startswith(S_SOI):
      f.seek(0)
      data = f.read()

      i = 2
      while i < len(data):
        (marker,) = _unpack("H", data[i : i + 2])
        (block,) = _unpack("H", data[i + 2 : i + 4])

        if 0xFFC0 == marker:
          type = ".jpg"
          height, width = _unpack("HH", data[i + 5 : i + 9])
          break

        i += 2 + block

    elif header.startswith(b"\x89PNG\r\n\x1a\n"):
      f.seek(16)
      type = ".png"
      width, height = _unpack("II", f.read(8))

      typ = f.read(2)
      if typ[1] <= 2:
        type = ".png.jpg"

    elif header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
      f.seek(6)
      type = ".gif"
      width, height = _unpack("HH", f.read(4), "I")

    elif header.startswith(b"BM"):
      f.seek(18)
      type = ".bmp.jpg"
      width, height = _unpack("II", f.read(8), "I")

    elif header.startswith(b"II") or header.startswith(b"MM"):
      f.seek(0)
      endian = "I" if header.startswith(b"II") else "M"
      version = _unpack("H", header[2:4], endian)[0]

      offset = 0
      if version == 42:  # ClassicTIFF
        offset_size = 4
        entry_size = 12

        f.seek(4)
        offset = _unpack("I", f.read(4), endian)[0]

        def parse(offset):
          f.seek(offset)

          entries = []
          count = _unpack("H", f.read(2), endian)[0]
          for _ in range(count):
            raw = f.read(entry_size)
            tag, typ, count, value = _unpack("HHII", raw, endian)
            entries.append((tag, typ, count, value))

          next = _unpack("I", f.read(4), endian)[0]
          return entries, next

      elif version == 43:  # BigTIFF
        offset_size = _unpack("H", header[4:6], endian)[0]
        if offset_size == 8:
          entry_size = 20
          offset = _unpack("Q", header[8:16], endian)[0]

          def parse(offset):
            f.seek(offset)

            entries = []
            count = _unpack("Q", f.read(8), endian)[0]

            for _ in range(count):
              raw = f.read(entry_size)
              tag, typ = _unpack("HH", raw[:4], endian)
              count = _unpack("Q", raw[4:12], endian)[0]
              value = _unpack("Q", raw[12:20], endian)[0]
              entries.append((tag, typ, count, value))

            next = _unpack(endian + "Q", f.read(8), endian)[0]
            return entries, next

      while offset != 0:
        entries, offset = parse(offset)

        for tag, typ, count, value in entries:
          if tag == 256:
            width = int(value)
          elif tag == 257:
            height = int(value)

        if width > 0 and height > 0:
          type = ".tiff"
          break

    elif header[0:4] == b"RIFF" and header[8:12] == b"WEBP":
      f.seek(0)
      # [TODO] check big or little
      riff, size, webp = _unpack("4sI4s", f.read(12))

      if riff == b"RIFF" and webp == b"WEBP":
        type = ".webp"
        chunk_header = f.read(4)
        if chunk_header == b"VP8X":
          f.seek(8, 1)
          wb, hb = _unpack("3s3s", f.read(6), "I")
          width = int.from_bytes(wb, "little") + 1
          height = int.from_bytes(hb, "little") + 1

        elif chunk_header == b"VP8L":
          f.seek(5, 1)
          b = f.read(4)
          width = 1 + (((b[1] & 0x3F) << 8) | b[0])
          height = 1 + (((b[3] & 0xF) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))

        elif chunk_header == b"VP8 ":
          f.seek(10, 1)
          width, height = _unpack("HH", f.read(4), "I")
          width &= 0x3FFF
          height &= 0x3FFF

        else:
          type = "null"
          height = -1
          width = -1

  return (type, height, width)


def _shrink(file, output, maxWidth=None, merge=True, magic=False):
  shrink = False

  type, w, h = _gen_shrink_type(file)
  if type == "null":
    return shrink

  if magic:
    if not _check():
      return shrink

    path = str(Path(file).resolve())
    shell = ["ffmpeg", "-i", path]

    if type == ".heic":
      shell += ["-map", "0", "-y", "ex.%03d.jpg"]
      sr = _run(shell)

      if sr.returncode != 0:
        print(sr.stderr)

      # [TODO] pick right cols raws in bytes
      type = ".heic.jpg"
      shell = ["ffmpeg", "-i", "ex.%03d.jpg", "-vf", "tile=8x6", "-frames:v", "1"]

    if maxWidth is not None and w > maxWidth:
      m = max(w, h)
      if m > maxWidth:
        scale = maxWidth / m
        w = int(ceil(scale * w))
        shell += ["-vf", f"scale={w}:-1"]

    suffix = str(randint(1000, 9999)) + type
    ofile = file + suffix

    shell += ["-y", path + suffix]
    sr = _run(shell)

    if sr.returncode != 0:
      print(sr.stderr)

    if type.startswith(".heic"):
      for t in glob.glob("ex.*.jpg"):
        try:
          os.remove(t)
        except Exception:
          pass

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

  if type == ".jpg" or type == ".heic.jpg":
    if merge:
      exif = _extract_exif(file)
      mergeExif(exif, ofile, type == ".jpg")

  if type.endswith(".jpg"):
    genComment(ofile)

  times = float(os.path.getsize(ofile)) / os.path.getsize(file)
  shrink = times < 1

  if file == output and not shrink:
    os.remove(ofile)
  else:
    os.replace(ofile, output)

  print(f" > {output} has shrink {times:.1%}")
  return shrink


def shrinkFile(
  file,
  optimizeWidth=OPTIMIZE_WIDTH,
  thumbnailWidth=THUMBNAIL_WIDTH,
  override=True,
  magic=False,
):
  result = False

  if not os.path.exists(file):
    return result

  name, ext = os.path.splitext(file)
  if ext.lower() in MAGIC_EXT:
    magic = True

  if override:
    result = _shrink(file, file, magic=magic)
  else:
    result = _shrink(file, name + "-new" + ext, magic=magic)
    file = name + "-new" + ext

  _shrink(file, name + "-o" + ext, maxWidth=optimizeWidth, merge=False, magic=magic)
  _shrink(
    file, name + "-thumbnail" + ext, maxWidth=thumbnailWidth, merge=False, magic=magic
  )

  return result


def main():
  parser = argparse.ArgumentParser(description="EXIF tool")
  parser.add_argument("-f", "--file", type=str, help="parse image Exif info")
  parser.add_argument("-t", "--to", type=str, help="merge exif to file")
  parser.add_argument("-v", "--version", action="store_true", help="echo version")
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
    "-s",
    "--shrink",
    type=str,
    help="shrink file or folder with optimize and thumbnail generated",
  )

  args = parser.parse_args()

  if args.file:
    if args.to:
      exif = _extract_exif(args.file)
      result = {"merge": mergeExif(exif, args.to)}
    else:
      result = parseExif(args.file)

  elif args.shrink:
    if os.path.isdir(args.shrink):
      files = []
      for d, _, f in os.walk(args.shrink):
        for file in f:
          _, e = os.path.splitext(file)
          if e.lower() in IMAGE_EXT:
            files.append(os.path.join(d, file))

      shrink = 0
      for f in files:
        if shrinkFile(f, override=args.override, magic=args.magic):
          shrink += 1

      result = {
        "total": len(files),
        "shrink": shrink,
        "override": args.override,
        "magic": args.magic,
      }

    else:
      result = {
        "result": shrinkFile(args.shrink, override=args.override, magic=args.magic),
        "override": args.override,
        "magic": args.magic,
      }

  elif args.version:
    result = {"version": VERSION, "magic": _check()}
  else:
    print("usage: ex [-h] [-v] [-f FILE] [[-o] [-m] -s FILE]")
    return

  print(json.dumps(result, indent=2))


def todo(file):
  with open(file, "rb") as f:
    data = f.read()

  target = 0
  while target >= 0:
    target = data.find(S_APP1410, target + 1)
    print(target, data[target : target + 20])


if __name__ == "__main__":
  main()

# def lite(file, output):
#   with open(file, "rb") as f:
#     data = f.read()

#   segmentLite = []
#   segments = _segments(data)

#   for seg in segments:
#     prefix = seg[0:2]

#     if prefix in (S_SOI, S_DQT, S_DHT, S_DCT, S_SOS, S_DRI):
#       segmentLite.append(seg)

#     elif prefix == S_APP1 and seg[4:10] == S_APP1410:
#       segmentLite.append(_genLiteExif(seg))

#     elif prefix == S_COM:
#       length = _unpack("H", seg[2:4])[0]

#       try:
#         comments = seg[4 : length + 4].rstrip(b"\x00").decode("utf-8", errors="replace")
#         print("comments:", comments)
#       except Exception:
#         pass

#     else:
#       # length = _unpack("H", seg[2:4])
#       # print("Ignore:", seg[:2], length)
#       pass

#   _comment(segmentLite, "nt25.ef2")
#   with open(output, "wb") as f:
#     f.write(b"".join(segmentLite))
