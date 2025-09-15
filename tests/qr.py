# "pyzbar>=0.1.9",
# "qrcode[pil]>=8.2",

import qrcode
import qrcode.constants

from pyzbar.pyzbar import decode
from PIL import Image, ImageOps


def make_qr(
  data: str,
  file: str,
  mask=6,
  size=10,
  border=4,
  ecc=qrcode.constants.ERROR_CORRECT_L,
  fg="black",
  bg="white",
):
  qr = qrcode.QRCode(
    version=None,
    mask_pattern=mask,
    error_correction=ecc,
    box_size=size,
    border=border,
  )

  qr.add_data(data)
  qr.make(fit=True)

  img = qr.make_image(fill_color=fg, back_color=bg)
  img.save(file)
  print(f"{file}")


def read_qr(file: str) -> list[str]:
  objs = decode(Image.open(file))
  print(objs)
  texts = [o.data.decode("utf-8") for o in objs if o.type == "QRCODE"]
  return texts


def magic(file, output):
  img = Image.open(file)
  img = ImageOps.mirror(img)
  img = img.rotate(90, expand=True)
  # ffmpeg -i input.png -filter_complex "[0:v]vflip,rotate=PI/2" -c:v png output.png
  img.save(output)


if __name__ == "__main__":
  url = "http://a.b.c/entryid=view&yzm=S39c9817bbebac8av"
  target = "o.png"

  make_qr(url, target + ".png")
  read_qr("qa.png")
  read_qr("na.jpg")
  read_qr("o.png.png")

  # read_qr(target+".png")

  # magic(target+".png", target)
  # read_qr(target)

  # refer = read_qr('./tests/t.png')
  # for i in range(8):
  #   r = read_qr(f"./tests/qrcode_mask_{i}.jpg")
  #   print(r == refer)
